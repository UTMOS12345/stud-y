from django.urls import path

from . import views

urlpatterns = [
    path('', views.board, name='kanban'),
    path('columns/', views.add_column, name='kanban_add_column'),
    path('columns/<int:column_id>/rename/', views.rename_column, name='kanban_rename_column'),
    path('columns/<int:column_id>/delete/', views.delete_column, name='kanban_delete_column'),
    path('columns/<int:column_id>/cards/', views.add_card, name='kanban_add_card'),
    path('cards/move/', views.move_card, name='kanban_move_card'),
    path('cards/<int:card_id>/edit/', views.edit_card, name='kanban_edit_card'),
    path('cards/<int:card_id>/delete/', views.delete_card, name='kanban_delete_card'),
]
