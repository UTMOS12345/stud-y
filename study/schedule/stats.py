"""Numbers for the statistics tab and the dashboard: planned time from schedule
blocks, focused time from finished Pomodoro sessions."""
import datetime

from django.utils import timezone

from .models import BlockSession, ScheduleBlock

DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']


def minutes_between(start, end):
    return (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)


def day_start(day):
    """Midnight at the start of `day` in the active (user's) time zone."""
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time.min))


def week_start(day):
    return day - datetime.timedelta(days=day.weekday())


def week_stats(user, day):
    """Planned and focused hours for each day (Mon-Sun) of the week holding `day`.
    Two queries for the whole week."""
    monday = week_start(day)
    planned = [0] * 7
    focused = [0] * 7

    for date, start, end in ScheduleBlock.objects.filter(
        schedule__user=user,
        schedule__date__range=(monday, monday + datetime.timedelta(days=6)),
    ).values_list('schedule__date', 'start_time', 'end_time'):
        planned[(date - monday).days] += minutes_between(start, end)

    for ended, seconds in BlockSession.objects.filter(
        user=user,
        end_time__gte=day_start(monday),
        end_time__lt=day_start(monday + datetime.timedelta(days=7)),
    ).values_list('end_time', 'focused_seconds'):
        focused[(timezone.localtime(ended).date() - monday).days] += seconds / 60

    return [
        {
            'date': monday + datetime.timedelta(days=i),
            'label': DAY_LABELS[i],
            'planned_hours': round(planned[i] / 60, 1),
            'focused_hours': round(focused[i] / 60, 1),
        }
        for i in range(7)
    ]
