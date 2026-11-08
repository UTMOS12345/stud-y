import json
import logging
import datetime
from datetime import date, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import transaction, IntegrityError
from django.db.models import Sum
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import DaySchedule, DayTemplate, Action, ScheduleBlock, TemplateBlock
from .forms import ScheduleBlockForm
from .stats import block_stats, carried_over_block, recent_focus, records, summary, week_stats, week_blocks

logger = logging.getLogger(__name__)


# ─── helpers ──────────────────────────────────────────────────────────────────

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


def _build_schedule_with_gaps(blocks, carried_over=None):
    """
    Return schedule blocks with empty gaps inserted between them.
    Used to visualize idle time in the schedule view.
    carried_over is a block from the evening before that runs into this day.
    """
    if not blocks and not carried_over:
        return []

    blocks = sorted(blocks, key=lambda b: b.start_time)
    result = []
    cursor, cursor_time = 0, datetime.time(0, 0)

    def add_gap(until, until_time):
        if until > cursor:
            result.append({
                'is_empty': True,
                'start_time': cursor_time,
                'end_time': until_time,
                'title': 'Empty',
                'duration_mins': until - cursor,
                'duration_formatted': _format_duration(until - cursor),
                'height': min(110, 56 + (until - cursor) * 2 // 3),
            })

    if carried_over:
        cursor = carried_over.end_minutes - 24 * 60
        cursor_time = carried_over.end_time
        result.append({
            'is_empty': False,
            'is_carried_over': True,
            'block': carried_over,
            'start_time': datetime.time(0, 0),
            'end_time': carried_over.end_time,
            'title': carried_over.title,
            'duration_mins': cursor,
            'duration_formatted': _format_duration(cursor),
        })

    for block in blocks:
        add_gap(block.start_minutes, block.start_time)
        result.append({
            'is_empty': False,
            'block': block,
            'start_time': block.start_time,
            'end_time': block.end_time,
            'title': block.title,
            'duration_mins': block.duration_minutes,
            'duration_formatted': _format_duration(block.duration_minutes),
        })
        cursor, cursor_time = block.end_minutes, block.end_time

    # The day is shown as ending at 23:59, so count the last gap up to 23:59 too
    add_gap(23 * 60 + 59, datetime.time(23, 59))
    return result


def _save_action(user, action_type, data):
    """Create or update an Action from the JSON sent by the schedule / template pages."""
    name      = data.get('name', '').strip()
    color     = data.get('color') or Action.next_color(user)
    icon      = data.get('icon_name', 'activity')
    action_id = data.get('action_id')
    if not name:
        return JsonResponse({'error': 'Name required'}, status=400)
    try:
        with transaction.atomic():
            if action_type == 'update_action' and action_id:
                Action.objects.filter(id=action_id, user=user).update(
                    name=name, color=color, icon_name=icon
                )
            else:
                Action.objects.create(user=user, name=name, color=color, icon_name=icon)
    except IntegrityError:
        return JsonResponse({'error': f"You already have an action called '{name}'"}, status=400)
    return JsonResponse({'success': True})


MAX_APPLY_DAYS = 92


def _apply_template_range(user, data):
    """Apply a template to every chosen weekday between two dates (both included)."""
    template = DayTemplate.objects.filter(id=data.get('template_id'), user=user).first()
    if not template:
        return JsonResponse({'error': 'Template not found'}, status=404)
    if not template.template_blocks.exists():
        return JsonResponse({'error': 'This template has no blocks yet'}, status=400)

    try:
        first = date.fromisoformat(data.get('start'))
        last = date.fromisoformat(data.get('end'))
        weekdays = {int(d) for d in data.get('weekdays')}
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Pick a date range and at least one weekday'}, status=400)
    if last < first or not weekdays or not weekdays <= set(range(7)):
        return JsonResponse({'error': 'Pick a date range and at least one weekday'}, status=400)
    if (last - first).days >= MAX_APPLY_DAYS:
        return JsonResponse({'error': f'Pick at most {MAX_APPLY_DAYS} days at a time'}, status=400)

    days = [first + timedelta(days=n) for n in range((last - first).days + 1)]
    days = [d for d in days if d.weekday() in weekdays]
    if not days:
        return JsonResponse({'error': 'None of those weekdays fall inside the range'}, status=400)

    applied = skipped = 0
    with transaction.atomic():
        for day in days:
            added, passed = template.apply_to_date_merge(day)
            applied += added
            skipped += passed
    return JsonResponse({
        'success': True,
        'days': len(days),
        'applied': applied,
        'skipped': skipped,
        'message': f"Applied to {len(days)} day{'s' if len(days) != 1 else ''}: "
                   f"{applied} blocks added, {skipped} skipped (overlaps).",
    })


def _delete_action(user, data):
    """Delete an Action. Blocks that used it are kept and just lose their action."""
    action = Action.objects.filter(id=data.get('action_id'), user=user).first()
    if not action:
        return JsonResponse({'error': 'Action not found'}, status=404)
    with transaction.atomic():
        ScheduleBlock.objects.filter(action=action).update(action=None)
        TemplateBlock.objects.filter(action=action).update(action=None)
        action.delete()
    return JsonResponse({'success': True})


def _error_text(e):
    """Readable text for a ValidationError, without the ['...'] list formatting."""
    if isinstance(e, ValidationError):
        return " ".join(e.messages)
    return "Something went wrong, please try again."


def _json_error(e):
    if isinstance(e, json.JSONDecodeError):
        return JsonResponse({'error': 'Bad request'}, status=400)
    if isinstance(e, ValidationError):
        return JsonResponse({'error': _error_text(e)}, status=400)
    logger.exception("Schedule request failed")
    return JsonResponse({'error': _error_text(e)}, status=500)


# ─── schedule view ─────────────────────────────────────────────────────────────

@login_required
def schedule_view(request):
    date_str = request.GET.get('date')
    try:
        selected_date = date.fromisoformat(date_str) if date_str else timezone.localdate()
    except (ValueError, TypeError):
        selected_date = timezone.localdate()

    # Only look the day up here. A row is created when the first block is added,
    # so just browsing dates doesn't fill the table with empty days.
    schedule = DaySchedule.objects.filter(user=request.user, date=selected_date).first()

    # ── POST ──────────────────────────────────────────────────────────────────
    if request.method == 'POST':

        # JSON actions (called by JS fetch)
        if request.headers.get('Content-Type') == 'application/json':
            try:
                data        = json.loads(request.body)
                action_type = data.get('action')

                if action_type in ('create_action', 'update_action'):
                    return _save_action(request.user, action_type, data)

                elif action_type == 'delete_action':
                    return _delete_action(request.user, data)

                elif action_type == 'delete_block':
                    if schedule:
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
                    if not schedule or not schedule.blocks.exists():
                        return JsonResponse({'error': 'This day has no blocks to save'}, status=400)
                    schedule.create_template_from_day(name)
                    return JsonResponse({'success': True})

                elif action_type == 'apply_template_range':
                    return _apply_template_range(request.user, data)

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

                return JsonResponse({'error': 'Unknown action'}, status=400)

            except Exception as e:
                return _json_error(e)

        # Standard form submission (add / edit block)
        block_id = request.POST.get('block_id')
        instance = schedule.blocks.filter(id=block_id).first() if (block_id and schedule) else None
        form = ScheduleBlockForm(request.POST, user=request.user, instance=instance)
        if form.is_valid():
            new_block = form.save(commit=False)
            try:
                with transaction.atomic():
                    if schedule is None:
                        schedule = DaySchedule.objects.create(user=request.user, date=selected_date)
                    new_block.schedule = schedule
                    new_block.save()
                return redirect(f"{request.path}?date={selected_date.isoformat()}")
            except Exception as e:
                if not isinstance(e, ValidationError):
                    logger.exception("Could not save block")
                form.add_error(None, _error_text(e))

    # ── GET ───────────────────────────────────────────────────────────────────
    else:
        form = ScheduleBlockForm(user=request.user)

    # Load the blocks once and reuse them for the list, gaps and statistics
    # (with the focus time from Pomodoro sessions, in the same query)
    blocks = list(
        schedule.blocks.select_related('action').annotate(focused_seconds=Sum('sessions__focused_seconds'))
    ) if schedule else []
    for b in blocks:
        b.focused_seconds = b.focused_seconds or 0
        b.focused_minutes = b.focused_seconds // 60
    if schedule is None:
        schedule = DaySchedule(user=request.user, date=selected_date)  # not saved, used for the date only

    # Serialize blocks to JSON for the statistics template
    blocks_data = []
    for b in blocks:
        blocks_data.append({
            'action':    b.action.name  if b.action else '',
            'color':     b.action.color if b.action else '#3B82F6',
            'icon':      b.action.icon_name if b.action else 'activity',
            'startMins': b.start_time.hour * 60 + b.start_time.minute,
            'endMins':   b.end_minutes,
            'title':     b.title,
            'blockType': b.block_type,
            'focusedSecs': b.focused_seconds,
        })

    # Build schedule with gaps for display
    carried_over = carried_over_block(request.user, selected_date)
    schedule_with_gaps = _build_schedule_with_gaps(blocks, carried_over)
    if carried_over:
        # the morning part fills that time in the full-day chart
        blocks_data.append({
            'action': carried_over.action.name if carried_over.action else '',
            'color': carried_over.action.color if carried_over.action else '#3B82F6',
            'icon': carried_over.action.icon_name if carried_over.action else 'activity',
            'startMins': 0,
            'endMins': carried_over.end_minutes - 24 * 60,
            'title': carried_over.title,
            'blockType': carried_over.block_type,
            'focusedSecs': 0,
        })

    actions = list(Action.objects.filter(user=request.user))
    week = week_stats(request.user, selected_date)
    day_rows = block_stats(request.user, selected_date)

    context = {
        'schedule':      schedule,
        'blocks':        blocks,
        'schedule_with_gaps': schedule_with_gaps,
        'form':          form,
        'templates':     DayTemplate.objects.filter(user=request.user),
        'actions':       actions,
        'next_action_color': Action.next_color(request.user, [a.color for a in actions]),
        'selected_date': selected_date,
        'week':          week,
        'block_stats_json': json.dumps(day_rows),
        'day_summary':   summary(day_rows, len(blocks)),
        'week_blocks': week_blocks(request.user, selected_date),
        'records':       records(request.user),
        'recent':        recent_focus(request.user, selected_date),
        'week_json':     json.dumps([{'label': d['label'], 'planned': d['planned_hours'],
                                      'focused': d['focused_hours']} for d in week]),
        'blocks_json':   json.dumps(blocks_data),
    }
    return render(request, 'schedule/schedule.html', context)


@login_required
def upcoming_blocks(request):
    """Blocks starting within the next 24 hours, for the reminders."""
    now = timezone.now()
    today = timezone.localdate()
    blocks = ScheduleBlock.objects.filter(
        schedule__user=request.user,
        schedule__date__range=(today, today + timedelta(days=1)),
    ).select_related('schedule')

    upcoming = []
    for block in blocks:
        starts = timezone.make_aware(datetime.datetime.combine(block.schedule.date, block.start_time))
        if now < starts <= now + timedelta(hours=24):
            upcoming.append({'id': block.id, 'title': block.title, 'starts_at': int(starts.timestamp() * 1000)})
    return JsonResponse({'blocks': upcoming})


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
                    return _save_action(request.user, action_type, data)

                elif action_type == 'delete_action':
                    return _delete_action(request.user, data)

                return JsonResponse({'error': 'Unknown action'}, status=400)

            except Exception as e:
                return _json_error(e)

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
                    instance.ends_next_day = cd.get('ends_next_day', False)
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
                        ends_next_day = cd.get('ends_next_day', False),
                        description = cd.get('description') or '',
                        block_type  = cd.get('block_type', 'fixed'),
                        order       = last_order + 1,
                    )
                return redirect('template_detail', template_id=template.id)
            except Exception as e:
                if not isinstance(e, ValidationError):
                    logger.exception("Could not save block")
                form.add_error(None, _error_text(e))

    # ── GET ───────────────────────────────────────────────────────────────────
    else:
        form = ScheduleBlockForm(user=request.user)

    context = {
        'template': template,
        'actions':  Action.objects.filter(user=request.user),
        'next_action_color': Action.next_color(request.user),
        'form':     form,
    }
    return render(request, 'schedule/partials/template_editor.html', context)