from django.urls import path
from . import views

urlpatterns = [
    path('', views.pomodoro, name='pomodoro'),
    path('sessions/', views.save_session, name='pomodoro_save_session'),
]
