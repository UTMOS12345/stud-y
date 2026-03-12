from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
import logging

# Import Profile from accounts app
from accounts.models import Profile

User = get_user_model()
logger = logging.getLogger(__name__)

@login_required
def settings_view(request, section='profile'):
    """Main settings dispatcher"""
    try:
        # We fetch the profile linked to the current user
        profile = request.user.profile
    except Profile.DoesNotExist:
        logger.error(f"Profile missing for user {request.user.pk}")
        messages.error(request, 'Profile not found. Please contact support.')
        return redirect('dashboard')

    if request.method == 'POST':
        # Determine which section we are saving based on the URL or a hidden field
        if section == 'profile':
            return handle_profile_post(request, profile)
        elif section == 'pomodoro':
            return handle_pomodoro_post(request, profile)
        elif section == 'preferences':
            return handle_preferences_post(request, profile)
        
    context = {
        'profile': profile,
        'user': request.user,
        'active_section': section,
    }
    return render(request, 'settings/settings_page.html', context)

def handle_profile_post(request, profile):
    """Handles Account info (User model) and Bio (Profile model)"""
    user = request.user
    try:
        # 1. Update User model fields (Names)
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.save()

        # 2. Update Profile model fields (Bio)
        if hasattr(profile, 'bio'):
            profile.bio = request.POST.get('bio', '').strip()
        profile.save()

        logger.info(f"User {user.pk} updated their account/profile info.")
        messages.success(request, '✓ profile updated successfully!')
    except Exception as e:
        logger.error(f"Error updating profile for {user.pk}: {str(e)}")
        messages.error(request, 'error updating profile.')
    
    return redirect('settings:profile')

def handle_pomodoro_post(request, profile):
    """Handles only Profile model (Pomodoro durations)"""
    try:
        # Convert and validate input
        durations = {
            'default_pomodoro_duration': int(request.POST.get('default_pomodoro_duration', 25)),
            'default_short_break_duration': int(request.POST.get('default_short_break_duration', 5)),
            'default_long_break_duration': int(request.POST.get('default_long_break_duration', 15)),
            'default_long_break_interval': int(request.POST.get('default_long_break_interval', 4)),
        }

        # Simple validation
        if durations['default_pomodoro_duration'] < 1:
            raise ValidationError("Duration must be positive.")

        # Update the profile object attributes
        for key, value in durations.items():
            setattr(profile, key, value)
        
        # We ONLY save the profile here. We don't need to save the User.
        profile.save()

        logger.info(f"User {request.user.pk} updated pomodoro settings.")
        messages.success(request, '✓ pomodoro settings updated!')
    except (ValueError, ValidationError) as e:
        messages.error(request, f'Invalid input: {str(e)}')
    except Exception as e:
        logger.error(f"Error updating pomodoro for {request.user.pk}: {str(e)}")
        messages.error(request, 'error saving pomodoro settings.')

    return redirect('settings:pomodoro')

def handle_preferences_post(request, profile):
    """Handles only Profile model (Theme, Timezone, Sync)"""
    try:
        # Update Timezone
        profile.timezone = request.POST.get('timezone', 'UTC').strip()

        # Update Theme
        theme = request.POST.get('theme_preference')
        if theme in ['light', 'dark', 'system']:
            profile.theme_preference = theme

        # Update Language
        profile.language_preference = request.POST.get('language_preference', 'en')

        # Update Checkbox
        profile.google_sync_enabled = request.POST.get('google_sync_enabled') == 'on'

        # We ONLY save the profile here.
        profile.save()

        logger.info(f"User {request.user.pk} updated preferences.")
        messages.success(request, '✓ preferences updated!')
    except Exception as e:
        logger.error(f"Error updating preferences for {request.user.pk}: {str(e)}")
        messages.error(request, 'error saving preferences.')

    return redirect('settings:preferences')


# --- Wrapper views for individual URL endpoints ---

@login_required
def profile_settings(request):
    return settings_view(request, 'profile')

@login_required
def pomodoro_settings(request):
    return settings_view(request, 'pomodoro')

@login_required
def preferences_settings(request):
    return settings_view(request, 'preferences')

@login_required
def security_settings(request):
    return settings_view(request, 'security')

@login_required
def about_settings(request):
    return settings_view(request, 'about')