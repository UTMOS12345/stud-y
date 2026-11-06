import datetime
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import Profile
from schedule.models import BlockSession

# Longest focus session we accept, the same as the longest pomodoro allowed in settings
MAX_SESSION_SECONDS = 120 * 60


@login_required
def pomodoro(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)

    context = {
        'pomodoro_time': profile.default_pomodoro_duration,
        'short_break_time': profile.default_short_break_duration,
        'long_break_time': profile.default_long_break_duration,
        'long_break_interval': profile.default_long_break_interval,
    }

    return render(request, 'pomodoro.html', context)


@login_required
@require_POST
def save_session(request):
    """Save one finished focus session. Body: {"focused_seconds": 1500}"""
    try:
        data = json.loads(request.body)
        seconds = int(data.get('focused_seconds'))
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({'error': 'focused_seconds must be a number'}, status=400)

    if not 1 <= seconds <= MAX_SESSION_SECONDS:
        return JsonResponse({'error': f'focused_seconds must be between 1 and {MAX_SESSION_SECONDS}'}, status=400)

    end = timezone.now()
    session = BlockSession.objects.create(
        user=request.user,
        start_time=end - datetime.timedelta(seconds=seconds),
        end_time=end,
        focused_seconds=seconds,
    )
    return JsonResponse({'id': session.id, 'focused_seconds': seconds}, status=201)
