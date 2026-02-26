from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Profile

User = get_user_model()

class UserSignalTest(TestCase):
    def test_profile_created_on_user_creation(self):
        """Test that a Profile is created when a new User is created"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword123'
        )
        
        # Check if profile exists
        self.assertTrue(Profile.objects.filter(user=user).exists())
        
        # Check if it's the correct profile
        profile = Profile.objects.get(user=user)
        self.assertEqual(profile.user, user)

    def test_profile_saved_on_user_save(self):
        """Test that the Profile is saved when the User is saved"""
        user = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpassword123'
        )
        
        profile = user.profile
        profile.timezone = 'America/New_York'
        profile.save()
        
        # Re-save user
        user.save()
        
        # Check if timezone is still correct
        updated_profile = Profile.objects.get(user=user)
        self.assertEqual(updated_profile.timezone, 'America/New_York')
