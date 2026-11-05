from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
import logging
import pytz

# Import Profile from accounts app
from accounts.models import Profile

User = get_user_model()
logger = logging.getLogger(__name__)

# List of common timezones
COMMON_TIMEZONES = [
    'UTC',
    'Africa/Cairo', 'Africa/Johannesburg', 'Africa/Lagos',
    'America/Anchorage', 'America/Chicago', 'America/Denver', 'America/Los_Angeles', 'America/New_York', 'America/Toronto', 'America/Vancouver',
    'Asia/Bangkok', 'Asia/Dubai', 'Asia/Hong_Kong', 'Asia/Jakarta', 'Asia/Kolkata', 'Asia/Shanghai', 'Asia/Singapore', 'Asia/Tashkent', 'Asia/Tokyo',
    'Australia/Brisbane', 'Australia/Sydney',
    'Europe/Berlin', 'Europe/London', 'Europe/Moscow', 'Europe/Paris',
    'Pacific/Auckland', 'Pacific/Fiji'
]

# (min, max) for each pomodoro setting, matching the inputs in pomodoro_section.html
POMODORO_LIMITS = {
    'default_pomodoro_duration': (1, 120),
    'default_short_break_duration': (1, 60),
    'default_long_break_duration': (1, 120),
    'default_long_break_interval': (1, 20),
}
POMODORO_LABELS = {
    'default_pomodoro_duration': 'Focus time',
    'default_short_break_duration': 'Short break',
    'default_long_break_duration': 'Long break',
    'default_long_break_interval': 'Long break interval',
}

@login_required
def settings_view(request, section='profile'):
    """Main settings dispatcher"""
    # Users made before the signal existed (e.g. createsuperuser) may have no profile yet
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        # Determine which section we are saving based on the URL or a hidden field
        if section == 'profile':
            return handle_profile_post(request, profile)
        elif section == 'pomodoro':
            return handle_pomodoro_post(request, profile)
        elif section == 'preferences':
            return handle_preferences_post(request, profile)
        elif section == 'security':
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)  # stay logged in after the change
                logger.info(f"User {user.pk} changed their password.")
                messages.success(request, '✓ password changed!')
                return redirect('settings:security')
            # fall through and show the form with its errors
            return render(request, 'settings/settings_page.html', {
                'profile': profile, 'user': request.user, 'active_section': section,
                'timezones': COMMON_TIMEZONES, 'password_form': password_form,
            })
        # Sections without a form: send the user back instead of re-rendering on POST
        return redirect(f'settings:{section}')

    context = {
        'profile': profile,
        'user': request.user,
        'active_section': section,
        'timezones': COMMON_TIMEZONES,
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

        # Same limits as the inputs on the settings page
        for key, value in durations.items():
            low, high = POMODORO_LIMITS[key]
            if not low <= value <= high:
                raise ValidationError(f"{POMODORO_LABELS[key]} must be between {low} and {high}.")

        # Update the profile object attributes
        for key, value in durations.items():
            setattr(profile, key, value)
        
        # We ONLY save the profile here. We don't need to save the User.
        profile.save()

        logger.info(f"User {request.user.pk} updated pomodoro settings.")
        messages.success(request, '✓ pomodoro settings updated!')
    except ValueError:
        messages.error(request, 'Invalid input: please enter whole numbers.')
    except ValidationError as e:
        messages.error(request, f"Invalid input: {' '.join(e.messages)}")
    except Exception as e:
        logger.error(f"Error updating pomodoro for {request.user.pk}: {str(e)}")
        messages.error(request, 'error saving pomodoro settings.')

    return redirect('settings:pomodoro')

def handle_preferences_post(request, profile):
    """Handles only Profile model (Theme, Timezone, Sync)"""
    try:
        # Update Timezone
        timezone = request.POST.get('timezone', 'UTC').strip()
        # Validate timezone exists
        try:
            pytz.timezone(timezone)
            profile.timezone = timezone
        except pytz.exceptions.UnknownTimeZoneError:
            logger.warning(f"Invalid timezone '{timezone}' provided by user {request.user.pk}")
            profile.timezone = 'UTC'

        # Update Theme
        theme = request.POST.get('theme_preference', 'dark')
        if theme in ['light', 'dark', 'system']:
            profile.theme_preference = theme
            logger.info(f"User {request.user.pk} changed theme to {theme}")

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