from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def pomodoro(request):
    return render(request, 'pomodoro.html', {'profile': request.user.profile})