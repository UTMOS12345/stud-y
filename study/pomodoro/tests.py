import json

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from schedule.models import BlockSession


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

    def test_needs_post_and_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.client.logout()
        self.assertEqual(self.post({'focused_seconds': 60}).status_code, 302)
        self.assertFalse(BlockSession.objects.exists())
