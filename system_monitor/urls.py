# system_monitor/urls.py

from django.urls import path

from .views import (
    SystemMonitorDashboardView,
    DeviceDashboardView,
    StorageUsageView,
    DatabaseHealthView,
    OnlineUsersView,
    SecurityLogView,
    PerformanceView,
    MaintenanceView,
)

app_name = "system_monitor"

urlpatterns = [
    # Dashboard
    path(
        "",
        SystemMonitorDashboardView.as_view(),
        name="dashboard"
    ),

    # Devices
    path(
        "devices/",
        DeviceDashboardView.as_view(),
        name="devices"
    ),

    # Online users
    path(
        "online-users/",
        OnlineUsersView.as_view(),
        name="online_users"
    ),

    # Storage
    path(
        "storage/",
        StorageUsageView.as_view(),
        name="storage"
    ),

    # Database health
    path(
        "database/",
        DatabaseHealthView.as_view(),
        name="database"
    ),

    # Security logs
    path(
        "security-logs/",
        SecurityLogView.as_view(),
        name="security_logs"
    ),

    # Performance
    path(
        "performance/",
        PerformanceView.as_view(),
        name="performance"
    ),

    # Maintenance
    path(
        "maintenance/",
        MaintenanceView.as_view(),
        name="maintenance"
    ),
]