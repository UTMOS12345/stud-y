import zoneinfo

from django.utils import timezone


class UserTimezoneMiddleware:
    """Use the timezone from the user's profile, so "today" is their today, not the server's."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tz_name = None
        if request.user.is_authenticated:
            profile = getattr(request.user, 'profile', None)
            tz_name = getattr(profile, 'timezone', None)

        try:
            if tz_name:
                timezone.activate(zoneinfo.ZoneInfo(tz_name))
            else:
                timezone.deactivate()
        except (zoneinfo.ZoneInfoNotFoundError, ValueError):
            timezone.deactivate()

        return self.get_response(request)
