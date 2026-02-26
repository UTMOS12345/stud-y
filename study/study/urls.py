from django.urls import path, include
from django.views.generic import RedirectView
from django.contrib import admin

urlpatterns = [
    path('accounts/', include('accounts.urls')),
    path('login/', RedirectView.as_view(url='/accounts/login/', permanent=False)),
    path('signup/', RedirectView.as_view(url='/accounts/signup/', permanent=False)),
    path('', RedirectView.as_view(url='/accounts/login/', permanent=False)),
    path('admin/', admin.site.urls),
]