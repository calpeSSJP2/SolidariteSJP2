from django.shortcuts import render

from django.views.generic import CreateView, ListView, UpdateView
from django.urls import reverse_lazy
from .models import Meeting, MeetingAttendance, MeetingDecision
from .forms import MeetingForm, MeetingAttendanceForm, MeetingDecisionForm

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

class RoleRequiredMixin(LoginRequiredMixin):  ##The class help me to set the user who will access your page
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        user = request.user

        if not user.is_authenticated:
            return self.handle_no_permission()

        if hasattr(user, 'role') and user.role in self.allowed_roles:
            return super().dispatch(request, *args, **kwargs)

        raise PermissionDenied("You do not have permission to access this page.")

class MeetingListView(ListView):
    model = Meeting
    template_name = 'meeting_Mngt/meeting_list.html'
    context_object_name = 'meetings'
    allowed_roles = ['itadmin', 'officer', 'manager']

class MeetingCreateView(RoleRequiredMixin, CreateView):
    model = Meeting
    form_class = MeetingForm
    template_name = 'meeting_Mngt/meeting_form.html'
    success_url = reverse_lazy('meeting_Mngt:meeting-list')
    allowed_roles = ['itadmin', 'officer', 'manager']

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)



class AttendanceCreateView(CreateView):
    model = MeetingAttendance
    form_class = MeetingAttendanceForm
    template_name = 'meeting_Mngt/attendance_form.html'
    success_url = reverse_lazy('meeting_Mngt:meeting-list')


class DecisionCreateView(CreateView):
    model = MeetingDecision
    form_class = MeetingDecisionForm
    template_name = 'meeting_Mngt/decision_form.html'
    success_url = reverse_lazy('meeting_Mngt:meeting-list')
    allowed_roles = ['itadmin', 'officer', 'manager']

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

class DecisionListView(ListView):
    model = MeetingDecision
    template_name = 'meeting_Mngt/decision_list.html'
    context_object_name = 'decisions'
