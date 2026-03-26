from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
import json
from .models import DaySchedule, DayTemplate, Action
from .forms import ScheduleBlockForm
from datetime import date

@login_required
def schedule_view(request):
    today = date.today()
    # Logic: Get or create today's schedule for this user
    schedule, created = DaySchedule.objects.get_or_create(user=request.user, date=today)
    
    if request.method == 'POST':
        if request.headers.get('Content-Type') == 'application/json':
            try:
                data = json.loads(request.body)
                if data.get('action') == 'create_action':
                    name = data.get('name')
                    color = data.get('color', '#3B82F6')
                    icon_name = data.get('icon_name', 'activity')
                    if name:
                        action, created = Action.objects.get_or_create(
                            user=request.user, name=name,
                            defaults={'color': color, 'icon_name': icon_name}
                        )
                        return JsonResponse({'id': action.id, 'name': action.name, 'color': action.color, 'icon_name': action.icon_name})
                    return JsonResponse({'error': 'Name is required'}, status=400)
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)

        # Pass the user to the form so it can filter Action choices
        form = ScheduleBlockForm(request.POST, user=request.user)
        if form.is_valid():
            new_block = form.save(commit=False)
            new_block.schedule = schedule
            try:
                new_block.save() # Triggers model full_clean()
                return redirect(request.path) # Refresh page
            except ValidationError as e:
                form.add_error(None, e)
    else:
        form = ScheduleBlockForm(user=request.user)
    
    context = {
        'schedule': schedule,
        'form': form,
        'templates': DayTemplate.objects.filter(user=request.user),
        'actions': Action.objects.filter(user=request.user),
    }
    return render(request, 'schedule/schedule.html', context)
