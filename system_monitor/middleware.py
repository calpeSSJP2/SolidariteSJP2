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

            # Update existing device OR create new one
            device, created = UserDevice.objects.get_or_create(
                user=request.user,
                user_agent=user_agent_string,
                defaults={
                    'device_type': device_type,
                    'browser': user_agent.browser.family,
                    'operating_system': user_agent.os.family,
                    'ip_address': ip,
                    'last_activity': now(),
                    'is_active': True,
                }
            )

            # Update activity if device already exists
            if not created:
                device.last_activity = now()
                device.ip_address = ip
                device.is_active = True
                device.save(update_fields=[
                    'last_activity',
                    'ip_address',
                    'is_active'
                ])

        return response

    def get_client_ip(self, request):

        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')

        return ip