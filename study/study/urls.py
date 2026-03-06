from django.urls import path, include
from django.views.generic import RedirectView
from django.contrib import admin

urlpatterns = [
    path('accounts/', include('accounts.urls')),
    path('login/', RedirectView.as_view(url='/accounts/login/')),
    path('signup/', RedirectView.as_view(url='/accounts/signup/')),
    
    path('', include('dashboard.urls')),
    path('dashboard/', RedirectView.as_view(url='/')),
    path('pomodoro/' , include('pomodoro.urls')) ,
    path('admin/', admin.site.urls),
]