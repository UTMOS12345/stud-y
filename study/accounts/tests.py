from django.test import TestCase
from django.urls import reverse

from .models import Profile, User


class LoginViewTest(TestCase):
    def setUp(self):
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

    def test_pages_work_without_profile(self):
        Profile.objects.filter(user=self.user).delete()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('pomodoro')).status_code, 200)
        self.assertTrue(Profile.objects.filter(user=self.user).exists())
