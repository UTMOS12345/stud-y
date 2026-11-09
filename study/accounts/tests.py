import datetime
import re

from django.core import mail
from django.core.cache import cache
from django.db.models import RestrictedError
from django.test import TestCase, override_settings
from django.urls import path, reverse

from habits.models import Habit, HabitEntry
from schedule.models import Action, BlockSession, DaySchedule, DayTemplate, ScheduleBlock, TemplateBlock

from .models import Profile, User


class LoginViewTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='t', email='t@t.com', password='pw12345!x')

    def test_login_page_status_code(self):
        """Test that the login page is accessible and returns 200 OK"""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')

    def test_login_goes_to_next_page(self):
        response = self.client.post(reverse('login'), {
            'email': 't@t.com', 'password': 'pw12345!x', 'next': '/schedule/',
        })
        self.assertRedirects(response, '/schedule/', fetch_redirect_response=False)

    def test_login_ignores_next_to_other_sites(self):
        response = self.client.post(reverse('login'), {
            'email': 't@t.com', 'password': 'pw12345!x', 'next': 'https://evil.com/',
        })
        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)

    def test_logged_in_user_on_signup_goes_to_dashboard(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('signup'))
        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)

    def test_too_many_wrong_passwords_locks_login(self):
        url = reverse('login')
        for _ in range(5):
            self.assertEqual(self.client.post(url, {'email': 't@t.com', 'password': 'wrong'}).status_code, 200)
        # even the right password is refused while locked
        response = self.client.post(url, {'email': 't@t.com', 'password': 'pw12345!x'})
        self.assertEqual(response.status_code, 429)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_successful_login_resets_failures(self):
        url = reverse('login')
        for _ in range(4):
            self.client.post(url, {'email': 't@t.com', 'password': 'wrong'})
        self.assertEqual(self.client.post(url, {'email': 't@t.com', 'password': 'pw12345!x'}).status_code, 302)
        self.client.logout()
        for _ in range(4):
            self.client.post(url, {'email': 't@t.com', 'password': 'wrong'})
        self.assertEqual(self.client.post(url, {'email': 't@t.com', 'password': 'pw12345!x'}).status_code, 302)

    def test_logout_needs_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        self.assertIn('_auth_user_id', self.client.session)
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_pages_work_without_profile(self):
        Profile.objects.filter(user=self.user).delete()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('pomodoro')).status_code, 200)
        self.assertTrue(Profile.objects.filter(user=self.user).exists())


class PomodoroSettingsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='t', email='t@t.com', password='pw12345!x')
        self.client.force_login(self.user)

    def post(self, **values):
        data = {'default_pomodoro_duration': '25', 'default_short_break_duration': '5',
                'default_long_break_duration': '15', 'default_long_break_interval': '4'}
        data.update(values)
        return self.client.post(reverse('settings:pomodoro'), data)

    def test_valid_values_are_saved(self):
        self.post(default_pomodoro_duration='50', default_long_break_interval='3')
        profile = Profile.objects.get(user=self.user)
        self.assertEqual((profile.default_pomodoro_duration, profile.default_long_break_interval), (50, 3))

    def test_out_of_range_values_are_rejected(self):
        for field, value in [('default_short_break_duration', '0'),
                             ('default_long_break_duration', '100000'),
                             ('default_long_break_interval', '0'),
                             ('default_pomodoro_duration', 'abc')]:
            self.post(**{field: value})
        profile = Profile.objects.get(user=self.user)
        self.assertEqual(profile.default_short_break_duration, 5)
        self.assertEqual(profile.default_long_break_duration, 15)
        self.assertEqual(profile.default_long_break_interval, 4)
        self.assertEqual(profile.default_pomodoro_duration, 25)


class SidebarTest(TestCase):
    def test_help_goes_somewhere(self):
        user = User.objects.create_user(username='t', email='t@t.com', password='pw12345!x')
        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'href="https://github.com/UTMOS12345/stud-y/issues"')


class SettingsUrlTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='t', email='t@t.com', password='pw12345!x')
        self.client.force_login(self.user)

    def test_settings_root_opens_profile(self):
        response = self.client.get('/settings/')
        self.assertRedirects(response, reverse('settings:profile'))

    def test_every_section_loads(self):
        for section in ['profile', 'pomodoro', 'preferences', 'security', 'about']:
            self.assertEqual(self.client.get(reverse(f'settings:{section}')).status_code, 200, section)

    def test_post_to_about_redirects_back(self):
        response = self.client.post(reverse('settings:about'))
        self.assertRedirects(response, reverse('settings:about'))

    def test_change_password(self):
        url = reverse('settings:security')
        response = self.client.post(url, {'old_password': 'wrong', 'new_password1': 'NewPass123!x', 'new_password2': 'NewPass123!x'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'incorrectly')

        response = self.client.post(url, {'old_password': 'pw12345!x', 'new_password1': 'NewPass123!x', 'new_password2': 'NewPass123!x'}, follow=True)
        self.assertRedirects(response, url)
        # still logged in, and the success message is shown
        self.assertContains(response, 'password changed')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass123!x'))

    def test_your_timezone_is_always_offered_and_selected(self):
        url = reverse('settings:preferences')
        self.assertContains(self.client.get(url), '<option value="Asia/Tashkent" selected>')
        profile = Profile.objects.get(user=self.user)
        profile.timezone = 'Asia/Baku'
        profile.save()
        self.assertContains(self.client.get(url), '<option value="Asia/Baku" selected>')

    def test_preferences_page_does_not_rewrite_the_timezone_list(self):
        self.assertNotContains(self.client.get(reverse('settings:preferences')), 'allTimezones')

    def test_reminder_only_accepts_offered_values(self):
        url = reverse('settings:preferences')
        base = {'timezone': 'UTC', 'theme_preference': 'dark', 'language_preference': 'en'}
        self.client.post(url, {**base, 'reminder_minutes': '15'})
        self.assertEqual(Profile.objects.get(user=self.user).reminder_minutes, 15)
        self.client.post(url, {**base, 'reminder_minutes': '999'})
        self.assertEqual(Profile.objects.get(user=self.user).reminder_minutes, 15)

    def test_language_only_accepts_supported_values(self):
        url = reverse('settings:preferences')
        self.client.post(url, {'timezone': 'UTC', 'theme_preference': 'dark', 'language_preference': 'x' * 50})
        self.assertEqual(Profile.objects.get(user=self.user).language_preference, 'en')
        self.assertContains(self.client.get(url), '<option value="en"')


class PasswordResetTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='t', email='t@t.com', password='pw12345!x')
        self.url = reverse('password_reset')

    def request_link(self, email='t@t.com'):
        response = self.client.post(self.url, {'email': email})
        self.assertRedirects(response, reverse('password_reset_done'))
        return re.search(r'http://testserver(/\S+)', mail.outbox[-1].body).group(1) if mail.outbox else None

    def open_form(self):
        form = self.client.get(self.request_link(), follow=True)
        return form, form.redirect_chain[-1][0]

    def test_login_page_links_here(self):
        self.assertContains(self.client.get(reverse('login')), f'href="{self.url}"')

    def test_full_reset(self):
        link = self.request_link()
        self.assertEqual(mail.outbox[0].subject, 'Reset your stud-y password')
        self.assertEqual(mail.outbox[0].to, ['t@t.com'])
        form = self.client.get(link, follow=True)
        self.assertContains(form, 'new_password1')
        response = self.client.post(form.redirect_chain[-1][0],
                                    {'new_password1': 'Fresh-Pass-99', 'new_password2': 'Fresh-Pass-99'})
        self.assertRedirects(response, reverse('password_reset_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Fresh-Pass-99'))
        # the link is spent
        self.assertContains(self.client.get(link, follow=True), 'link expired')

    def test_weak_password_is_refused(self):
        _, url = self.open_form()
        response = self.client.post(url, {'new_password1': '123', 'new_password2': '123'})
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('pw12345!x'))

    def test_unknown_email_looks_the_same_and_sends_nothing(self):
        self.assertIsNone(self.request_link('nobody@t.com'))
        self.assertEqual(len(mail.outbox), 0)

    def test_email_limit(self):
        for _ in range(6):
            self.client.post(self.url, {'email': 't@t.com'})
        self.assertEqual(len(mail.outbox), 3)

    def test_ip_limit(self):
        for n in range(13):
            self.client.post(self.url, {'email': f'x{n}@t.com'})
        self.client.post(self.url, {'email': 't@t.com'})
        self.assertEqual(len(mail.outbox), 0)

    def test_new_password_lifts_the_login_lockout(self):
        for _ in range(5):
            self.client.post(reverse('login'), {'email': 't@t.com', 'password': 'wrong'})
        _, url = self.open_form()
        self.client.post(url, {'new_password1': 'Fresh-Pass-99', 'new_password2': 'Fresh-Pass-99'})
        response = self.client.post(reverse('login'), {'email': 't@t.com', 'password': 'Fresh-Pass-99'})
        self.assertEqual(response.status_code, 302)

    def test_bad_link(self):
        response = self.client.get(reverse('password_reset_confirm', args=['abc', 'set-password-x']))
        self.assertContains(response, 'link expired')


class DeleteAccountTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='t', email='t@t.com', password='pw12345!x')
        self.client.force_login(self.user)
        self.url = reverse('settings:delete_account')

    def fill(self, user):
        day = datetime.date(2026, 1, 5)
        action = Action.objects.create(user=user, name='Math')
        schedule = DaySchedule.objects.create(user=user, date=day)
        block = ScheduleBlock.objects.create(schedule=schedule, action=action, title='A',
                                             start_time=datetime.time(9), end_time=datetime.time(10))
        template = DayTemplate.objects.create(user=user, name='T')
        TemplateBlock.objects.create(template=template, action=action, title='B',
                                     start_time=datetime.time(9), end_time=datetime.time(10))
        moment = datetime.datetime(2026, 1, 5, 5, tzinfo=datetime.timezone.utc)
        BlockSession.objects.create(user=user, block=block, start_time=moment, end_time=moment, focused_seconds=60)
        habit = Habit.objects.create(user=user, name='H', color='#000000')
        HabitEntry.objects.create(habit=habit, date=day, value=100)

    def test_wrong_password_deletes_nothing(self):
        response = self.client.post(self.url, {'password': 'nope'}, follow=True)
        self.assertContains(response, 'Wrong password')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_removes_everything_of_yours_only(self):
        other = User.objects.create_user(username='o', email='o@o.com', password='pw12345!x')
        self.fill(self.user)
        self.fill(other)
        response = self.client.post(self.url, {'password': 'pw12345!x'}, follow=True)
        self.assertContains(response, 'have been deleted')
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertNotIn('_auth_user_id', self.client.session)
        for model in (Profile, Action, DaySchedule, ScheduleBlock, DayTemplate, TemplateBlock, BlockSession, Habit, HabitEntry):
            self.assertEqual(model.objects.count(), 1, model.__name__)
        self.assertTrue(Action.objects.filter(user=other).exists())

    def test_needs_post_and_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.post(self.url, {'password': 'pw12345!x'}).status_code, 302)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_action_in_use_still_cannot_be_deleted_alone(self):
        self.fill(self.user)
        with self.assertRaises(RestrictedError):
            Action.objects.get().delete()


def broken_view(request):
    raise RuntimeError('boom')


urlpatterns = [path('boom/', broken_view)]


class ErrorPageTest(TestCase):
    def test_404(self):
        response = self.client.get('/no-such-page/')
        self.assertTemplateUsed(response, '404.html')
        self.assertContains(response, 'data-text="404"', status_code=404)

    @override_settings(ROOT_URLCONF='accounts.tests')
    def test_500(self):
        self.client.raise_request_exception = False
        response = self.client.get('/boom/')
        self.assertContains(response, 'data-text="500"', status_code=500)
