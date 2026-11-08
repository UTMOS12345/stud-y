from django.contrib import admin

from .models import Habit, HabitEntry


@admin.register(Habit)
class HabitAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'kind', 'color', 'created_at')
    list_filter = ('kind',)
    search_fields = ('name', 'user__email')
    list_select_related = ('user',)


@admin.register(HabitEntry)
class HabitEntryAdmin(admin.ModelAdmin):
    list_display = ('habit', 'date', 'value')
    date_hierarchy = 'date'
    list_select_related = ('habit',)
