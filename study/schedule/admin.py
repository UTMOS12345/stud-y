from django.contrib import admin
from .models import DaySchedule, ScheduleBlock, BlockSession, DayTemplate, TemplateBlock, Action


class ScheduleBlockInline(admin.TabularInline):
    model = ScheduleBlock
    extra = 0
    fields = ('start_time', 'end_time', 'title', 'action', 'block_type')


class TemplateBlockInline(admin.TabularInline):
    model = TemplateBlock
    extra = 0
    fields = ('order', 'start_time', 'end_time', 'title', 'action', 'block_type')


@admin.register(DaySchedule)
class DayScheduleAdmin(admin.ModelAdmin):
    list_display = ('date', 'user', 'template')
    list_filter = ('date',)
    search_fields = ('user__email',)
    date_hierarchy = 'date'
    list_select_related = ('user', 'template')
    inlines = [ScheduleBlockInline]


@admin.register(ScheduleBlock)
class ScheduleBlockAdmin(admin.ModelAdmin):
    list_display = ('title', 'schedule', 'start_time', 'end_time', 'action', 'block_type')
    list_filter = ('block_type',)
    search_fields = ('title', 'schedule__user__email')
    list_select_related = ('schedule__user', 'action')


@admin.register(DayTemplate)
class DayTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'user')
    search_fields = ('name', 'user__email')
    list_select_related = ('user',)
    inlines = [TemplateBlockInline]


@admin.register(Action)
class ActionAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'color', 'icon_name')
    search_fields = ('name', 'user__email')
    list_select_related = ('user',)


@admin.register(BlockSession)
class BlockSessionAdmin(admin.ModelAdmin):
    list_display = ('block', 'start_time', 'end_time')
    list_select_related = ('block',)


admin.site.register(TemplateBlock)
