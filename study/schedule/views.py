from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import DaySchedule, DayTemplate
from datetime import date

@login_required
def schedule_view(request):
    today = date.today()
    # This line caused your error - it will work once you run migrations
    schedule, created = DaySchedule.objects.get_or_create(user=request.user, date=today)
    templates = DayTemplate.objects.filter(user=request.user)
    
    return render(request, 'schedule/schedule.html', {
        'schedule': schedule,
        'templates': templates,
    })