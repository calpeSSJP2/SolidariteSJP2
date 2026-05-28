# system_monitor/urls.py

from django.urls import path
from .views import DeviceDashboardView

app_name = 'system_monitor'

urlpatterns = [
    path(
        '',
        DeviceDashboardView.as_view(),
        name='device_dashboard'
    ),
]