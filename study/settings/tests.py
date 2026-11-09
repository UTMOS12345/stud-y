import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


class ProductionSettingsTests(SimpleTestCase):
    def load(self, **env):
        """Import the settings in a fresh process with these environment values."""
        code = ("import study.settings as s; print(s.SESSION_COOKIE_SECURE if hasattr(s, 'SESSION_COOKIE_SECURE') else None,"
                " s.CSRF_COOKIE_SECURE if hasattr(s, 'CSRF_COOKIE_SECURE') else None,"
                " getattr(s, 'SECURE_SSL_REDIRECT', None), getattr(s, 'SECURE_HSTS_SECONDS', None),"
                " 'whitenoise.middleware.WhiteNoiseMiddleware' in s.MIDDLEWARE,"
                " s.CACHES['default']['BACKEND'].rsplit('.', 1)[-1] if hasattr(s, 'CACHES') else None)")
        result = subprocess.run([sys.executable, '-c', code], cwd=settings.BASE_DIR, capture_output=True, text=True,
                                env={**os.environ, 'SECRET_KEY': 'x', **env}, check=True)
        return result.stdout.split()

    def test_plain_http_server_keeps_cookies_usable(self):
        cookie, csrf, redirect, hsts, whitenoise, cache = self.load(DEBUG='False', USE_HTTPS='False')
        self.assertEqual((cookie, csrf, redirect, hsts), ('None', 'None', 'None', 'None'))
        self.assertEqual((whitenoise, cache), ('True', 'DatabaseCache'))

    def test_https_server_is_locked_down(self):
        cookie, csrf, redirect, hsts, whitenoise, cache = self.load(DEBUG='False', USE_HTTPS='True')
        self.assertEqual((cookie, csrf, redirect, hsts), ('True', 'True', 'True', '2592000'))

    def test_development_stays_simple(self):
        cookie, csrf, redirect, hsts, whitenoise, cache = self.load(DEBUG='True')
        self.assertEqual((cookie, whitenoise, cache), ('None', 'False', 'None'))
