from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'settings'

urlpatterns = [
    # /settings/ opens the profile section
    path('', RedirectView.as_view(pattern_name='settings:profile'), name='index'),
    
    # Individual section URLs
    path('profile/', views.profile_settings, name='profile'),
    path('pomodoro/', views.pomodoro_settings, name='pomodoro'),
    path('preferences/', views.preferences_settings, name='preferences'),
    path('security/', views.security_settings, name='security'),
    path('about/', views.about_settings, name='about'),
    path('delete-account/', views.delete_account, name='delete_account'),
]








