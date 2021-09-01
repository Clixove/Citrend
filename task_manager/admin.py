from django.contrib import admin
from .models import *

@admin.register(Factory)
class FactoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'trained_time', 'busy', 'mae']
    list_filter = ['user', 'trained_time', 'busy']
    search_fields = ['name']
    autocomplete_fields = ['user']


@admin.register(Column)
class ColumnAdmin(admin.ModelAdmin):
    list_display = ['factory', 'name', 'belong_transaction', 'is_date', 'is_company',
                    'is_score', 'use', 'log', 'diff', 'fill_na_avg']
    autocomplete_fields = ['factory']
    search_fields = ['factory', 'name']
