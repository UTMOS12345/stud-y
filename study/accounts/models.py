from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid

class User(AbstractUser):
    """Custom User model with UUID primary key and email as username"""
    external_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    email = models.EmailField(unique=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

class Profile(models.Model):
    """User profile with timezone and pomodoro settings"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    timezone = models.CharField(max_length=64, default=settings.TIME_ZONE)
    
    default_pomodoro_duration = models.PositiveIntegerField(default=25)
    default_short_break_duration = models.PositiveIntegerField(default=5)
    default_long_break_duration = models.PositiveIntegerField(default=15)
    default_long_break_interval = models.PositiveIntegerField(default=4)
    
    theme_preference = models.CharField(max_length=20, choices=[
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('system', 'System'),
    ], default='dark')
    language_preference = models.CharField(max_length=10, default='en')
    

    def __str__(self):
        return f"Profile for {self.user.email}"
    
    def get_theme_display_for_html(self):
        """
        Returns the proper HTML data-theme value based on user preference
        Used in base.html for setting data-theme attribute
        """
        if self.theme_preference == 'light':
            return 'studyLight'
        elif self.theme_preference == 'dark':
            return 'studyTheme'
        else:  # system
            return 'system'