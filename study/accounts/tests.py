from django.test import TestCase
from django.urls import reverse

class LoginViewTest(TestCase):
    def test_login_page_status_code(self):
        """Test that the login page is accessible and returns 200 OK"""
        response = self.client.get(reverse('accounts:account_login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'account/login.html')
