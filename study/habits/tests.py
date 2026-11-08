import datetime
import json
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .models import Habit, HabitEntry

# 10:30 on Jan 15 in Tashkent, the default time zone
NOW = datetime.datetime(2026, 1, 15, 5, 30, tzinfo=datetime.timezone.utc)
D = lambda day, month=1: datetime.date(2026, month, day)


class HabitTestCase(TestCase):
    def setUp(self):
        patcher = mock.patch('django.utils.timezone.now', return_value=NOW)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = User.objects.create_user(username='t', email='t@t.com', password='pw12345!x')
        self.client.force_login(self.user)
        self.url = reverse('habits')

    def habit(self, kind='check', name='Read', user=None):
        return Habit.objects.create(user=user or self.user, name=name, kind=kind, color='#10B981')

    def entry(self, habit, date, value):
        return self.client.post(reverse('habit_entry', args=[habit.id]),
                                json.dumps({'date': date, 'value': value}), content_type='application/json')

    def row(self, response, habit):
        return next(r for r in response.context['rows'] if r['habit'] == habit)


class EntryTests(HabitTestCase):
    def test_check_fills_and_empties(self):
        habit = self.habit()
        self.assertEqual(self.entry(habit, '2026-01-10', 100).status_code, 200)
        self.assertEqual(HabitEntry.objects.get().value, 100)
        self.assertEqual(self.entry(habit, '2026-01-10', 100).status_code, 200)
        self.assertEqual(HabitEntry.objects.count(), 1)
        self.entry(habit, '2026-01-10', 0)
        self.assertFalse(HabitEntry.objects.exists())

    def test_each_kind_only_takes_its_values(self):
        cases = {'check': ([100, 0], [50, 1, 101]), 'three': ([50, 100, 0], [25, 75]), 'percent': ([1, 37, 100, 0], [101, -1])}
        for kind, (good, bad) in cases.items():
            habit = self.habit(kind, name=kind)
            for value in good:
                self.assertEqual(self.entry(habit, '2026-01-10', value).status_code, 200, (kind, value))
            for value in bad:
                self.assertEqual(self.entry(habit, '2026-01-10', value).status_code, 400, (kind, value))

    def test_nonsense_is_rejected(self):
        habit = self.habit('percent')
        for value in ['50', 12.5, True, None, [1]]:
            self.assertEqual(self.entry(habit, '2026-01-10', value).status_code, 400, value)
        self.assertEqual(self.entry(habit, 'soon', 50).status_code, 400)
        response = self.client.post(reverse('habit_entry', args=[habit.id]), '[]', content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(HabitEntry.objects.exists())

    def test_future_days_are_refused(self):
        self.assertEqual(self.entry(self.habit(), '2026-01-16', 100).status_code, 400)
        self.assertEqual(self.entry(self.habit(name='b'), '2026-01-15', 100).status_code, 200)

    def test_someone_elses_habit(self):
        other = User.objects.create_user(username='o', email='o@o.com', password='pw12345!x')
        theirs = self.habit(user=other)
        self.assertEqual(self.entry(theirs, '2026-01-10', 100).status_code, 404)
        self.assertEqual(self.client.post(reverse('habit_delete', args=[theirs.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse('habit_edit', args=[theirs.id]), {'name': 'x', 'color': '#000000'}).status_code, 404)

    def test_needs_post_and_login(self):
        habit = self.habit()
        self.assertEqual(self.client.get(reverse('habit_entry', args=[habit.id])).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_response_has_fresh_numbers(self):
        habit = self.habit()
        self.entry(habit, '2026-01-14', 100)
        data = self.entry(habit, '2026-01-15', 100).json()
        self.assertEqual((data['streak'], data['summary']['done_today'], data['summary']['total']), (2, 1, 1))


class CalendarTests(HabitTestCase):
    def test_month_has_every_day_and_marks_today(self):
        habit = self.habit()
        response = self.client.get(self.url)
        self.assertEqual(len(response.context['days']), 31)
        cells = self.row(response, habit)['cells']
        self.assertEqual(len(cells), 31)
        self.assertTrue(cells[14]['is_today'])
        self.assertTrue(cells[15]['is_future'])
        self.assertFalse(cells[14]['is_future'])

    def test_month_navigation(self):
        response = self.client.get(self.url, {'month': '2026-02'})
        self.assertEqual(len(response.context['days']), 28)
        self.assertEqual((response.context['previous_month'], response.context['next_month']), ('2026-01', '2026-03'))
        response = self.client.get(self.url, {'month': '2025-12'})
        self.assertEqual(response.context['next_month'], '2026-01')

    def test_bad_month_falls_back_to_this_one(self):
        for bad in ['nope', '2026-13', '9999-01']:
            self.assertEqual(self.client.get(self.url, {'month': bad}).context['month'], D(1), bad)

    def test_score_counts_from_when_the_habit_began(self):
        habit = self.habit('three')          # created today, Jan 15
        self.entry(habit, '2026-01-15', 50)
        self.assertEqual(self.row(self.client.get(self.url), habit)['score'], 50)
        # filling an earlier day moves the start back: 11, 12, 13, 14, 15 are 5 days, (100 + 50) / 5
        self.entry(habit, '2026-01-11', 100)
        self.assertEqual(self.row(self.client.get(self.url), habit)['score'], 30)

    def test_future_month_has_no_score(self):
        habit = self.habit()
        self.assertIsNone(self.row(self.client.get(self.url, {'month': '2026-03'}), habit)['score'])

    def test_streak_and_summary(self):
        read, run = self.habit(), self.habit('percent', name='Run')
        for day in ['2026-01-13', '2026-01-14', '2026-01-15']:
            self.entry(read, day, 100)
        self.entry(run, '2026-01-15', 40)
        response = self.client.get(self.url)
        self.assertEqual(self.row(response, read)['streak'], 3)
        summary = response.context['summary']
        self.assertEqual((summary['done_today'], summary['total'], summary['best_streak']), (1, 2, 3))

    def test_query_count_does_not_grow_with_habits(self):
        for n in range(6):
            self.entry(self.habit(name=f'h{n}'), '2026-01-10', 100)
        with self.assertNumQueries(5):  # session, user, profile, habits, entries
            self.client.get(self.url)

    def test_only_your_habits(self):
        other = User.objects.create_user(username='o', email='o@o.com', password='pw12345!x')
        self.habit(user=other, name='Theirs')
        self.assertNotContains(self.client.get(self.url), 'Theirs')

    def test_empty_page_invites_you_to_start(self):
        self.assertContains(self.client.get(self.url), 'first habit')

    def test_sidebar_links_here(self):
        self.assertContains(self.client.get(reverse('dashboard')), f'href="{self.url}"')


class HabitFormTests(HabitTestCase):
    def create(self, **extra):
        data = {'name': 'Read', 'description': '20 pages', 'kind': 'percent', 'color': '#EF4444'}
        data.update(extra)
        return self.client.post(self.url, data)

    def test_create(self):
        self.assertEqual(self.create().status_code, 200)
        habit = Habit.objects.get()
        self.assertEqual((habit.user, habit.name, habit.description, habit.kind, habit.color),
                         (self.user, 'Read', '20 pages', 'percent', '#EF4444'))

    def test_bad_input(self):
        for extra in [{'name': ''}, {'kind': 'emoji'}, {'color': 'red;'}, {'color': ''}]:
            self.assertEqual(self.create(**extra).status_code, 400, extra)
        self.assertFalse(Habit.objects.exists())

    def test_duplicate_name(self):
        self.create()
        response = self.create(name='read')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], "You already have a habit called 'read'")

    def test_new_habit_form_suggests_an_unused_color(self):
        self.create(color='#3B82F6')
        self.assertEqual(self.client.get(self.url).context['next_color'], '#10B981')

    def test_edit_keeps_the_kind(self):
        habit = self.habit('percent')
        url = reverse('habit_edit', args=[habit.id])
        self.assertEqual(self.client.post(url, {'name': 'Walk', 'description': 'x', 'color': '#123456', 'kind': 'check'}).status_code, 200)
        habit.refresh_from_db()
        self.assertEqual((habit.name, habit.kind, habit.color), ('Walk', 'percent', '#123456'))

    def test_edit_can_keep_its_own_name(self):
        habit = self.habit()
        self.assertEqual(self.client.post(reverse('habit_edit', args=[habit.id]), {'name': 'Read', 'color': '#123456'}).status_code, 200)

    def test_delete_removes_entries(self):
        habit = self.habit()
        self.entry(habit, '2026-01-10', 100)
        self.assertEqual(self.client.post(reverse('habit_delete', args=[habit.id])).status_code, 200)
        self.assertFalse(HabitEntry.objects.exists())
