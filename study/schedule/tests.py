import datetime
import json
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from .models import Action, BlockSession, DaySchedule, DayTemplate, ScheduleBlock, TemplateBlock
from .stats import subject_stats, week_stats, week_subjects
from .views import _build_schedule_with_gaps

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
        # a fixed number, it does not grow with the number of blocks or sessions
        with self.assertNumQueries(14):
            self.client.get(self.url, {'date': '2026-01-05'})

    def test_blocks_show_focused_time(self):
        block = self.add_block(datetime.date(2026, 1, 5), T(9), T(10), title='Algebra')
        self.add_block(datetime.date(2026, 1, 5), T(11), T(12), title='Reading')
        now = datetime.datetime(2026, 1, 5, 9, 30, tzinfo=datetime.timezone.utc)
        for seconds in (1500, 900):
            BlockSession.objects.create(user=self.user, block=block, start_time=now, end_time=now,
                                        focused_seconds=seconds)
        response = self.client.get(self.url, {'date': '2026-01-05'})
        focused = {b.title: b.focused_minutes for b in response.context['blocks']}
        self.assertEqual(focused, {'Algebra': 40, 'Reading': 0})
        self.assertContains(response, '40 m.')

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


class DeleteActionTests(ScheduleTestCase):
    def test_delete_action_keeps_blocks(self):
        block = self.add_block(datetime.date(2026, 1, 5), T(9), T(10))
        template = DayTemplate.objects.create(user=self.user, name='Mon')
        t_block = TemplateBlock.objects.create(template=template, action=self.action,
                                               title='A', start_time=T(9), end_time=T(10))
        response = self.post_json(self.url, {'action': 'delete_action', 'action_id': self.action.id})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Action.objects.exists())
        block.refresh_from_db(); t_block.refresh_from_db()
        self.assertIsNone(block.action)
        self.assertIsNone(t_block.action)

    def test_cannot_delete_someone_elses_action(self):
        other = User.objects.create_user(username='o', email='o@o.com', password='pw12345!x')
        theirs = Action.objects.create(user=other, name='Theirs')
        response = self.post_json(self.url, {'action': 'delete_action', 'action_id': theirs.id})
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Action.objects.filter(pk=theirs.pk).exists())


class HelperTests(ScheduleTestCase):
    def test_week_stats(self):
        self.add_block(datetime.date(2026, 1, 5), T(9), T(10, 30))   # Monday
        self.add_block(datetime.date(2026, 1, 5), T(11), T(12))
        self.add_block(datetime.date(2026, 1, 7), T(8), T(9, 15))    # Wednesday
        self.add_block(datetime.date(2026, 1, 12), T(9), T(10))      # next week, not counted
        # focus: 45 min on Monday, 30 min on Wednesday, one session next week
        for day, seconds in [(5, 1500), (5, 1200), (7, 1800), (12, 1500)]:
            ended = datetime.datetime(2026, 1, day, 10, 0, tzinfo=datetime.timezone.utc)
            BlockSession.objects.create(user=self.user, start_time=ended, end_time=ended, focused_seconds=seconds)
        with self.assertNumQueries(2):
            week = week_stats(self.user, datetime.date(2026, 1, 7))
        self.assertEqual([d['planned_hours'] for d in week], [2.5, 0.0, 1.2, 0.0, 0.0, 0.0, 0.0])
        self.assertEqual([d['focused_hours'] for d in week], [0.8, 0.0, 0.5, 0.0, 0.0, 0.0, 0.0])
        self.assertEqual(week[0]['date'], datetime.date(2026, 1, 5))
        self.assertEqual(week[6]['label'], 'Sun')

    def test_week_stats_uses_the_users_day(self):
        # 22:00 UTC on Sunday is already Monday in Tashkent (UTC+5)
        ended = datetime.datetime(2026, 1, 11, 22, 0, tzinfo=datetime.timezone.utc)
        BlockSession.objects.create(user=self.user, start_time=ended, end_time=ended, focused_seconds=3600)
        from django.utils import timezone
        with timezone.override('Asia/Tashkent'):
            week = week_stats(self.user, datetime.date(2026, 1, 12))
        self.assertEqual(week[0]['focused_hours'], 1.0)

    def test_subject_stats(self):
        day = datetime.date(2026, 1, 5)
        english = Action.objects.create(user=self.user, name='English', color='#10B981')
        algebra = self.add_block(day, T(9), T(10))                      # Math 60
        self.add_block(day, T(18), T(18, 30))                           # Math 30, same subject
        reading = self.add_block(day, T(11), T(13), action=english)     # English 120
        self.add_block(datetime.date(2026, 1, 6), T(9), T(10))          # other day
        ended = datetime.datetime(2026, 1, 5, 10, 0, tzinfo=datetime.timezone.utc)
        for block, seconds in [(algebra, 1500), (reading, 1500), (reading, 1500), (None, 600)]:
            BlockSession.objects.create(user=self.user, block=block, start_time=ended, end_time=ended,
                                        focused_seconds=seconds)
        with self.assertNumQueries(2):
            rows = subject_stats(self.user, day)
        self.assertEqual([(r['name'], r['planned_minutes'], r['focused_minutes']) for r in rows],
                         [('English', 120, 50), ('Math', 90, 25), ('No subject', 0, 10)])
        self.assertEqual(rows[0]['color'], '#10B981')
        # a range adds up both days, so Math moves to the top
        rows = subject_stats(self.user, day, day + datetime.timedelta(days=1))
        self.assertEqual((rows[0]['name'], rows[0]['planned_minutes']), ('Math', 150))

    def test_day_summary_on_statistics_tab(self):
        block = self.add_block(datetime.date(2026, 1, 5), T(9), T(11))
        ended = datetime.datetime(2026, 1, 5, 6, 0, tzinfo=datetime.timezone.utc)
        for seconds in (1500, 1500, 1500):
            BlockSession.objects.create(user=self.user, block=block, start_time=ended, end_time=ended,
                                        focused_seconds=seconds)
        summary = self.client.get(self.url, {'date': '2026-01-05'}).context['day_summary']
        self.assertEqual((summary['planned'], summary['focused'], summary['sessions'], summary['done_percent']),
                         ('2h', '1h 15m', 3, 62))
        self.assertEqual(summary['top_subject'], 'Math')

    def test_empty_day_summary(self):
        summary = self.client.get(self.url, {'date': '2026-01-05'}).context['day_summary']
        self.assertEqual((summary['planned_minutes'], summary['done_percent'], summary['top_subject']), (0, None, None))

    def test_week_subjects(self):
        english = Action.objects.create(user=self.user, name='English', color='#10B981')
        self.add_block(datetime.date(2026, 1, 5), T(9), T(11))                   # Mon, Math 2h
        reading = self.add_block(datetime.date(2026, 1, 8), T(9), T(10), action=english)  # Thu
        self.add_block(datetime.date(2026, 1, 13), T(9), T(12))                  # next week
        ended = datetime.datetime(2026, 1, 8, 6, 0, tzinfo=datetime.timezone.utc)
        BlockSession.objects.create(user=self.user, block=reading, start_time=ended, end_time=ended,
                                    focused_seconds=1800)
        rows = week_subjects(self.user, datetime.date(2026, 1, 7))
        self.assertEqual([(r['name'], r['planned'], r['focused'], r['planned_width'], r['focused_width']) for r in rows],
                         [('Math', '2h', '0m', 100, 0), ('English', '1h', '30m', 50, 25)])
        response = self.client.get(self.url, {'date': '2026-01-07'})
        self.assertContains(response, 'This Week by Subject')

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

    def test_template_copy_and_apply_use_few_queries(self):
        day = datetime.date(2026, 1, 5)
        for h in range(6, 18):
            self.add_block(day, T(h), T(h, 30), title=f'b{h}')
        schedule = DaySchedule.objects.get(date=day)
        with self.assertNumQueries(6):  # same count for any number of blocks
            template = schedule.create_template_from_day('Busy day')
        self.assertEqual(template.template_blocks.count(), 12)
        with self.assertNumQueries(9):  # same count for any number of blocks
            applied, skipped = template.apply_to_date_merge(datetime.date(2026, 1, 9))
        self.assertEqual((applied, skipped), (12, 0))
        # applying again to the same day skips everything
        self.assertEqual(template.apply_to_date_merge(datetime.date(2026, 1, 9)), (0, 12))

    def test_apply_template_skips_overlaps(self):
        TemplateBlock.objects.create(template=self.template, action=self.action,
                                     title='A', start_time=T(9), end_time=T(10))
        TemplateBlock.objects.create(template=self.template, action=self.action,
                                     title='B', start_time=T(11), end_time=T(12))
        self.add_block(datetime.date(2026, 1, 6), T(9, 30), T(10, 30))
        self.assertEqual(self.template.apply_to_date_merge(datetime.date(2026, 1, 6)), (1, 1))


class TimezoneTests(ScheduleTestCase):
    # 22:00 UTC on Jan 5 is already Jan 6 in Auckland and Tashkent, still Jan 5 in New York
    NOW = datetime.datetime(2026, 1, 5, 22, 0, tzinfo=datetime.timezone.utc)

    def today_for(self, tz_name):
        self.user.profile.timezone = tz_name
        self.user.profile.save()
        with mock.patch('django.utils.timezone.now', return_value=self.NOW):
            return self.client.get(self.url).context['selected_date']

    def test_today_follows_user_timezone(self):
        self.assertEqual(self.today_for('America/New_York'), datetime.date(2026, 1, 5))
        self.assertEqual(self.today_for('Pacific/Auckland'), datetime.date(2026, 1, 6))
        self.assertEqual(self.today_for('Asia/Tashkent'), datetime.date(2026, 1, 6))

    def test_bad_timezone_falls_back(self):
        self.assertEqual(self.today_for('Not/AZone'), datetime.date(2026, 1, 6))

    def test_new_users_get_app_timezone(self):
        user = User.objects.create_user(username='n', email='n@n.com', password='pw12345!x')
        self.assertEqual(user.profile.timezone, 'Asia/Tashkent')


class ActionColorTests(ScheduleTestCase):
    def test_new_actions_get_different_colors(self):
        # setUp made 'Math' with the default blue
        for name in ['English', 'Coding', 'History']:
            self.post_json(self.url, {'action': 'create_action', 'name': name})
        colors = list(Action.objects.order_by('id').values_list('color', flat=True))
        self.assertEqual(colors, ['#3B82F6', '#10B981', '#F59E0B', '#EF4444'])

    def test_picked_color_is_kept(self):
        self.post_json(self.url, {'action': 'create_action', 'name': 'Art', 'color': '#123456'})
        self.assertEqual(Action.objects.get(name='Art').color, '#123456')

    def test_new_action_form_suggests_next_color(self):
        response = self.client.get(self.url)
        self.assertEqual(response.context['next_action_color'], '#10B981')
        self.assertContains(response, 'value = "#10B981"')

    def test_palette_wraps_around(self):
        for i in range(15):
            Action.objects.create(user=self.user, name=f'a{i}', color=Action.next_color(self.user))
        self.assertEqual(Action.objects.count(), 16)
