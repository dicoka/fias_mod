# coding: utf-8
from __future__ import unicode_literals, absolute_import

import six
from django.utils.encoding import python_2_unicode_compatible
from django.db import models

from fias.fields import UUIDField
from fias.models.common import June2016Update
from fias.models.status import CenterSt, CurentSt, OperStat


__all__ = ['AddrObj']


@python_2_unicode_compatible
class AddrObj(June2016Update):
    """
    Классификатор адресообразующих элементов
    """
    class Meta:
        app_label = 'fias'
        verbose_name = 'Адресообразующий элемент'
        verbose_name_plural = 'Адресообразующие элементы'
        index_together = (
            ('aolevel', 'shortname'),
            ('shortname', 'formalname'),
        )
        ordering = ['aolevel', 'formalname']

    aoguid = UUIDField('Глобальный уникальный идентификатор адресного объекта', primary_key=True)
    parentguid = UUIDField('Идентификатор объекта родительского объекта', blank=True, null=True, db_index=True)
    aoid = UUIDField('Уникальный идентификатор записи', db_index=True, unique=True)
    previd = UUIDField('Идентификатор записи связывания с предыдушей исторической записью', blank=True, null=True)
    nextid = UUIDField('Идентификатор записи  связывания с последующей исторической записью', blank=True, null=True)

    formalname = models.CharField('Формализованное наименование', max_length=120, db_index=True)
    offname = models.CharField('Официальное наименование', max_length=120, blank=True, null=True)
    shortname = models.CharField('Краткое наименование типа объекта', max_length=10, db_index=True)
    aolevel = models.PositiveSmallIntegerField('Уровень адресного объекта', db_index=True)

    # KLADE
    regioncode = models.CharField('Код региона', max_length=2)
    autocode = models.CharField('Код автономии', max_length=1)
    areacode = models.CharField('Код района', max_length=3)
    citycode = models.CharField('Код города', max_length=3)
    ctarcode = models.CharField('Код внутригородского района', max_length=3)
    placecode = models.CharField('Код населенного пункта', max_length=3)
    plancode = models.CharField('Код элемента планировочной структуры', max_length=4)
    streetcode = models.CharField('Код улицы', max_length=4)
    extrcode = models.CharField('Код дополнительного адресообразующего элемента', max_length=4)
    sextcode = models.CharField('Код подчиненного дополнительного адресообразующего элемента', max_length=3)

    # KLADR
    code = models.CharField('Код адресного объекта одной строкой с признаком актуальности из КЛАДР 4.0',
                            max_length=17, blank=True, null=True)
    plaincode = models.CharField('Код адресного объекта из КЛАДР 4.0 одной строкой',
                                 help_text='Без признака актуальности (последних двух цифр)',
                                 max_length=15, blank=True, null=True)

    actstatus = models.BooleanField('Статус исторической записи в жизненном цикле адресного объекта', default=False)
    centstatus = models.ForeignKey(CenterSt, verbose_name='Статус центра', default=0, on_delete=models.CASCADE)
    operstatus = models.ForeignKey(OperStat, verbose_name='Статус действия над записью – причина появления записи', default=0, on_delete=models.CASCADE)
    currstatus = models.ForeignKey(CurentSt, verbose_name='Статус актуальности КЛАДР 4',
                                   help_text='последние две цифры в коде', default=0, on_delete=models.CASCADE)

    livestatus = models.BooleanField('Признак действующего адресного объекта', default=False)


    # gnedoy
    parent_address = models.CharField('Полный адрес родителя', blank=True, default='', max_length=150,
                                      help_text='Сохранненный  в виде текстовой строки адрес родителей из ФИАС')

    def full_name(self, depth=None, formal=False):
        assert isinstance(depth, six.integer_types), 'Depth must be integer'

        if not self.parentguid or self.aolevel <= 1 or depth <= 0:
            if formal:
                return self.get_formal_name()
            return self.get_natural_name()
        else:
            parent = AddrObj.objects.get(pk=self.parentguid)
            return '{0}, {1}'.format(parent.full_name(depth-1, formal), self)

    def get_formal_name(self):
        return '{0}. {1}'.format(self.shortname, self.formalname)

    def full_name_rus(self, min_level=2):
        names_list = [self.get_natural_name()]
        try:
            parent = self
            while True:
                parent = AddrObj.objects.get(pk=parent.parentguid)
                if parent.aolevel < min_level:
                    break
                names_list.append(parent.get_natural_name())      # без Республики
        except:
            pass
        name = names_list[len(names_list) - 1]
        for i in range(len(names_list) - 2, -1, -1):
            name += ', ' + names_list[i]
        return name

    def full_address(self):
        return self.full_name(5)

    def get_natural_name(self):
        if self.shortname == 'р-н' or self.shortname == 'км':
            return '{0} {1}'.format(self.formalname, self.shortname)
        if self.shortname in ['ул', 'г', 'с', 'пер', 'тер', 'ш']:
            return '{0}. {1}'.format(self.shortname, self.formalname)
        return '{0} {1}'.format(self.shortname, self.formalname)

    def get_parent_natural_address(self):
        parents_natural_name = ''
        try:
            parent = AddrObj.objects.get(pk=self.parentguid)
            parents_natural_name = parent.get_natural_name()
            while True:
                parent = AddrObj.objects.get(pk=parent.parentguid)
                # name = name + ', ' + parent.get_natural_name()  # c Республикой
                if parent.aolevel == 1:
                    break
                parents_natural_name += ', ' + parent.get_natural_name()  # без Республики
        except:
            pass
        return parents_natural_name

    def get_natural_address(self):
        return '{}, {}'.format(self.get_natural_name(), self.get_parent_natural_address())

    def __str__(self):
        return '{}, {}'.format(self.get_natural_name(), self.parent_address)

    # gnedoy
    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if not update_fields or 'parent_address' not in update_fields:
            self.parent_address = ''
            if self.parentguid is not None:
                try:
                    self.parent_address = str(AddrObj.objects.get(pk=self.parentguid))
                except:
                    pass
            super(AddrObj, self).save(force_insert, force_update, using, update_fields)
            # change all children addresses
            parent_address = self.__str__()
            for addr in AddrObj.objects.filter(parentguid=self.aoguid):
                addr.parent_address = parent_address
                addr.save(update_fields=['parent_address'])
        else:
            super(AddrObj, self).save(force_insert, force_update, using, update_fields)

"""
CREATE INDEX index_addrobj_search ON fias_addrobj USING gin ((formalname || ' ' || parent_address) gin_trgm_ops);
"""