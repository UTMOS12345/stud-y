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


NO_SUBJECT = {'name': 'No subject', 'color': '#6B7280'}


def subject_stats(user, first_day, last_day=None):
    """Planned and focused minutes per action (subject) between two dates.
    Focus sessions without a block, or on a block without an action, go to 'No subject'.
    Sorted by planned time, then focused time. Two queries."""
    last_day = last_day or first_day
    subjects = {}

    def row(action_id, name, color):
        if action_id is None:
            action_id, name, color = None, NO_SUBJECT['name'], NO_SUBJECT['color']
        return subjects.setdefault(action_id, {
            'name': name, 'color': color, 'planned_minutes': 0, 'focused_minutes': 0, 'sessions': 0,
        })

    for action_id, name, color, start, end in ScheduleBlock.objects.filter(
        schedule__user=user, schedule__date__range=(first_day, last_day),
    ).values_list('action_id', 'action__name', 'action__color', 'start_time', 'end_time'):
        row(action_id, name, color)['planned_minutes'] += minutes_between(start, end)

    for action_id, name, color, seconds in BlockSession.objects.filter(
        user=user,
        end_time__gte=day_start(first_day),
        end_time__lt=day_start(last_day + datetime.timedelta(days=1)),
    ).values_list('block__action_id', 'block__action__name', 'block__action__color', 'focused_seconds'):
        subject = row(action_id, name, color)
        subject['focused_minutes'] += seconds / 60
        subject['sessions'] += 1

    result = list(subjects.values())
    for r in result:
        r['focused_minutes'] = round(r['focused_minutes'])
    result.sort(key=lambda r: (-r['planned_minutes'], -r['focused_minutes'], r['name']))
    return result


def format_minutes(minutes):
    """90 -> '1h 30m', 60 -> '1h', 5 -> '5m'"""
    minutes = int(round(minutes))
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h}h {m}m"
    return f"{h}h" if h else f"{m}m"


def summary(subjects, block_count):
    """Totals for the stat cards, from the rows subject_stats() returned."""
    planned = sum(s['planned_minutes'] for s in subjects)
    focused = sum(s['focused_minutes'] for s in subjects)
    top = subjects[0] if subjects and subjects[0]['planned_minutes'] else None
    return {
        'planned_minutes': planned,
        'planned': format_minutes(planned),
        'focused_minutes': focused,
        'focused': format_minutes(focused),
        'sessions': sum(s['sessions'] for s in subjects),
        'blocks': block_count,
        # share of the plan you actually focused on, capped at 100
        'done_percent': min(100, round(focused * 100 / planned)) if planned else None,
        'top_subject': top['name'] if top else None,
        'top_subject_time': format_minutes(top['planned_minutes']) if top else '',
    }


def week_subjects(user, day):
    """subject_stats() for the whole week holding `day`, with bar widths (0-100)
    and readable times ready for the template."""
    monday = week_start(day)
    rows = subject_stats(user, monday, monday + datetime.timedelta(days=6))
    longest = max([max(r['planned_minutes'], r['focused_minutes']) for r in rows] + [1])
    for r in rows:
        r['planned'] = format_minutes(r['planned_minutes'])
        r['focused'] = format_minutes(r['focused_minutes'])
        r['planned_width'] = round(r['planned_minutes'] * 100 / longest)
        r['focused_width'] = round(r['focused_minutes'] * 100 / longest)
    return rows
