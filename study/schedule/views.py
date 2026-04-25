import json
from datetime import date
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import DaySchedule, DayTemplate, Action
from .forms import ScheduleBlockForm

@login_required
def schedule_view(request):
    date_str = request.GET.get('date')
    try:
        selected_date = date.fromisoformat(date_str) if date_str else date.today()
    except (ValueError, TypeError):
        selected_date = date.today()

    schedule, _ = DaySchedule.objects.get_or_create(user=request.user, date=selected_date)
    
    if request.method == 'POST':
        if request.headers.get('Content-Type') == 'application/json':
            try:
                data = json.loads(request.body)
                action_type = data.get('action')

                # CONVERT TO TEMPLATE
                if action_type == 'convert_to_template':
                    name = data.get('template_name')
                    if not name:
                        return JsonResponse({'error': 'Name is required'}, status=400)
                    # Calls method in DaySchedule model
                    template = schedule.create_template_from_day(name)
                    return JsonResponse({'success': True, 'id': template.id})

                # APPLY TEMPLATE
                elif action_type == 'apply_template':
                    template_id = data.get('template_id')
                    template = DayTemplate.objects.filter(id=template_id, user=request.user).first()
                    if not template:
                        return JsonResponse({'error': 'Template not found'}, status=404)
                    
                    # Calls method in DayTemplate model
                    applied, skipped = template.apply_to_date_merge(selected_date)
                    return JsonResponse({
                        'success': True, 
                        'message': f"Applied {applied} blocks. {skipped} skipped."
                    })

                # DELETE BLOCK
                elif action_type == 'delete_block':
                    block_id = data.get('block_id')
                    schedule.blocks.filter(id=block_id).delete()
                    return JsonResponse({'success': True})

            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)

        # Standard Form Handling (Add/Edit Block)
        block_id = request.POST.get('block_id')
        instance = schedule.blocks.filter(id=block_id).first() if block_id else None
        form = ScheduleBlockForm(request.POST, user=request.user, instance=instance)
        
        if form.is_valid():
            new_block = form.save(commit=False)
            new_block.schedule = schedule
            try:
                new_block.save()
                return redirect(f"{request.path}?date={selected_date.isoformat()}")
            except Exception as e:
                form.add_error(None, str(e))
    else:
        form = ScheduleBlockForm(user=request.user)

    context = {
        'schedule': schedule,
        'form': form,
        'templates': DayTemplate.objects.filter(user=request.user),
        'actions': Action.objects.filter(user=request.user),
        'selected_date': selected_date,
    }
    return render(request, 'schedule/schedule.html', context)