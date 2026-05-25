from django.db import models

# system_monitor/models.py

from django.db import models
from django.conf import settings

class UserDevice(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='devices'
    )

    device_type = models.CharField(max_length=50, blank=True)
    browser = models.CharField(max_length=100, blank=True)
    operating_system = models.CharField(max_length=100, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)

    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)

    user_agent = models.TextField(blank=True)

    login_time = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)

    is_active = models.BooleanField(default=True)

    app_version = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.device_type}"

# system_monitor/middleware.py

from .models import UserDevice
from user_agents import parse
from django.utils.timezone import now

class DeviceTrackingMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        response = self.get_response(request)

        if request.user.is_authenticated:

            ip = self.get_client_ip(request)

            user_agent_string = request.META.get('HTTP_USER_AGENT', '')
            user_agent = parse(user_agent_string)

            device_type = "Desktop"

            if user_agent.is_mobile:
                device_type = "Mobile"

            elif user_agent.is_tablet:
                device_type = "Tablet"

            UserDevice.objects.create(
                user=request.user,
                device_type=device_type,
                browser=user_agent.browser.family,
                operating_system=user_agent.os.family,
                ip_address=ip,
                user_agent=user_agent_string,
                last_activity=now(),
            )

        return response

    def get_client_ip(self, request):

        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')

        return ip

