from django.contrib import admin
from .models import DaySchedule, ScheduleBlock, BlockSession, DayTemplate, TemplateBlock, Action

admin.site.register(DaySchedule)
admin.site.register(ScheduleBlock)
admin.site.register(BlockSession)
admin.site.register(DayTemplate)
admin.site.register(TemplateBlock)
admin.site.register(Action)

