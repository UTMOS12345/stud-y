from django.contrib import admin

from .models import Card, Column


@admin.register(Column)
class ColumnAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'position')
    search_fields = ('name', 'user__email')
    list_select_related = ('user',)


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('title', 'column', 'position', 'created_at')
    search_fields = ('title',)
    list_select_related = ('column',)
