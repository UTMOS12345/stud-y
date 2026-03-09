from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
import logging

# Import Profile from accounts app (where it actually is)
from accounts.models import Profile

User = get_user_model()

logger = logging.getLogger(__name__)


@login_required
def settings_view(request, section='profile'):
    """Main settings view that renders different sections"""
    try:
        profile = request.user.profile
    except Profile.DoesNotExist:
        messages.error(request, 'Profile not found. Please contact support.')
        logger.error(f'Profile does not exist for user: {request.user.id}')
        return redirect('dashboard')

    # Handle form submissions for each section
    if request.method == 'POST':
        section_from_post = request.POST.get('section', section)
        
        if section_from_post == 'profile':
            return handle_profile_post(request, request.user, profile)
        elif section_from_post == 'pomodoro':
            return handle_pomodoro_post(request, profile)
        elif section_from_post == 'preferences':
            return handle_preferences_post(request, profile)
        else:
            return redirect('settings:profile')

    context = {
        'profile': profile,
        'user': request.user,
        'active_section': section,
    }
    
    return render(request, 'settings/settings_page.html', context)


def handle_profile_post(request, user, profile):
    """Handle profile form submission"""
    try:
        # Update user first name and last name
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.save()

        # Update profile bio if exists
        if hasattr(profile, 'bio'):
            profile.bio = request.POST.get('bio', '').strip()
        
        profile.save()

        logger.info(f'User {request.user.id} updated profile')
        messages.success(request, '✓ profile updated successfully!')
        return redirect('settings:profile')

    except Exception as e:
        messages.error(request, 'error updating profile. please try again.')
        logger.error(f'Error updating profile for user {request.user.id}: {str(e)}')
        return redirect('settings:profile')


def handle_pomodoro_post(request, profile):
    """Handle pomodoro settings form submission"""
    try:
        # Update pomodoro settings with validation
        default_pomodoro = int(request.POST.get('default_pomodoro_duration', 25))
        if not (1 <= default_pomodoro <= 120):
            raise ValidationError('Work duration must be between 1 and 120 minutes')
        profile.default_pomodoro_duration = default_pomodoro

        short_break = int(request.POST.get('default_short_break_duration', 5))
        if not (1 <= short_break <= 60):
            raise ValidationError('Short break must be between 1 and 60 minutes')
        profile.default_short_break_duration = short_break

        long_break = int(request.POST.get('default_long_break_duration', 15))
        if not (1 <= long_break <= 120):
            raise ValidationError('Long break must be between 1 and 120 minutes')
        profile.default_long_break_duration = long_break

        interval = int(request.POST.get('default_long_break_interval', 4))
        if not (1 <= interval <= 20):
            raise ValidationError('Break interval must be between 1 and 20')
        profile.default_long_break_interval = interval

        profile.save()

        logger.info(f'User {request.user.id} updated pomodoro settings')
        messages.success(request, '✓ pomodoro settings updated!')
        return redirect('settings:pomodoro')

    except ValueError:
        messages.error(request, 'invalid number format. please enter valid numbers.')
        return redirect('settings:pomodoro')
    except ValidationError as e:
        messages.error(request, str(e))
        return redirect('settings:pomodoro')
    except Exception as e:
        messages.error(request, 'error saving pomodoro settings. please try again.')
        logger.error(f'Error updating pomodoro for user {request.user.id}: {str(e)}')
        return redirect('settings:pomodoro')


def handle_preferences_post(request, profile):
    """Handle preferences form submission"""
    try:
        # Update timezone
        timezone = request.POST.get('timezone', '').strip()
        if timezone:
            profile.timezone = timezone

        # Update theme preference
        theme_preference = request.POST.get('theme_preference', '').strip()
        if theme_preference in ['light', 'dark', 'system']:
            profile.theme_preference = theme_preference

        # Update language preference
        language_preference = request.POST.get('language_preference', '').strip()
        if language_preference:
            profile.language_preference = language_preference

        # Update google sync setting
        profile.google_sync_enabled = request.POST.get('google_sync_enabled') == 'on'

        profile.save()

        logger.info(f'User {request.user.id} updated preferences')
        messages.success(request, '✓ preferences updated!')
        return redirect('settings:preferences')

    except Exception as e:
        messages.error(request, 'error saving preferences. please try again.')
        logger.error(f'Error updating preferences for user {request.user.id}: {str(e)}')
        return redirect('settings:preferences')


# Individual section views for direct access
@login_required
def profile_settings(request):
    """Profile settings page"""
    return settings_view(request, 'profile')


@login_required
def pomodoro_settings(request):
    """Pomodoro settings page"""
    return settings_view(request, 'pomodoro')


@login_required
def preferences_settings(request):
    """Preferences settings page"""
    return settings_view(request, 'preferences')


@login_required
def security_settings(request):
    """Security settings page"""
    return settings_view(request, 'security')


@login_required
def about_settings(request):
    """About settings page"""
    return settings_view(request, 'about')