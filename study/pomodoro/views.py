import datetime
import json

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import Profile
from schedule.models import BlockSession, ScheduleBlock

# Longest focus session we accept: block mode can time a whole block, like a school day
MAX_SESSION_SECONDS = 16 * 3600


def today_bounds():
    """Start and end of today in the user's time zone."""
    start = timezone.make_aware(datetime.datetime.combine(timezone.localdate(), datetime.time.min))
    return start, start + datetime.timedelta(days=1)


@login_required
def pomodoro(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    start, end = today_bounds()
    today = BlockSession.objects.filter(
        user=request.user, end_time__gte=start, end_time__lt=end,
    ).aggregate(count=Count('id'), seconds=Sum('focused_seconds'))

    # blocks you can focus on: today's, plus one picked from the schedule (?block=)
    blocks = list(ScheduleBlock.objects.filter(
        schedule__user=request.user, schedule__date=timezone.localdate(),
    ).select_related('action', 'schedule'))
    selected_id = None
    requested = request.GET.get('block', '')
    if requested.isdigit():
        picked = ScheduleBlock.objects.filter(pk=requested, schedule__user=request.user).select_related('action', 'schedule').first()
        if picked:
            selected_id = picked.id
            if picked not in blocks:
                blocks.insert(0, picked)
    if selected_id is None:
        now = timezone.localtime().time()
        current = next((b for b in blocks if b.start_time <= now < b.end_time), None)
        selected_id = current.id if current else None

    context = {
        'pomodoro_time': profile.default_pomodoro_duration,
        'short_break_time': profile.default_short_break_duration,
        'long_break_time': profile.default_long_break_duration,
        'long_break_interval': profile.default_long_break_interval,
        'today_sessions': today['count'],
        'today_focused_seconds': today['seconds'] or 0,
        'today': timezone.localdate(),
        'blocks': blocks,
        'selected_block_id': selected_id,
        'block_from_link': requested.isdigit() and selected_id is not None,
    }

    return render(request, 'pomodoro.html', context)


@login_required
@require_POST
def save_session(request):
    """Save one finished focus session.
    Body: {"focused_seconds": 1500, "block_id": 12, "ended_at": 1767600000000}
    block_id is optional. ended_at is when the session really ended, in milliseconds
    since 1970, because a session can reach the server long after it finished."""
    try:
        data = json.loads(request.body)
        seconds = int(data.get('focused_seconds'))
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({'error': 'focused_seconds must be a number'}, status=400)

    if not 1 <= seconds <= MAX_SESSION_SECONDS:
        return JsonResponse({'error': f'focused_seconds must be between 1 and {MAX_SESSION_SECONDS}'}, status=400)

    block = None
    block_id = data.get('block_id')
    if block_id not in (None, ''):
        if str(block_id).isdigit():
            block = ScheduleBlock.objects.filter(pk=block_id, schedule__user=request.user).first()
        if block is None:
            return JsonResponse({'error': 'Block not found'}, status=404)

    end = timezone.now()
    ended_at = data.get('ended_at')
    if ended_at is not None:
        try:
            if isinstance(ended_at, bool) or ended_at <= 0:
                raise ValueError
            reported = datetime.datetime.fromtimestamp(ended_at / 1000, tz=datetime.timezone.utc)
        except (TypeError, ValueError, OverflowError, OSError):
            return JsonResponse({'error': 'ended_at must be a time in milliseconds'}, status=400)
        end = min(end, reported)  # a device clock running fast can't create future sessions

        # the same upload arriving twice (two tabs, a lost response) is one session
        existing = BlockSession.objects.filter(user=request.user, end_time=end, focused_seconds=seconds).first()
        if existing:
            return JsonResponse({'id': existing.id, 'focused_seconds': seconds})

    session = BlockSession.objects.create(
        user=request.user,
        block=block,
        start_time=end - datetime.timedelta(seconds=seconds),
        end_time=end,
        focused_seconds=seconds,
    )
    return JsonResponse({'id': session.id, 'focused_seconds': seconds}, status=201)
