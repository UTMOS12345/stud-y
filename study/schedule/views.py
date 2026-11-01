import json
import datetime
from datetime import date, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from .models import DaySchedule, DayTemplate, Action, ScheduleBlock, TemplateBlock
from .forms import ScheduleBlockForm


# ─── helpers ──────────────────────────────────────────────────────────────────

def _block_minutes(block):
    """Return the duration of a ScheduleBlock or TemplateBlock in minutes."""
    delta = (
        datetime.datetime.combine(datetime.date.min, block.end_time)
        - datetime.datetime.combine(datetime.date.min, block.start_time)
    )
    return int(delta.total_seconds() / 60)


def _week_hours(user, selected_date):
    """
    Return a list of 7 floats (Mon–Sun) representing scheduled hours
    for the week that contains selected_date.
    """
    week_start = selected_date - timedelta(days=selected_date.weekday())
    hours = []
    for i in range(7):
        day = week_start + timedelta(days=i)
        sched = DaySchedule.objects.filter(user=user, date=day).first()
        mins = 0
        if sched:
            for b in sched.blocks.select_related('action').all():
                mins += _block_minutes(b)
        hours.append(round(mins / 60, 1))
    return hours


def _format_duration(minutes):
    """Format duration in minutes to readable string."""
    if minutes <= 0:
        return "0 m."
    h = minutes // 60
    m = minutes % 60
    if h > 0 and m > 0:
        return f"{h} h. {m} m."
    elif h > 0:
        return f"{h} h."
    else:
        return f"{m} m."


def _build_schedule_with_gaps(schedule):
    """
    Return schedule blocks with empty gaps inserted between them.
    Used to visualize idle time in the schedule view.
    """
    blocks = list(schedule.blocks.select_related('action').all())
    
    if not blocks:
        return []
    
    # Sort blocks by start time
    blocks.sort(key=lambda b: b.start_time)
    
    result = []
    
    # Check if there's a gap before the first block
    first_start_mins = blocks[0].start_time.hour * 60 + blocks[0].start_time.minute
    if first_start_mins > 0:
        result.append({
            'is_empty': True,
            'start_time': datetime.time(0, 0),
            'end_time': blocks[0].start_time,
            'title': 'Empty',
            'duration_mins': first_start_mins,
            'duration_formatted': _format_duration(first_start_mins),
        })
    
    # Add blocks and gaps between them
    for i, block in enumerate(blocks):
        block_mins = _block_minutes(block)
        result.append({
            'is_empty': False,
            'block': block,
            'start_time': block.start_time,
            'end_time': block.end_time,
            'title': block.title,
            'duration_mins': block_mins,
            'duration_formatted': _format_duration(block_mins),
        })
        
        # Check for gap to next block
        if i < len(blocks) - 1:
            next_block = blocks[i + 1]
            gap_mins = (
                (next_block.start_time.hour * 60 + next_block.start_time.minute) -
                (block.end_time.hour * 60 + block.end_time.minute)
            )
            if gap_mins > 0:
                result.append({
                    'is_empty': True,
                    'start_time': block.end_time,
                    'end_time': next_block.start_time,
                    'title': 'Empty',
                    'duration_mins': gap_mins,
                    'duration_formatted': _format_duration(gap_mins),
                })
    
    # Check if there's a gap after the last block
    last_end_mins = blocks[-1].end_time.hour * 60 + blocks[-1].end_time.minute
    if last_end_mins < 1440:  # 24 * 60
        remaining_mins = 1440 - last_end_mins
        result.append({
            'is_empty': True,
            'start_time': blocks[-1].end_time,
            'end_time': datetime.time(23, 59),
            'title': 'Empty',
            'duration_mins': remaining_mins,
            'duration_formatted': _format_duration(remaining_mins),
        })
    
    return result


# ─── schedule view ─────────────────────────────────────────────────────────────

@login_required
def schedule_view(request):
    date_str = request.GET.get('date')
    try:
        selected_date = date.fromisoformat(date_str) if date_str else date.today()
    except (ValueError, TypeError):
        selected_date = date.today()

    schedule, _ = DaySchedule.objects.get_or_create(user=request.user, date=selected_date)

    # ── POST ──────────────────────────────────────────────────────────────────
    if request.method == 'POST':

        # JSON actions (called by JS fetch)
        if request.headers.get('Content-Type') == 'application/json':
            try:
                data        = json.loads(request.body)
                action_type = data.get('action')

                if action_type in ('create_action', 'update_action'):
                    name      = data.get('name', '').strip()
                    color     = data.get('color', '#3B82F6')
                    icon      = data.get('icon_name', 'activity')
                    action_id = data.get('action_id')
                    if not name:
                        return JsonResponse({'error': 'Name required'}, status=400)
                    if action_type == 'update_action' and action_id:
                        Action.objects.filter(id=action_id, user=request.user).update(
                            name=name, color=color, icon_name=icon
                        )
                    else:
                        Action.objects.create(
                            user=request.user, name=name, color=color, icon_name=icon
                        )
                    return JsonResponse({'success': True})

                elif action_type == 'delete_block':
                    schedule.blocks.filter(id=data.get('block_id')).delete()
                    return JsonResponse({'success': True})

                elif action_type == 'delete_template':
                    DayTemplate.objects.filter(
                        id=data.get('template_id'), user=request.user
                    ).delete()
                    return JsonResponse({'success': True})

                elif action_type == 'convert_to_template':
                    name = data.get('template_name', '').strip()
                    if not name:
                        return JsonResponse({'error': 'Name required'}, status=400)
                    schedule.create_template_from_day(name)
                    return JsonResponse({'success': True})

                elif action_type == 'apply_template':
                    template = DayTemplate.objects.filter(
                        id=data.get('template_id'), user=request.user
                    ).first()
                    if not template:
                        return JsonResponse({'error': 'Template not found'}, status=404)
                    applied, skipped = template.apply_to_date_merge(selected_date)
                    return JsonResponse({
                        'success': True,
                        'message': f"Applied {applied} blocks. {skipped} skipped (overlaps)."
                    })

            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)

        # Standard form submission (add / edit block)
        block_id = request.POST.get('block_id')
        instance = schedule.blocks.filter(id=block_id).first() if block_id else None
        form = ScheduleBlockForm(request.POST, user=request.user, instance=instance)
        if form.is_valid():
            new_block          = form.save(commit=False)
            new_block.schedule = schedule
            try:
                new_block.save()
                return redirect(f"{request.path}?date={selected_date.isoformat()}")
            except Exception as e:
                form.add_error(None, str(e))

    # ── GET ───────────────────────────────────────────────────────────────────
    else:
        form = ScheduleBlockForm(user=request.user)

    # Serialize blocks to JSON for the statistics template
    blocks_data = []
    for b in schedule.blocks.select_related('action').all():
        blocks_data.append({
            'action':    b.action.name  if b.action else '',
            'color':     b.action.color if b.action else '#3B82F6',
            'icon':      b.action.icon_name if b.action else 'activity',
            'startMins': b.start_time.hour * 60 + b.start_time.minute,
            'endMins':   b.end_time.hour   * 60 + b.end_time.minute,
            'title':     b.title,
            'blockType': b.block_type,
        })

    # Build schedule with gaps for display
    schedule_with_gaps = _build_schedule_with_gaps(schedule)

    context = {
        'schedule':      schedule,
        'schedule_with_gaps': schedule_with_gaps,
        'form':          form,
        'templates':     DayTemplate.objects.filter(user=request.user),
        'actions':       Action.objects.filter(user=request.user),
        'selected_date': selected_date,
        'week_hours':    _week_hours(request.user, selected_date),
        'blocks_json':   json.dumps(blocks_data),
    }
    return render(request, 'schedule/schedule.html', context)


# ─── template detail view ──────────────────────────────────────────────────────

@login_required
def template_detail_view(request, template_id):
    """
    Template editor — mirrors schedule_view but operates on TemplateBlocks.
    Renders schedule/partials/template_editor.html.
    """
    template = get_object_or_404(DayTemplate, id=template_id, user=request.user)

    # ── POST ──────────────────────────────────────────────────────────────────
    if request.method == 'POST':

        if request.headers.get('Content-Type') == 'application/json':
            try:
                data        = json.loads(request.body)
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

                elif action_type in ('create_action', 'update_action'):
                    name      = data.get('name', '').strip()
                    color     = data.get('color', '#3B82F6')
                    icon      = data.get('icon_name', 'activity')
                    action_id = data.get('action_id')
                    if not name:
                        return JsonResponse({'error': 'Name required'}, status=400)
                    if action_type == 'update_action' and action_id:
                        Action.objects.filter(id=action_id, user=request.user).update(
                            name=name, color=color, icon_name=icon
                        )
                    else:
                        Action.objects.create(
                            user=request.user, name=name, color=color, icon_name=icon
                        )
                    return JsonResponse({'success': True})

            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)

        # Standard form — add / edit TemplateBlock
        block_id = request.POST.get('block_id')
        instance = template.template_blocks.filter(id=block_id).first() if block_id else None
        form     = ScheduleBlockForm(request.POST, user=request.user)

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
                    last_order = (
                        template.template_blocks
                        .order_by('-order')
                        .values_list('order', flat=True)
                        .first()
                    ) or 0
                    TemplateBlock.objects.create(
                        template    = template,
                        title       = cd['title'],
                        action      = cd.get('action'),
                        start_time  = cd['start_time'],
                        end_time    = cd['end_time'],
                        description = cd.get('description') or '',
                        block_type  = cd.get('block_type', 'fixed'),
                        order       = last_order + 1,
                    )
                return redirect('template_detail', template_id=template.id)
            except Exception as e:
                form.add_error(None, str(e))

    # ── GET ───────────────────────────────────────────────────────────────────
    else:
        form = ScheduleBlockForm(user=request.user)

    context = {
        'template': template,
        'actions':  Action.objects.filter(user=request.user),
        'form':     form,
    }
    return render(request, 'schedule/partials/template_editor.html', context)