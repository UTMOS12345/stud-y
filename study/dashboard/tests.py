import datetime
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from schedule.models import Action, BlockSession, DaySchedule, ScheduleBlock

T = datetime.time
# 10:30 in Tashkent (UTC+5), the app's default time zone
NOW = datetime.datetime(2026, 1, 5, 5, 30, tzinfo=datetime.timezone.utc)
TODAY = datetime.date(2026, 1, 5)


class DashboardTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='t', email='t@t.com', password='pw12345!x')
        self.action = Action.objects.create(user=self.user, name='Math', color='#3B82F6')
        self.client.force_login(self.user)

    def add_block(self, start, end, title='Block', date=TODAY):
        schedule, _ = DaySchedule.objects.get_or_create(user=self.user, date=date)
        return ScheduleBlock.objects.create(schedule=schedule, action=self.action, title=title,
                                            start_time=start, end_time=end)

    def get(self):
        with mock.patch('django.utils.timezone.now', return_value=NOW):
            return self.client.get(reverse('dashboard'))


class TodayTests(DashboardTestCase):
    def test_now_and_next(self):
        self.add_block(T(8), T(9), 'Done')
        running = self.add_block(T(10), T(11), 'Running')
        self.add_block(T(14), T(15), 'Later')
        self.add_block(T(12), T(13), 'Next')
        BlockSession.objects.create(user=self.user, block=running, start_time=NOW, end_time=NOW,
                                    focused_seconds=1500)

        context = self.get().context
        self.assertEqual(context['current'].title, 'Running')
        self.assertEqual((context['current'].minutes_left, context['current'].progress), (30, 50))
        self.assertEqual((context['upcoming'].title, context['upcoming'].starts_in), ('Next', '1h 30m'))
        self.assertEqual([b.title for b in context['blocks']], ['Done', 'Running', 'Next', 'Later'])
        self.assertEqual(context['blocks'][1].focused, '25m')
        self.assertTrue(context['blocks'][0].is_done)

    def test_free_time_and_nothing_next(self):
        self.add_block(T(8), T(9))
        context = self.get().context
        self.assertIsNone(context['current'])
        self.assertIsNone(context['upcoming'])

    def test_empty_day(self):
        response = self.get()
        self.assertContains(response, 'Plan your day')
        self.assertNotContains(response, 'coming soon')

    def test_only_your_blocks(self):
        other = User.objects.create_user(username='o', email='o@o.com', password='pw12345!x')
        schedule = DaySchedule.objects.create(user=other, date=TODAY)
        ScheduleBlock.objects.create(schedule=schedule, title='Theirs', start_time=T(10), end_time=T(11))
        self.assertEqual(self.get().context['blocks'], [])


class NumbersTests(DashboardTestCase):
    def test_today_and_week_numbers(self):
        block = self.add_block(T(9), T(11))                                  # Monday Jan 5, 2h
        self.add_block(T(9), T(11), date=datetime.date(2026, 1, 7))          # Wednesday, 2h
        self.add_block(T(9), T(11), date=datetime.date(2026, 1, 12))         # next week
        for seconds in (1500, 1500):
            BlockSession.objects.create(user=self.user, block=block, start_time=NOW, end_time=NOW,
                                        focused_seconds=seconds)
        context = self.get().context
        self.assertEqual((context['day']['focused'], context['day']['sessions'], context['day']['done_percent']),
                         ('50m', 2, 42))
        self.assertEqual((context['week_planned'], context['week_focused'], context['week_percent']), (4.0, 0.8, 20))

    def test_new_user_numbers(self):
        context = self.get().context
        self.assertEqual((context['day']['focused'], context['week_percent']), ('0m', None))
