import calendar
import datetime
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from schedule.models import ACTION_COLORS, next_palette_color
from schedule.stats import current_streak

from .forms import HabitEditForm, HabitForm
from .models import Habit, HabitEntry

WEEKDAY_LETTERS = 'MTWTFSS'
HISTORY_DAYS = 400  # how far back a streak is followed


def month_from(text, today):
    """First day of the month in `text` (YYYY-MM), or of this month if it makes no sense."""
    try:
        month = datetime.datetime.strptime(text or '', '%Y-%m').date()
    except ValueError:
        return today.replace(day=1)
    return month if 2000 <= month.year <= 2100 else today.replace(day=1)


def month_score(habit, values, first, last, today):
    """Average fill over the days of the month so far, counted from when the habit began."""
    end = min(last, today)
    in_month = [d for d in values if first <= d <= end]
    began = min([timezone.localtime(habit.created_at).date()] + in_month)
    start = max(first, began)
    days = (end - start).days + 1
    if days <= 0:
        return None
    return round(sum(values[d] for d in in_month) / days)


def month_grid(user, first, today):
    """Everything the calendar needs for one month. Two queries, however many habits."""
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    days = [first + datetime.timedelta(days=n) for n in range(last.day)]

    habits = list(Habit.objects.filter(user=user))
    values = {habit.id: {} for habit in habits}
    since = min(first, today - datetime.timedelta(days=HISTORY_DAYS))
    for habit_id, date, value in HabitEntry.objects.filter(
        habit__user=user, date__gte=since,
    ).values_list('habit_id', 'date', 'value'):
        values[habit_id][date] = value

    rows = []
    for habit in habits:
        mine = values[habit.id]
        rows.append({
            'habit': habit,
            'score': month_score(habit, mine, first, last, today),
            'streak': current_streak(set(mine), today),
            'cells': [{
                'date': day,
                'value': mine.get(day, 0),
                'is_future': day > today,
                'is_today': day == today,
            } for day in days],
        })

    scores = [row['score'] for row in rows if row['score'] is not None]
    summary = {
        'total': len(rows),
        'done_today': sum(1 for habit in habits if values[habit.id].get(today) == 100),
        'month_average': round(sum(scores) / len(scores)) if scores else None,
        'best_streak': max([row['streak'] for row in rows] + [0]),
    }
    return {
        'rows': rows,
        'summary': summary,
        'days': [{
            'date': day,
            'number': day.day,
            'letter': WEEKDAY_LETTERS[day.weekday()],
            'is_today': day == today,
            'is_weekend': day.weekday() >= 5,
        } for day in days],
    }


@login_required
def habits_page(request):
    if request.method == 'POST':
        return save_habit(HabitForm(request.POST, user=request.user), request.user)

    today = timezone.localdate()
    first = month_from(request.GET.get('month'), today)
    grid = month_grid(request.user, first, today)
    previous = (first - datetime.timedelta(days=1)).replace(day=1)
    following = (first + datetime.timedelta(days=32)).replace(day=1)
    return render(request, 'habits.html', {
        **grid,
        'month': first,
        'previous_month': previous.strftime('%Y-%m'),
        'next_month': following.strftime('%Y-%m'),
        'is_this_month': first == today.replace(day=1),
        'kinds': Habit.Kind.choices,
        'colors': ACTION_COLORS,
        'next_color': next_palette_color([row['habit'].color for row in grid['rows']]),
    })


def save_habit(form, user):
    if not form.is_valid():
        first_error = next(iter(form.errors.values()))[0]
        return JsonResponse({'error': first_error}, status=400)
    habit = form.save(commit=False)
    habit.user = user
    habit.save()
    return JsonResponse({'id': habit.id})


@login_required
@require_POST
def edit_habit(request, habit_id):
    habit = get_object_or_404(Habit, id=habit_id, user=request.user)
    return save_habit(HabitEditForm(request.POST, instance=habit, user=request.user), request.user)


@login_required
@require_POST
def delete_habit(request, habit_id):
    get_object_or_404(Habit, id=habit_id, user=request.user).delete()
    return JsonResponse({'success': True})


@login_required
@require_POST
def set_entry(request, habit_id):
    """Set how full one day's box is. Body: {"date": "2026-11-08", "value": 50}; value 0 empties it."""
    habit = get_object_or_404(Habit, id=habit_id, user=request.user)
    try:
        data = json.loads(request.body)
        date = datetime.date.fromisoformat(data['date'])
        value = data['value']
    except (ValueError, TypeError, KeyError):
        return JsonResponse({'error': 'Send a date and a value'}, status=400)

    if isinstance(value, bool) or not isinstance(value, int) or not habit.accepts(value):
        return JsonResponse({'error': 'That value does not fit this habit'}, status=400)
    today = timezone.localdate()
    if date > today:
        return JsonResponse({'error': "You can't fill in a day that hasn't happened yet"}, status=400)

    if value == 0:
        HabitEntry.objects.filter(habit=habit, date=date).delete()
    else:
        HabitEntry.objects.update_or_create(habit=habit, date=date, defaults={'value': value})

    grid = month_grid(request.user, date.replace(day=1), today)
    row = next(r for r in grid['rows'] if r['habit'].id == habit.id)
    return JsonResponse({'value': value, 'score': row['score'], 'streak': row['streak'], 'summary': grid['summary']})
