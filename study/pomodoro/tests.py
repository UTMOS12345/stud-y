import datetime
import json

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from schedule.models import Action, BlockSession, DaySchedule, ScheduleBlock


def make_block(user, start=datetime.time(9), end=datetime.time(10)):
    schedule, _ = DaySchedule.objects.get_or_create(user=user, date=datetime.date(2026, 1, 5))
    action, _ = Action.objects.get_or_create(user=user, name='Math')
    return ScheduleBlock.objects.create(schedule=schedule, action=action, title='Algebra',
                                        start_time=start, end_time=end)


class SaveSessionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='t', email='t@t.com', password='pw12345!x')
        self.client.force_login(self.user)
        self.url = reverse('pomodoro_save_session')

    def post(self, body):
        return self.client.post(self.url, json.dumps(body), content_type='application/json')

    def test_session_is_saved(self):
        response = self.post({'focused_seconds': 1500})
        self.assertEqual(response.status_code, 201)
        session = BlockSession.objects.get()
        self.assertEqual((session.user, session.focused_seconds, session.block), (self.user, 1500, None))
        self.assertEqual(session.duration.total_seconds(), 1500)

    def test_bad_values_are_rejected(self):
        for body in [{}, {'focused_seconds': 'abc'}, {'focused_seconds': 0}, {'focused_seconds': 99999}, []]:
            self.assertEqual(self.post(body).status_code, 400, body)
        self.assertFalse(BlockSession.objects.exists())

    def test_session_can_belong_to_a_block(self):
        block = make_block(self.user)
        self.assertEqual(self.post({'focused_seconds': 1500, 'block_id': block.id}).status_code, 201)
        self.assertEqual(BlockSession.objects.get().block, block)

    def test_cannot_use_someone_elses_block(self):
        other = User.objects.create_user(username='o', email='o@o.com', password='pw12345!x')
        theirs = make_block(other)
        for block_id in [theirs.id, 999999, 'abc']:
            self.assertEqual(self.post({'focused_seconds': 1500, 'block_id': block_id}).status_code, 404)
        self.assertFalse(BlockSession.objects.exists())

    def test_needs_post_and_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.client.logout()
        self.assertEqual(self.post({'focused_seconds': 60}).status_code, 302)
        self.assertFalse(BlockSession.objects.exists())


class PomodoroPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='t', email='t@t.com', password='pw12345!x')
        self.client.force_login(self.user)

    def test_counts_only_todays_sessions(self):
        from django.utils import timezone
        now = timezone.now()
        for ended, seconds in [(now, 1500), (now, 600), (now - datetime.timedelta(days=2), 1500)]:
            BlockSession.objects.create(user=self.user, start_time=ended - datetime.timedelta(seconds=seconds),
                                        end_time=ended, focused_seconds=seconds)
        other = User.objects.create_user(username='o', email='o@o.com', password='pw12345!x')
        BlockSession.objects.create(user=other, start_time=now, end_time=now, focused_seconds=900)

        response = self.client.get(reverse('pomodoro'))
        self.assertEqual(response.context['today_sessions'], 2)
        self.assertEqual(response.context['today_focused_seconds'], 2100)


class FocusLinkTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='t', email='t@t.com', password='pw12345!x')
        self.client.force_login(self.user)

    def test_block_from_schedule_link_is_selected(self):
        block = make_block(self.user)  # not today, still offered when linked
        response = self.client.get(reverse('pomodoro'), {'block': block.id})
        self.assertEqual(response.context['selected_block_id'], block.id)
        self.assertIn(block, response.context['blocks'])

    def test_someone_elses_block_is_ignored(self):
        other = User.objects.create_user(username='o', email='o@o.com', password='pw12345!x')
        response = self.client.get(reverse('pomodoro'), {'block': make_block(other).id})
        self.assertIsNone(response.context['selected_block_id'])
        self.assertEqual(response.context['blocks'], [])

    def test_schedule_links_each_block_to_the_timer(self):
        block = make_block(self.user)
        response = self.client.get(reverse('schedule'), {'date': '2026-01-05'})
        self.assertContains(response, f"{reverse('pomodoro')}?block={block.id}")


class BlockModeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='t', email='t@t.com', password='pw12345!x')
        self.client.force_login(self.user)

    def post(self, body):
        return self.client.post(reverse('pomodoro_save_session'), json.dumps(body), content_type='application/json')

    def test_long_block_run_is_saved(self):
        block = make_block(self.user, datetime.time(8, 30), datetime.time(17, 45))
        self.assertEqual(self.post({'focused_seconds': 9 * 3600 + 15 * 60, 'block_id': block.id}).status_code, 201)
        self.assertEqual(BlockSession.objects.get().focused_seconds, 33300)

    def test_more_than_16_hours_is_rejected(self):
        self.assertEqual(self.post({'focused_seconds': 16 * 3600 + 1}).status_code, 400)

    def test_page_has_block_times_for_block_mode(self):
        block = make_block(self.user)
        response = self.client.get(reverse('pomodoro'), {'block': block.id})
        self.assertContains(response, 'data-start="09:00" data-end="10:00"')
        self.assertContains(response, 'data-date="2026-01-05"')
        self.assertContains(response, 'id="block-mode-btn"')
