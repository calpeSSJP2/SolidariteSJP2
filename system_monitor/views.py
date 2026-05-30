

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
from django.db import connection

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.db import connection


from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.db import connection
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

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.conf import settings
from django.db import connection
import os

import os

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import connection
from django.views.generic import TemplateView


class StorageUsageView(LoginRequiredMixin, TemplateView):
    template_name = "system_monitor/storage_usage.html"

    def folder_size_mb(self, path):
        """
        Return folder size in MB.
        """
        if not path or not os.path.exists(path):
            return 0

        total = 0

        for root, dirs, files in os.walk(path):
            for file in files:
                try:
                    fp = os.path.join(root, file)

                    if os.path.isfile(fp):
                        total += os.path.getsize(fp)

                except (OSError, FileNotFoundError):
                    pass

        return round(total / 1024 / 1024, 2)

    def get_database_size_mb(self):
        """
        Return database size in MB.
        """
        try:
            with connection.cursor() as cursor:

                if connection.vendor == "postgresql":
                    cursor.execute("""
                        SELECT ROUND(
                            pg_database_size(current_database())::numeric
                            / 1024 / 1024,
                            2
                        )
                    """)
                    result = cursor.fetchone()

                elif connection.vendor == "mysql":
                    cursor.execute("""
                        SELECT ROUND(
                            SUM(data_length + index_length)
                            / 1024 / 1024,
                            2
                        )
                        FROM information_schema.TABLES
                        WHERE table_schema = DATABASE()
                    """)
                    result = cursor.fetchone()

                else:
                    return 0

                return float(result[0] or 0)

        except Exception:
            return 0

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Static files
        static_size = self.folder_size_mb(
            getattr(settings, "STATIC_ROOT", "")
        )

        # Media files
        media_size = self.folder_size_mb(
            getattr(settings, "MEDIA_ROOT", "")
        )

        # Project source code size
        project_size = self.folder_size_mb(settings.BASE_DIR)

        # Database size
        database_size = self.get_database_size_mb()

        # Total storage
        total_storage = round(
            static_size +
            media_size +
            database_size,
            2
        )

        context.update({
            "static_size_mb": static_size,
            "media_size_mb": media_size,
            "project_size_mb": project_size,
            "database_size": database_size,
            "total_storage_mb": total_storage,
            "db_vendor": connection.vendor.upper(),
        })

        return context





class DatabaseHealthView(LoginRequiredMixin, TemplateView):
    template_name = "system_monitor/database_health.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["db_vendor"] = connection.vendor

        with connection.cursor() as cursor:

            # PostgreSQL
            if connection.vendor == "postgresql":

                # Total database size
                cursor.execute("""
                    SELECT pg_size_pretty(
                        pg_database_size(current_database())
                    )
                """)
                context["database_size"] = cursor.fetchone()[0]

                # Table sizes
                cursor.execute("""
                    SELECT
                        relname,
                        ROUND(
                            pg_total_relation_size(relid)::numeric
                            / 1024 / 1024,
                            2
                        ) AS size_mb
                    FROM pg_catalog.pg_statio_user_tables
                    ORDER BY pg_total_relation_size(relid) DESC
                """)
                context["tables"] = cursor.fetchall()

            # MySQL
            elif connection.vendor == "mysql":

                # Total database size
                cursor.execute("""
                    SELECT ROUND(
                        SUM(data_length + index_length)
                        / 1024 / 1024,
                        2
                    )
                    FROM information_schema.TABLES
                    WHERE table_schema = DATABASE()
                """)
                context["database_size"] = f"{cursor.fetchone()[0]} MB"

                # Table sizes
                cursor.execute("""
                    SELECT
                        table_name,
                        ROUND(
                            (data_length + index_length)
                            / 1024 / 1024,
                            2
                        ) AS size_mb
                    FROM information_schema.TABLES
                    WHERE table_schema = DATABASE()
                    ORDER BY (data_length + index_length) DESC
                """)
                context["tables"] = cursor.fetchall()

            else:
                context["database_size"] = "N/A"
                context["tables"] = []

        context["table_count"] = len(context["tables"])

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


