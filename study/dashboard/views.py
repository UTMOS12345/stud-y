from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from schedule.models import ScheduleBlock
from schedule.stats import block_stats, carried_over_block, focus_streak, format_minutes, summary, week_stats


def add_display_fields(block):
    block.planned = format_minutes(block.duration_minutes)
    block.color = block.action.color if block.action else '#6B7280'


def today_blocks(user, today):
    """Today's blocks with the focus time each one got."""
    blocks = list(
        ScheduleBlock.objects.filter(schedule__user=user, schedule__date=today)
        .select_related('action')
        .annotate(focused_seconds=Sum('sessions__focused_seconds'))
        .order_by('start_time')
    )
    for b in blocks:
        add_display_fields(b)
        b.focused = format_minutes((b.focused_seconds or 0) / 60)
    return blocks


def now_and_next(blocks, now, carried_over=None):
    """The block running at `now` (or None) and the next one to start.
    carried_over is last evening's block that runs into today."""
    now_minutes = now.hour * 60 + now.minute
    current, position = None, now_minutes
    if carried_over and now_minutes + 24 * 60 < carried_over.end_minutes:
        current, position = carried_over, now_minutes + 24 * 60  # counted from yesterday's midnight
    else:
        current = next((b for b in blocks if b.start_minutes <= now_minutes < b.end_minutes), None)
    upcoming = next((b for b in blocks if b.start_minutes > now_minutes), None)
    if current:
        current.minutes_left = current.end_minutes - position
        current.progress = round((position - current.start_minutes) * 100 / current.duration_minutes)
    if upcoming:
        upcoming.starts_in = format_minutes(upcoming.start_minutes - now_minutes)
    return current, upcoming


@login_required
def dashboard(request):
    now = timezone.localtime()
    blocks = today_blocks(request.user, now.date())
    carried_over = carried_over_block(request.user, now.date())
    if carried_over:
        add_display_fields(carried_over)
    current, upcoming = now_and_next(blocks, now.time(), carried_over)
    now_minutes = now.hour * 60 + now.minute
    for b in blocks:
        b.is_done = b.end_minutes <= now_minutes
        b.is_current = b is current

    day = summary(block_stats(request.user, now.date()), len(blocks))
    week = week_stats(request.user, now.date())
    week_planned = sum(d['planned_hours'] for d in week)
    week_focused = sum(d['focused_hours'] for d in week)
    tallest = max([max(d['planned_hours'], d['focused_hours']) for d in week] + [0.1])
    for d in week:
        d['planned_height'] = round(d['planned_hours'] * 100 / tallest)
        d['focused_height'] = round(d['focused_hours'] * 100 / tallest)
        d['is_today'] = d['date'] == now.date()

    return render(request, 'dashboard.html', {
        'today': now.date(),
        'day': day,
        'streak': focus_streak(request.user, now.date()),
        'week': week,
        'week_planned': round(week_planned, 1),
        'week_focused': round(week_focused, 1),
        'week_percent': min(100, round(week_focused * 100 / week_planned)) if week_planned else None,
        'blocks': blocks,
        'current': current,
        'upcoming': upcoming,
    })
