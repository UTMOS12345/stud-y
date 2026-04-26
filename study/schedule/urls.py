from django.urls import path
from . import views

urlpatterns = [
    path('', views.schedule_view, name='schedule'),
    path('template/<int:template_id>/', views.template_detail_view, name='template_detail'),

]