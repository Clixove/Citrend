from django.contrib import admin
from .models import *


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['created_time', 'created_user', 'amount', 'paid', 'method', 'token']
    list_filter = ['created_time', 'paid', 'method']
    autocomplete_fields = ['created_user']
    search_fields = ['token']


@admin.register(PayingMethod)
class MethodAdmin(admin.ModelAdmin):
    list_display = ['name', 'payment_button_url']


@admin.register(Prestige)
class PrestigeAdmin(admin.ModelAdmin):
    list_display = ['created_time', 'created_user', 'amount', 'max_existed_factory', 'training_tickets', 'expired_time']
    list_filter = ['created_time', 'expired_time']
    autocomplete_fields = ['created_user', 'transaction']


@admin.register(WebsiteManager)
class WebsiteManagerAdmin(admin.ModelAdmin):
    list_display = ['user', 'email']
    autocomplete_fields = ['user']
