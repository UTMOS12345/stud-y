from django.urls import path
from . import views

app_name = 'settings'

urlpatterns = [
    # Main settings page with section parameter
    path('', views.profile_settings, name='profile'),
    
    # Individual section URLs
    path('profile/', views.profile_settings, name='profile'),
    path('pomodoro/', views.pomodoro_settings, name='pomodoro'),
    path('preferences/', views.preferences_settings, name='preferences'),
    path('security/', views.security_settings, name='security'),
    path('about/', views.about_settings, name='about'),
]








