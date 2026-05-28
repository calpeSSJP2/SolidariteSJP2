from django.shortcuts import render

# system_monitor/views.py
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import UserDevice
from django.shortcuts import render
from .models import UserDevice
from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def device_dashboard(request):

    devices = UserDevice.objects.select_related('user').order_by('-last_activity')

    return render(
        request,
        'system_monitor/device_dashboard.html',
        {'devices': devices}
    )



class DeviceDashboardView(LoginRequiredMixin, ListView):

    model = UserDevice

    template_name = 'system_monitor/device_dashboard.html'

    context_object_name = 'devices'

    ordering = ['-last_activity']