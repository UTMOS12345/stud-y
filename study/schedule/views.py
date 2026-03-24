from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import DaySchedule, DayTemplate, ScheduleBlock
from .forms import ScheduleBlockForm
from datetime import date
from django.core.exceptions import ValidationError

@login_required
def schedule_view(request):
    today = date.today()
    schedule, created = DaySchedule.objects.get_or_create(user=request.user, date=today)
    templates = DayTemplate.objects.filter(user=request.user)
    
    if request.method == 'POST':
        form = ScheduleBlockForm(request.POST)
        if form.is_valid():
            new_block = form.save(commit=False)
            new_block.schedule = schedule  # Assign the current day's schedule
            try:
                new_block.save()  # This triggers the overlap check in your model
                return redirect('schedule') # Refresh to show new block
            except ValidationError as e:
                # If there's an overlap error, send it back to the form
                form.add_error(None, e)
    else:
        form = ScheduleBlockForm()
    
    return render(request, 'schedule/schedule.html', {
        'schedule': schedule,
        'templates': templates,
        'form': form, # Pass the form to the template
    })