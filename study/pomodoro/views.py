from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# Import Profile from accounts app
from accounts.models import Profile


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