# coding: utf-8
from __future__ import unicode_literals, absolute_import
from fias.suggest import backend
from django.urls import path
from .views import AddressAutocompleteJSON

urlpatterns = backend.urlpatterns

urlpatterns += [
    path(
        'address_json/',
        AddressAutocompleteJSON,
        name='autocomplete-address-json'
    ),
]
