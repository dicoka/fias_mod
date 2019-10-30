# coding: utf-8
from __future__ import unicode_literals, absolute_import
import re
from itertools import permutations
import string
from django.db.models import Q, Value as V
from django.db.models.functions import Concat
from django.http import JsonResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from fias.models.addrobj import AddrObj


# Create your views here.


@login_required
def AddressAutocompleteJSON(request):
    query = request.GET.get('query', '')
    suggestions = []
    if len(query) < 1:
        return JsonResponse({'suggestions': suggestions}, safe=False)
    # удаляем пунктуацию
    #query = query.translate(str.maketrans('', '', string.punctuation))
    query = query.replace('.', ' ').replace(',', ' ')
    # делим на отдельные слова
    key_words = query.split()
    # удаляем короткие названия типа "ул", "гор" и т.п.
    for short_name in short_names:
        key_words = [x for x in key_words if x != short_name]
    if len(key_words) == 0:
        return JsonResponse({'suggestions': suggestions}, safe=False)

    # ***************
    # 1.Вариант с поиском без текстовой строки (0.03-1.3 сек)
    #qs = addr_search(key_words)
    #qs = qs[:10]

    # 2.Вариант с поиском по текстовой строке средствами Django (0.06 сек, индекс не помогает)
    """
    q = Q()
    for word in key_words:
        q = q & Q(saved_text__icontains=word)
    qs = AddrObj.objects\
        .filter(q)\
        .only('pk', 'saved_text', 'aoguid')
    qs = qs[:10]
    """

    # 3.Вариант c поиском по текстовой строке с raw запросом (0.003-0.005сек с индексом)
    sub_query = ''
    order_by = ''
    ilike = "%%{}%%".format(key_words[0])
    ilike_rev = "%%{}%%".format(key_words[-1])
    for i in range(1, len(key_words)):
        sub_query += "AND formalname || ' ' || parent_address ILIKE '%%{}%%' ".format(key_words[i])
        order_by += " , formalname || ' ' || parent_address ILIKE '%%{}%%' OR NULL ".format(key_words[i])
        ilike += "%%{}%%".format(key_words[i])
        ilike_rev += "%%{}%%".format(key_words[len(key_words) - i - 1])
    query =\
'''
SELECT aoguid, shortname, formalname, parent_address
FROM fias_addrobj 
WHERE formalname || ' ' || parent_address  ILIKE '{1}' OR formalname || ' ' || parent_address ILIKE '{2}'
ORDER BY formalname ILIKE '{0}' OR NULL
       , formalname ILIKE '{0}%%' OR NULL
       , formalname ILIKE '%%{0}%%' OR NULL
LIMIT 10
'''

    query = query.format(key_words[0], ilike, ilike_rev)

    print(query)

    qs = AddrObj.objects.raw(query)

    #^^^^^^^^^^********

    compiled_key_words = [re.compile(r'(?P<WORD>({}))'.format(word), re.IGNORECASE) for word in key_words]

    import time
    start = time.time()

    for item in qs:
        value_html = value = item.__str__()
        # highlight key words
        for pattern in compiled_key_words:
            value_html = re.sub(pattern, r'<strong>\g<WORD></strong>', value_html)
        suggestions.append({'value': value, 'value_html': value_html, 'data': str(item.pk)})

    end = time.time()
    print(end - start)
    return JsonResponse({'suggestions': suggestions}, safe=False)


# TODO при миграции использовать short_names = [], иначе ошибка
try:
    short_names = AddrObj.objects.order_by().values('shortname').distinct()
    short_names = short_names.values_list('shortname', flat=True)
    short_names = list(short_names)
except Exception as ex:
    print("Autocomplete view shortnames exception (it's ok when migrating): ()".format(ex))
    short_names = []


def addr_search(key_words):
    num_key_words = len(key_words)
    if num_key_words == 0:
        return None

    qs_all = AddrObj.objects.all()
    # все улицы, нас.пункты
    qs_base = qs_all.filter(Q(aolevel=7) | Q(aolevel=6) | Q(aolevel=65) | Q(aolevel=4))

    # переставляем слова в запросе, перебираем все комбинации
    qs_permutations = AddrObj.objects.none()
    for request in permutations(key_words, num_key_words):
        # где совпадает имя из 1 слова
        # --начинается
        # qs = qs_1 = qs_base.filter(formalname__istartswith=requests[0])
        # --или содержит
        qs = qs_1 = qs_base.filter(formalname__icontains=request[0])

        if num_key_words > 1:

            # где совпадает имя из 2-х слов
            # -- совпадают только начала слов
            # qs_2 = qs_base.filter(formalname__iregex=r'^({0}.* {1}.*)'.format(requests[0], requests[1]))
            # -- или не только начала слов, а содержат искомые слова
            qs_2 = qs_base.filter(formalname__iregex=r'^(.*{0}.*{1}.*)'.format(request[0], request[1]))

            # где совпадает родитель (исключаем респ. Крым)
            qs_parent1 = qs_all.filter(formalname__icontains=request[1]).exclude(aolevel=1)
            # где совпадает родитель родителя
            qs_parent_parent1 = qs_all.filter(parentguid__in=qs_parent1)

            if num_key_words == 2:
                # где совпадает еще родитель |или еще и родитель родителя |или совпадает имя из 2-х слов
                qs = qs_1.filter(parentguid__in=qs_parent1) | qs_1.filter(parentguid__in=qs_parent_parent1) | qs_2

            else:  # > 2
                # где совпадает имя из 3-х слов
                qs_3 = qs_base.filter(
                    formalname__iregex=r'^(.*{0}.*{1}.*{2}.*)'.format(request[0], request[1], request[2]))
                # где совпадает родитель (исключаем респ. Крым)
                qs_parent2 = qs_all.filter(formalname__icontains=request[2]).exclude(aolevel=1)
                # где совпадает родитель родителя
                qs_parent_parent2 = qs_all.filter(parentguid__in=qs_parent2)
                # улица из 2-х слов и родитель | или совпадает улица из 2-х слов и родитель родителя |или улица из 3-х слов
                qs = qs_2.filter(parentguid__in=qs_parent2) | qs_2.filter(parentguid__in=qs_parent_parent2) | qs_3
                # или совпадает улица из 1 слова и родитель и родитель родителя
                qs_parent1_parent2 = qs_parent1.filter(parentguid__in=qs_parent2)
                qs = qs | qs_1.filter(parentguid__in=qs_parent1_parent2)
                # или совпадает улица и родитель из 2-х слов
                qs_parent_2 = qs_base.filter(formalname__iregex=r'^(.*{0}.*{1}.*)'.format(request[1], request[2]))
                qs = qs | qs_1.filter(parentguid__in=qs_parent_2)

        qs_permutations = qs_permutations | qs

    return qs_permutations


book_search_str = Concat('number', V(' '),
                       'address_irregular', V(' '),
                       'address_saved', V(' '),
                       'address_house', V(' '),
                       'address_apartment')