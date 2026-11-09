import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from schedule.models import ACTION_COLORS

from .forms import CardForm, ColumnForm, NewCardForm
from .models import Card, Column

DEFAULT_COLUMNS = ('To do', 'Doing', 'Done')
MAX_COLUMNS = 12


def form_error(form):
    return JsonResponse({'error': next(iter(form.errors.values()))[0]}, status=400)


def card_html(card):
    return render_to_string('includes/kanban_card.html', {'card': card})


def next_position(cards):
    highest = cards.aggregate(highest=Max('position'))['highest']
    return 0 if highest is None else highest + 1


@login_required
def board(request):
    columns = list(Column.objects.filter(user=request.user).prefetch_related('cards'))
    if not columns:
        for position, name in enumerate(DEFAULT_COLUMNS):
            Column.objects.create(user=request.user, name=name, position=position)
        columns = list(Column.objects.filter(user=request.user).prefetch_related('cards'))
    return render(request, 'kanban.html', {'columns': columns, 'colors': ACTION_COLORS})


@login_required
@require_POST
def add_column(request):
    columns = Column.objects.filter(user=request.user)
    if columns.count() >= MAX_COLUMNS:
        return JsonResponse({'error': f'A board can have {MAX_COLUMNS} columns at most'}, status=400)
    form = ColumnForm(request.POST)
    if not form.is_valid():
        return form_error(form)
    column = form.save(commit=False)
    column.user = request.user
    column.position = next_position(columns)
    column.save()
    return JsonResponse({'id': column.id})


@login_required
@require_POST
def rename_column(request, column_id):
    column = get_object_or_404(Column, id=column_id, user=request.user)
    form = ColumnForm(request.POST, instance=column)
    if not form.is_valid():
        return form_error(form)
    form.save()
    return JsonResponse({'id': column.id})


@login_required
@require_POST
def delete_column(request, column_id):
    column = get_object_or_404(Column, id=column_id, user=request.user)
    if Column.objects.filter(user=request.user).count() == 1:
        return JsonResponse({'error': 'A board needs at least one column'}, status=400)
    column.delete()
    return JsonResponse({'success': True})


@login_required
@require_POST
def add_card(request, column_id):
    column = get_object_or_404(Column, id=column_id, user=request.user)
    form = NewCardForm(request.POST)
    if not form.is_valid():
        return form_error(form)
    card = form.save(commit=False)
    card.column = column
    card.position = next_position(column.cards)
    card.save()
    return JsonResponse({'html': card_html(card)}, status=201)


@login_required
@require_POST
def edit_card(request, card_id):
    card = get_object_or_404(Card, id=card_id, column__user=request.user)
    form = CardForm(request.POST, instance=card)
    if not form.is_valid():
        return form_error(form)
    card = form.save(commit=False)

    column_id = request.POST.get('column', '')
    if column_id.isdigit() and int(column_id) != card.column_id:
        card.column = get_object_or_404(Column, id=int(column_id), user=request.user)
        card.position = next_position(card.column.cards)
    card.save()
    return JsonResponse({'html': card_html(card), 'column': card.column_id})


@login_required
@require_POST
def delete_card(request, card_id):
    get_object_or_404(Card, id=card_id, column__user=request.user).delete()
    return JsonResponse({'success': True})


@login_required
@require_POST
def move_card(request):
    """Put a card at a place in a column. Body: {"card": 3, "column": 2, "index": 0}"""
    try:
        data = json.loads(request.body)
        card_id, column_id, index = data['card'], data['column'], data['index']
    except (ValueError, TypeError, KeyError):
        return JsonResponse({'error': 'Send a card, a column and an index'}, status=400)
    if not all(type(value) is int for value in (card_id, column_id, index)):
        return JsonResponse({'error': 'Send a card, a column and an index'}, status=400)

    card = get_object_or_404(Card, id=card_id, column__user=request.user)
    column = get_object_or_404(Column, id=column_id, user=request.user)
    with transaction.atomic():
        cards = list(column.cards.exclude(pk=card.pk))
        cards.insert(max(0, min(index, len(cards))), card)
        card.column = column
        for position, each in enumerate(cards):
            each.position = position
        Card.objects.bulk_update(cards, ['position', 'column'])
    return JsonResponse({'success': True})
