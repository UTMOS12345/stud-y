import json
from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from .models import DaySchedule, DayTemplate, Action, ScheduleBlock, TemplateBlock
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

                if action_type in ['create_action', 'update_action']:
                    name, color = data.get('name'), data.get('color', '#3B82F6')
                    icon, action_id = data.get('icon_name', 'activity'), data.get('action_id')
                    if not name:
                        return JsonResponse({'error': 'Name required'}, status=400)
                    if action_type == 'update_action' and action_id:
                        Action.objects.filter(id=action_id, user=request.user).update(name=name, color=color, icon_name=icon)
                    else:
                        Action.objects.create(user=request.user, name=name, color=color, icon_name=icon)
                    return JsonResponse({'success': True})

                elif action_type == 'delete_block':
                    schedule.blocks.filter(id=data.get('block_id')).delete()
                    return JsonResponse({'success': True})

                elif action_type == 'delete_template':
                    DayTemplate.objects.filter(id=data.get('template_id'), user=request.user).delete()
                    return JsonResponse({'success': True})

                elif action_type == 'convert_to_template':
                    name = data.get('template_name')
                    if not name:
                        return JsonResponse({'error': 'Name required'}, status=400)
                    schedule.create_template_from_day(name)
                    return JsonResponse({'success': True})

                elif action_type == 'apply_template':
                    template = DayTemplate.objects.filter(id=data.get('template_id'), user=request.user).first()
                    if not template:
                        return JsonResponse({'error': 'Template not found'}, status=404)
                    applied, skipped = template.apply_to_date_merge(selected_date)
                    return JsonResponse({'success': True, 'message': f"Applied {applied} blocks. {skipped} skipped (overlaps)."})

            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)

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


@login_required
def template_detail_view(request, template_id):
    """
    Template editor — mirrors schedule_view 1:1 but operates on TemplateBlocks.
    Renders schedule/template_editor.html (sits alongside schedule.html, NOT in partials).
    """
    template = get_object_or_404(DayTemplate, id=template_id, user=request.user)

    if request.method == 'POST':

        if request.headers.get('Content-Type') == 'application/json':
            try:
                data = json.loads(request.body)
                action_type = data.get('action')

                if action_type == 'delete_template_block':
                    template.template_blocks.filter(id=data.get('block_id')).delete()
                    return JsonResponse({'success': True})

                elif action_type == 'rename_template':
                    name = data.get('name', '').strip()
                    if not name:
                        return JsonResponse({'error': 'Name required'}, status=400)
                    template.name = name
                    template.save(update_fields=['name'])
                    return JsonResponse({'success': True})

                elif action_type in ['create_action', 'update_action']:
                    name      = data.get('name')
                    color     = data.get('color', '#3B82F6')
                    icon      = data.get('icon_name', 'activity')
                    action_id = data.get('action_id')
                    if not name:
                        return JsonResponse({'error': 'Name required'}, status=400)
                    if action_type == 'update_action' and action_id:
                        Action.objects.filter(id=action_id, user=request.user).update(name=name, color=color, icon_name=icon)
                    else:
                        Action.objects.create(user=request.user, name=name, color=color, icon_name=icon)
                    return JsonResponse({'success': True})

            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)

        # Standard form — add/edit TemplateBlock using the same ScheduleBlockForm
        block_id = request.POST.get('block_id')
        instance = template.template_blocks.filter(id=block_id).first() if block_id else None
        form = ScheduleBlockForm(request.POST, user=request.user)

        if form.is_valid():
            cd = form.cleaned_data
            try:
                if instance:
                    instance.title       = cd['title']
                    instance.action      = cd.get('action')
                    instance.start_time  = cd['start_time']
                    instance.end_time    = cd['end_time']
                    instance.description = cd.get('description') or ''
                    instance.block_type  = cd.get('block_type', 'fixed')
                    instance.save()
                else:
                    last_order = (template.template_blocks.order_by('-order').values_list('order', flat=True).first()) or 0
                    TemplateBlock.objects.create(
                        template=template,
                        title=cd['title'],
                        action=cd.get('action'),
                        start_time=cd['start_time'],
                        end_time=cd['end_time'],
                        description=cd.get('description') or '',
                        block_type=cd.get('block_type', 'fixed'),
                        order=last_order + 1,
                    )
                return redirect('template_detail', template_id=template.id)
            except Exception as e:
                form.add_error(None, str(e))
    else:
        form = ScheduleBlockForm(user=request.user)

    context = {
        'template': template,
        'actions': Action.objects.filter(user=request.user),
        'form': form,
    }
    return render(request, 'schedule/partials/template_editor.html', context)