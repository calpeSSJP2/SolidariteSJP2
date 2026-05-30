

# system_monitor/views.py

from django.contrib.sessions.models import Session
from django.utils import timezone
import os
import psutil
from django.conf import settings
from django.views.generic import TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import get_user_model
from .models import SecurityEvent
from .models import UserDevice

User = get_user_model()


class SystemMonitorDashboardView(LoginRequiredMixin, TemplateView):
    """
    Main System Monitor Dashboard
    """

    template_name = "system_monitor/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Users
        context["total_users"] = User.objects.count()

        # Devices
        context["total_devices"] = UserDevice.objects.count()

        # System Performance
        memory = psutil.virtual_memory()

        context["ram_used_mb"] = round(memory.used / 1024 / 1024, 2)
        context["ram_percent"] = memory.percent
        context["cpu_percent"] = psutil.cpu_percent(interval=1)

        # Disk Usage
        disk = psutil.disk_usage("/")

        context["disk_used_gb"] = round(disk.used / (1024 ** 3), 2 )

        context["disk_free_gb"] = round( disk.free / (1024 ** 3), 2        )

        context["disk_percent"] = disk.percent

        return context

class DeviceDashboardView(LoginRequiredMixin, ListView):

    model = UserDevice

    template_name = "system_monitor/devices_dashboard.html"

    context_object_name = "devices"

    ordering = ["-last_activity"]

    paginate_by = 10

class StorageUsageView(LoginRequiredMixin, TemplateView):

    template_name = "system_monitor/storage_usage.html"

    def folder_size_mb(self, path):
        total = 0

        for root, dirs, files in os.walk(path):
            for file in files:
                fp = os.path.join(root, file)

                if os.path.exists(fp):
                    total += os.path.getsize(fp)

        return round(total / 1024 / 1024, 2)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["static_size_mb"] = self.folder_size_mb(
            settings.STATIC_ROOT
        ) if os.path.exists(settings.STATIC_ROOT) else 0

        return context

from django.db import connection


from django.db import connection

class DatabaseHealthView(LoginRequiredMixin, TemplateView):

    template_name = "system_monitor/database_health.html"

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context["db_vendor"] = connection.vendor

        with connection.cursor() as cursor:

            if connection.vendor == "postgresql":

                cursor.execute("""
                    SELECT
                        relname,
                        pg_total_relation_size(relid)
                    FROM pg_catalog.pg_statio_user_tables
                    ORDER BY pg_total_relation_size(relid) DESC
                """)

                context["tables"] = cursor.fetchall()

            elif connection.vendor == "mysql":

                cursor.execute("""
                    SELECT table_name,
                           ROUND(((data_length + index_length)/1024/1024),2)
                    FROM information_schema.TABLES
                    WHERE table_schema = DATABASE()
                """)

                context["tables"] = cursor.fetchall()

            else:
                context["tables"] = []

        return context



class OnlineUsersView(LoginRequiredMixin, TemplateView):
    template_name = "system_monitor/online_users.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sessions = Session.objects.filter( expire_date__gte=timezone.now())
        context["online_count"] = sessions.count()
        return context

class SecurityLogView(LoginRequiredMixin, ListView):

    model = SecurityEvent

    template_name = "system_monitor/security_logs.html"

    context_object_name = "events"

    paginate_by = 10

    ordering = ["-timestamp"]


class PerformanceView(LoginRequiredMixin, TemplateView):

    template_name = "system_monitor/performance.html"

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        memory = psutil.virtual_memory()

        context["ram"] = memory.percent

        context["cpu"] = psutil.cpu_percent(1)

        return context

class MaintenanceView(LoginRequiredMixin, TemplateView):

    template_name = "system_monitor/maintenance.html"


