from django.urls import path

from . import views

urlpatterns = [
    path('', views.habits_page, name='habits'),
    path('<int:habit_id>/edit/', views.edit_habit, name='habit_edit'),
    path('<int:habit_id>/delete/', views.delete_habit, name='habit_delete'),
    path('<int:habit_id>/entry/', views.set_entry, name='habit_entry'),
]
