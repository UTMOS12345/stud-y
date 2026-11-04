import datetime
import json

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from .models import Action, DaySchedule, DayTemplate, ScheduleBlock, TemplateBlock
from .views import _build_schedule_with_gaps, _week_hours

T = datetime.time


class ScheduleTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='t', email='t@t.com', password='pw12345!x')
        self.action = Action.objects.create(user=self.user, name='Math')
        self.client.force_login(self.user)
        self.url = reverse('schedule')

    def add_block(self, date, start, end, title='Block', action=None):
        schedule, _ = DaySchedule.objects.get_or_create(user=self.user, date=date)
        return ScheduleBlock.objects.create(
            schedule=schedule, action=action or self.action,
            title=title, start_time=start, end_time=end,
        )

    def post_json(self, url, body):
        return self.client.post(url, json.dumps(body), content_type='application/json')

    def block_form(self, **extra):
        data = {'action': self.action.id, 'title': 'Algebra', 'start_time': '09:00',
                'end_time': '10:00', 'block_type': 'fixed', 'description': ''}
        data.update(extra)
        return data


class ScheduleViewTests(ScheduleTestCase):
    def test_logged_out_user_is_sent_to_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('login')}?next={self.url}")

    def test_browsing_days_does_not_create_rows(self):
        for day in ['2026-01-01', '2026-01-02', '2026-01-03']:
            self.assertEqual(self.client.get(self.url, {'date': day}).status_code, 200)
        self.assertEqual(DaySchedule.objects.count(), 0)

    def test_adding_block_creates_the_day(self):
        response = self.client.post(f"{self.url}?date=2026-01-02", self.block_form())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(DaySchedule.objects.count(), 1)
        self.assertEqual(ScheduleBlock.objects.count(), 1)

    def test_overlapping_block_is_rejected_with_readable_error(self):
        self.add_block(datetime.date(2026, 1, 2), T(9), T(10), title='First')
        response = self.client.post(f"{self.url}?date=2026-01-02",
                                    self.block_form(start_time='09:30', end_time='10:30'))
        self.assertEqual(ScheduleBlock.objects.count(), 1)
        self.assertContains(response, 'Overlaps with existing block')
        self.assertNotContains(response, "[&#x27;Overlaps")

    def test_invalid_block_leaves_no_empty_day(self):
        self.client.post(f"{self.url}?date=2026-01-04", self.block_form(start_time='11:00', end_time='10:00'))
        self.assertEqual(DaySchedule.objects.count(), 0)

    def test_query_count_stays_small(self):
        for h in range(8, 14):
            self.add_block(datetime.date(2026, 1, 5), T(h), T(h, 45), title=f'b{h}')
        with self.assertNumQueries(9):
            self.client.get(self.url, {'date': '2026-01-05'})

    def test_duplicate_action_name(self):
        response = self.post_json(self.url, {'action': 'create_action', 'name': 'Math'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], "You already have an action called 'Math'")

    def test_unknown_json_action(self):
        response = self.post_json(self.url, {'action': 'nope'})
        self.assertEqual(response.status_code, 400)

    def test_save_empty_day_as_template(self):
        response = self.post_json(f"{self.url}?date=2026-01-09",
                                  {'action': 'convert_to_template', 'template_name': 'X'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(DayTemplate.objects.count(), 0)


class HelperTests(ScheduleTestCase):
    def test_week_hours(self):
        self.add_block(datetime.date(2026, 1, 5), T(9), T(10, 30))   # Monday
        self.add_block(datetime.date(2026, 1, 5), T(11), T(12))
        self.add_block(datetime.date(2026, 1, 7), T(8), T(9, 15))    # Wednesday
        self.add_block(datetime.date(2026, 1, 12), T(9), T(10))      # next week, not counted
        with self.assertNumQueries(1):
            hours = _week_hours(self.user, datetime.date(2026, 1, 7))
        self.assertEqual(hours, [2.5, 0.0, 1.2, 0.0, 0.0, 0.0, 0.0])

    def test_gaps(self):
        blocks = [
            self.add_block(datetime.date(2026, 1, 5), T(9), T(10)),
            self.add_block(datetime.date(2026, 1, 5), T(22), T(23)),
        ]
        gaps = [(g['is_empty'], g['duration_mins']) for g in _build_schedule_with_gaps(blocks)]
        self.assertEqual(gaps, [(True, 540), (False, 60), (True, 720), (False, 60), (True, 59)])


class TemplateTests(ScheduleTestCase):
    def setUp(self):
        super().setUp()
        self.template = DayTemplate.objects.create(user=self.user, name='Mon')
        self.template_url = reverse('template_detail', args=[self.template.id])

    def test_template_block_overlap_is_rejected(self):
        self.client.post(self.template_url, self.block_form())
        self.client.post(self.template_url, self.block_form(start_time='09:30', end_time='10:30'))
        self.assertEqual(TemplateBlock.objects.count(), 1)

    def test_template_block_without_action(self):
        response = self.client.post(self.template_url, self.block_form(action=''))
        self.assertEqual(response.status_code, 302)
        self.assertIsNone(TemplateBlock.objects.get().action)

    def test_save_day_as_template_keeps_blocks_without_action(self):
        day = datetime.date(2026, 1, 5)
        self.add_block(day, T(8), T(9))
        block = self.add_block(day, T(9), T(10), title='Free')
        block.action = None
        block.save()
        template = block.schedule.create_template_from_day('Copy')
        self.assertEqual(template.template_blocks.count(), 2)

    def test_apply_template_skips_overlaps(self):
        TemplateBlock.objects.create(template=self.template, action=self.action,
                                     title='A', start_time=T(9), end_time=T(10))
        TemplateBlock.objects.create(template=self.template, action=self.action,
                                     title='B', start_time=T(11), end_time=T(12))
        self.add_block(datetime.date(2026, 1, 6), T(9, 30), T(10, 30))
        self.assertEqual(self.template.apply_to_date_merge(datetime.date(2026, 1, 6)), (1, 1))
