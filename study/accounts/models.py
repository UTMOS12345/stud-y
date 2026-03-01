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
    timezone = models.CharField(max_length=64, default='UTC')
    
    default_pomodoro_duration = models.PositiveIntegerField(default=25)
    default_short_break_duration = models.PositiveIntegerField(default=5)
    default_long_break_duration = models.PositiveIntegerField(default=15)
    default_long_break_interval = models.PositiveIntegerField(default=4)
    
    theme_preference = models.CharField(max_length=20, choices=[
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('system', 'System'),
    ], default='system')
    language_preference = models.CharField(max_length=10, default='en')
    
    google_sync_enabled = models.BooleanField(default=False)

    def __str__(self):
        return f"Profile for {self.user.email}"
