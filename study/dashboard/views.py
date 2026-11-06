from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from schedule.models import ScheduleBlock
from schedule.stats import format_minutes, minutes_between


def today_blocks(user, today):
    """Today's blocks with the focus time each one got."""
    blocks = list(
        ScheduleBlock.objects.filter(schedule__user=user, schedule__date=today)
        .select_related('action')
        .annotate(focused_seconds=Sum('sessions__focused_seconds'))
        .order_by('start_time')
    )
    for b in blocks:
        b.planned = format_minutes(minutes_between(b.start_time, b.end_time))
        b.focused = format_minutes((b.focused_seconds or 0) / 60)
        b.color = b.action.color if b.action else '#6B7280'
    return blocks


def now_and_next(blocks, now):
    """The block running at `now` (or None) and the next one to start."""
    current = next((b for b in blocks if b.start_time <= now < b.end_time), None)
    upcoming = next((b for b in blocks if b.start_time > now), None)
    if current:
        current.minutes_left = minutes_between(now, current.end_time)
        current.progress = round(
            minutes_between(current.start_time, now) * 100 / minutes_between(current.start_time, current.end_time)
        )
    if upcoming:
        upcoming.starts_in = format_minutes(minutes_between(now, upcoming.start_time))
    return current, upcoming


@login_required
def dashboard(request):
    now = timezone.localtime()
    blocks = today_blocks(request.user, now.date())
    current, upcoming = now_and_next(blocks, now.time())
    for b in blocks:
        b.is_done = b.end_time <= now.time()
        b.is_current = b is current

    return render(request, 'dashboard.html', {
        'today': now.date(),
        'blocks': blocks,
        'current': current,
        'upcoming': upcoming,
    })
