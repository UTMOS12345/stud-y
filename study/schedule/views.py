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
    date_str = request.GET.get('date')
    try:
        selected_date = date.fromisoformat(date_str) if date_str else date.today()
    except (ValueError, TypeError):
        selected_date = date.today()

    schedule, created = DaySchedule.objects.get_or_create(user=request.user, date=selected_date)
    
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
                elif data.get('action') == 'delete_block':
                    block_id = data.get('block_id')
                    if block_id:
                        block = schedule.blocks.filter(id=block_id).first()
                        if block:
                            block.delete()
                            return JsonResponse({'success': True})
                        return JsonResponse({'error': 'Block not found'}, status=404)
                    return JsonResponse({'error': 'Block ID is required'}, status=400)
                elif data.get('action') == 'convert_to_template':
                    template_name = data.get('template_name')
                    if template_name:
                        try:
                            template = DayTemplate.objects.create(name=template_name, user=request.user)
                        except TypeError:
                            try:
                                template = DayTemplate.objects.create(name=template_name)
                            except TypeError:
                                template = DayTemplate.objects.create()
                        
                        fallback_action = Action.objects.filter(user=request.user).first()
                        if not fallback_action:
                            fallback_action = Action.objects.create(user=request.user, name="Default Action", color="#3B82F6", icon_name="activity")
                        
                        for block in schedule.blocks.all():
                            action_to_use = block.action or fallback_action
                            try:
                                template.template_blocks.create(
                                    action=action_to_use,
                                    title=block.title,
                                    start_time=block.start_time,
                                    end_time=block.end_time,
                                    block_type=block.block_type,
                                    description=block.description
                                )
                            except TypeError:
                                try:
                                    template.template_blocks.create(
                                        action=action_to_use,
                                        title=block.title,
                                        start_time=block.start_time,
                                        end_time=block.end_time,
                                        description=block.description
                                    )
                                except TypeError:
                                    try:
                                        template.template_blocks.create(
                                            action=action_to_use,
                                            title=block.title,
                                            start_time=block.start_time,
                                            end_time=block.end_time,
                                            block_type=block.block_type
                                        )
                                    except TypeError:
                                        template.template_blocks.create(
                                            action=action_to_use,
                                            title=block.title,
                                            start_time=block.start_time,
                                            end_time=block.end_time
                                        )
                        return JsonResponse({'success': True})
                    return JsonResponse({'error': 'Template name is required'}, status=400)
                elif data.get('action') == 'apply_template':
                    template_id = data.get('template_id')
                    if template_id:
                        try:
                            template = DayTemplate.objects.filter(id=template_id, user=request.user).first()
                        except Exception:
                            template = DayTemplate.objects.filter(id=template_id).first()
                        if template:
                            applied = 0
                            skipped = 0
                            
                            fallback_action = Action.objects.filter(user=request.user).first()
                            if not fallback_action:
                                fallback_action = Action.objects.create(user=request.user, name="Default Action", color="#3B82F6", icon_name="activity")
                                
                            for t_block in template.template_blocks.all():
                                # Check for overlap
                                overlap = schedule.blocks.filter(
                                    start_time__lt=t_block.end_time,
                                    end_time__gt=t_block.start_time
                                ).exists()
                                if not overlap:
                                    action_to_use = t_block.action or fallback_action
                                    schedule.blocks.create(
                                        action=action_to_use,
                                        title=t_block.title,
                                        start_time=t_block.start_time,
                                        end_time=t_block.end_time,
                                        block_type=getattr(t_block, 'block_type', 'task'),
                                        description=getattr(t_block, 'description', '')
                                    )
                                    applied += 1
                                else:
                                    skipped += 1
                            return JsonResponse({'success': True, 'applied': applied, 'skipped': skipped})
                        return JsonResponse({'error': 'Template not found'}, status=404)
                    return JsonResponse({'error': 'Template ID is required'}, status=400)
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)

        # Pass the user to the form so it can filter Action choices
        block_id = request.POST.get('block_id')
        instance = None
        if block_id:
            instance = schedule.blocks.filter(id=block_id).first()
            
        form = ScheduleBlockForm(request.POST, user=request.user, instance=instance)
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
    
    try:
        templates = DayTemplate.objects.filter(user=request.user)
    except Exception:
        templates = DayTemplate.objects.all()

    context = {
        'schedule': schedule,
        'form': form,
        'templates': templates,
        'actions': Action.objects.filter(user=request.user),
    }
    return render(request, 'schedule/schedule.html', context)