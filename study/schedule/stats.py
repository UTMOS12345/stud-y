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


NO_BLOCK = {'name': 'No block', 'color': '#6B7280'}


def block_stats(user, first_day, last_day=None):
    """Planned and focused minutes per block (grouped by action) between two dates.
    Focus sessions without a block, or on a block without an action, go to 'No block'.
    Sorted by planned time, then focused time. Two queries."""
    last_day = last_day or first_day
    rows = {}

    def row(action_id, name, color):
        if action_id is None:
            action_id, name, color = None, NO_BLOCK['name'], NO_BLOCK['color']
        return rows.setdefault(action_id, {
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
        entry = row(action_id, name, color)
        entry['focused_minutes'] += seconds / 60
        entry['sessions'] += 1

    result = list(rows.values())
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


def summary(rows, block_count):
    """Totals for the stat cards, from the rows block_stats() returned."""
    planned = sum(s['planned_minutes'] for s in rows)
    focused = sum(s['focused_minutes'] for s in rows)
    top = rows[0] if rows and rows[0]['planned_minutes'] else None
    return {
        'planned_minutes': planned,
        'planned': format_minutes(planned),
        'focused_minutes': focused,
        'focused': format_minutes(focused),
        'sessions': sum(s['sessions'] for s in rows),
        'blocks': block_count,
        # share of the plan you actually focused on, capped at 100
        'done_percent': min(100, round(focused * 100 / planned)) if planned else None,
        'top_block': top['name'] if top else None,
        'top_block_time': format_minutes(top['planned_minutes']) if top else '',
    }


def week_blocks(user, day):
    """block_stats() for the whole week holding `day`, with bar widths (0-100)
    and readable times ready for the template."""
    monday = week_start(day)
    rows = block_stats(user, monday, monday + datetime.timedelta(days=6))
    longest = max([max(r['planned_minutes'], r['focused_minutes']) for r in rows] + [1])
    for r in rows:
        r['planned'] = format_minutes(r['planned_minutes'])
        r['focused'] = format_minutes(r['focused_minutes'])
        r['planned_width'] = round(r['planned_minutes'] * 100 / longest)
        r['focused_width'] = round(r['focused_minutes'] * 100 / longest)
    return rows


def focus_streak(user, today, look_back_days=366):
    """How many days in a row, up to today, have at least one focus session.
    A streak that reached yesterday still counts while today has no session yet."""
    since = today - datetime.timedelta(days=look_back_days)
    days = {
        timezone.localtime(ended).date()
        for ended in BlockSession.objects.filter(
            user=user, end_time__gte=day_start(since),
        ).values_list('end_time', flat=True)
    }
    day = today if today in days else today - datetime.timedelta(days=1)
    streak = 0
    while day in days:
        streak += 1
        day -= datetime.timedelta(days=1)
    return streak


def longest_run(days):
    """Longest run of consecutive dates in a set."""
    best = 0
    for day in days:
        if day - datetime.timedelta(days=1) in days:
            continue  # not the start of a run
        length = 1
        while day + datetime.timedelta(days=length) in days:
            length += 1
        best = max(best, length)
    return best


def records(user):
    """All-time numbers from every focus session. One query."""
    per_day = {}
    total = count = 0
    for ended, seconds in BlockSession.objects.filter(user=user).values_list('end_time', 'focused_seconds'):
        day = timezone.localtime(ended).date()
        per_day[day] = per_day.get(day, 0) + seconds
        total += seconds
        count += 1

    best_day, best_seconds = max(per_day.items(), key=lambda kv: kv[1]) if per_day else (None, 0)
    return {
        'sessions': count,
        'total_hours': round(total / 3600, 1),
        'average_session': format_minutes(total / 60 / count) if count else None,
        'best_day': best_day,
        'best_day_time': format_minutes(best_seconds / 60),
        'longest_streak': longest_run(set(per_day)),
        'active_days': len(per_day),
    }


def heat_level(minutes):
    """0-4, like a contribution calendar."""
    if minutes <= 0:
        return 0
    if minutes < 30:
        return 1
    if minutes < 60:
        return 2
    if minutes < 120:
        return 3
    return 4


def recent_focus(user, day, weeks=5):
    """Focus over the last `weeks` weeks up to the week holding `day`, one query:
    - calendar: rows of 7 days (Mon-Sun) with minutes and a 0-4 level
    - hours: focused minutes for each hour of the day (0-23), split across hours
      when a session runs past the hour"""
    first = week_start(day) - datetime.timedelta(weeks=weeks - 1)
    last = week_start(day) + datetime.timedelta(days=6)
    per_day = {}
    per_hour = [0.0] * 24

    for ended, seconds in BlockSession.objects.filter(
        user=user, end_time__gte=day_start(first), end_time__lt=day_start(last + datetime.timedelta(days=1)),
    ).values_list('end_time', 'focused_seconds'):
        local_end = timezone.localtime(ended)
        per_day[local_end.date()] = per_day.get(local_end.date(), 0) + seconds / 60

        # spread the focused minutes over the hours the session covered
        start = local_end - datetime.timedelta(seconds=seconds)
        while start < local_end:
            next_hour = (start + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            chunk_end = min(next_hour, local_end)
            per_hour[start.hour] += (chunk_end - start).total_seconds() / 60
            start = chunk_end

    today = timezone.localdate()
    calendar = []
    for w in range(weeks):
        row = []
        for d in range(7):
            date = first + datetime.timedelta(days=w * 7 + d)
            minutes = round(per_day.get(date, 0))
            row.append({
                'date': date,
                'minutes': minutes,
                'time': format_minutes(minutes),
                'level': heat_level(minutes),
                'is_future': date > today,
                'is_selected': date == day,
            })
        calendar.append(row)

    tallest = max(per_hour + [1])
    hours = [{'hour': h, 'minutes': round(m), 'height': round(m * 100 / tallest)} for h, m in enumerate(per_hour)]
    peak = max(hours, key=lambda h: h['minutes'])
    return {
        'calendar': calendar,
        'hours': hours,
        'peak_hour': peak['hour'] if peak['minutes'] else None,
        'total': format_minutes(sum(per_day.values())),
    }
