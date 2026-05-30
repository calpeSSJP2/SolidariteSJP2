# system_monitor/middleware.py

from django.utils.timezone import now
from user_agents import parse

from .models import UserDevice


class DeviceTrackingMiddleware:
    """
    Tracks authenticated user devices and updates
    their latest activity.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        response = self.get_response(request)

        if request.user.is_authenticated:

            ip = self.get_client_ip(request)

            user_agent_string = request.META.get(
                "HTTP_USER_AGENT",
                ""
            )

            ua = parse(user_agent_string)

            # Device type detection
            if ua.is_mobile:
                device_type = "Mobile"
            elif ua.is_tablet:
                device_type = "Tablet"
            else:
                device_type = "Desktop"

            # FIX: use correct variable (ua)
            device, created = UserDevice.objects.get_or_create(
                user=request.user,
                device_type=device_type,
                browser=ua.browser.family,
                operating_system=ua.os.family,
                defaults={
                    "ip_address": ip,
                    "user_agent": user_agent_string,
                    "is_active": True,
                }
            )

            # Always update latest activity
            device.last_activity = now()
            device.ip_address = ip
            device.user_agent = user_agent_string
            device.is_active = True

            device.save(
                update_fields=[
                    "last_activity",
                    "ip_address",
                    "user_agent",
                    "is_active"
                ]
            )

        return response

    @staticmethod
    def get_client_ip(request):
        """
        Get real client IP (supports proxies).
        """

        x_forwarded_for = request.META.get(
            "HTTP_X_FORWARDED_FOR"
        )

        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()

        return request.META.get("REMOTE_ADDR")