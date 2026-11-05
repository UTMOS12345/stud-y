from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

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
