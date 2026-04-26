import json
from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import transaction

from .models import DaySchedule, DayTemplate, Action, ScheduleBlock, TemplateBlock
from .forms import ScheduleBlockForm

@login_required
def schedule_view(request):
    """
    Handles the main Schedule tab: Day view, Action management, 
    and applying/converting templates.
    """
    # 1. Handle Date Selection
    date_str = request.GET.get('date')
    try:
        selected_date = date.fromisoformat(date_str) if date_str else date.today()
    except (ValueError, TypeError):
        selected_date = date.today()

    # 2. Get or Create the schedule for the specific day
    schedule, _ = DaySchedule.objects.get_or_create(user=request.user, date=selected_date)
    
    # 3. Handle POST Requests
    if request.method == 'POST':
        
        # A. Handle AJAX/JSON Requests
        if request.headers.get('Content-Type') == 'application/json':
            try:
                data = json.loads(request.body)
                action_type = data.get('action')

                # Create or Update Action Bubble
                if action_type in ['create_action', 'update_action']:
                    name, color = data.get('name'), data.get('color', '#3B82F6')
                    icon, action_id = data.get('icon_name', 'activity'), data.get('action_id')
                    
                    if not name: return JsonResponse({'error': 'Name required'}, status=400)

                    if action_type == 'update_action' and action_id:
                        Action.objects.filter(id=action_id, user=request.user).update(
                            name=name, color=color, icon_name=icon
                        )
                    else:
                        Action.objects.create(user=request.user, name=name, color=color, icon_name=icon)
                    return JsonResponse({'success': True})

                # Delete a Schedule Block
                elif action_type == 'delete_block':
                    schedule.blocks.filter(id=data.get('block_id')).delete()
                    return JsonResponse({'success': True})

                # Delete a Template (from the list)
                elif action_type == 'delete_template':
                    DayTemplate.objects.filter(id=data.get('template_id'), user=request.user).delete()
                    return JsonResponse({'success': True})

                # Convert current day's blocks into a new Template
                elif action_type == 'convert_to_template':
                    name = data.get('template_name')
                    if not name: return JsonResponse({'error': 'Name required'}, status=400)
                    schedule.create_template_from_day(name)
                    return JsonResponse({'success': True})

                # Apply an existing Template to the current day
                elif action_type == 'apply_template':
                    template = DayTemplate.objects.filter(id=data.get('template_id'), user=request.user).first()
                    if not template: return JsonResponse({'error': 'Template not found'}, status=404)
                    
                    applied, skipped = template.apply_to_date_merge(selected_date)
                    return JsonResponse({
                        'success': True, 
                        'message': f"Applied {applied} blocks. {skipped} skipped (overlaps)."
                    })

            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)

        # B. Handle Standard Form Submission (Add/Edit Block)
        block_id = request.POST.get('block_id')
        instance = schedule.blocks.filter(id=block_id).first() if block_id else None
        form = ScheduleBlockForm(request.POST, user=request.user, instance=instance)
        
        if form.is_valid():
            new_block = form.save(commit=False)
            new_block.schedule = schedule
            try:
                new_block.save() # Model clean() handles overlap logic
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


@login_required
def template_detail_view(request, template_id):
    """
    Handles the Template Editor: View the structure of a template,
    add/edit/delete blocks within that template blueprint.
    """
    template = get_object_or_404(DayTemplate, id=template_id, user=request.user)
    
    if request.method == 'POST':
        # AJAX: Delete block from template
        if request.headers.get('Content-Type') == 'application/json':
            data = json.loads(request.body)
            if data.get('action') == 'delete_template_block':
                template.template_blocks.filter(id=data.get('block_id')).delete()
                return JsonResponse({'success': True})
        
        # Form: Add or Edit block in template
        block_id = request.POST.get('block_id')
        instance = template.template_blocks.filter(id=block_id).first() if block_id else None
        
        # Extract data from the same form fields used in the schedule
        title = request.POST.get('title')
        action_id = request.POST.get('action')
        start = request.POST.get('start_time')
        end = request.POST.get('end_time')
        desc = request.POST.get('description')
        b_type = request.POST.get('block_type', 'fixed')

        try:
            if instance:
                instance.title, instance.action_id = title, action_id
                instance.start_time, instance.end_time = start, end
                instance.description, instance.block_type = desc, b_type
                instance.save()
            else:
                TemplateBlock.objects.create(
                    template=template, title=title, action_id=action_id,
                    start_time=start, end_time=end,
                    description=desc, block_type=b_type
                )
            return redirect('template_detail', template_id=template.id)
        except Exception as e:
            # Handle template block save errors (e.g. invalid times)
            pass

    context = {
        'template': template,
        'actions': Action.objects.filter(user=request.user),
        # Empty form for the Modal
        'form': ScheduleBlockForm(user=request.user), 
    }
    return render(request, 'schedule/template_editor.html', context)