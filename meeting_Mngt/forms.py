from django import forms
from .models import Meeting, MeetingAttendance, MeetingDecision


class MeetingForm(forms.ModelForm):
    class Meta:
        model = Meeting
        fields = ['topic', 'date', 'start_time','end_time']


class MeetingAttendanceForm(forms.ModelForm):
    class Meta:
        model = MeetingAttendance
        fields = ['meeting', 'member', 'check_in_time']


class MeetingDecisionForm(forms.ModelForm):
    class Meta:
        model = MeetingDecision
        fields = ['meeting', 'decision_text', 'assigned_to', 'deadline', 'implemented']
