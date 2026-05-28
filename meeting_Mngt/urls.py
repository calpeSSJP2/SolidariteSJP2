from django.urls import path
from .views import (
    MeetingListView, MeetingCreateView,
    AttendanceCreateView, DecisionCreateView, DecisionListView
)

urlpatterns = [
    path('', MeetingListView.as_view(), name='meeting-list'), ##At project level, I used to start by /meetings
    path('create/', MeetingCreateView.as_view(), name='meeting-create'),
    path('attendance/', AttendanceCreateView.as_view(), name='attendance-create'),
    path('decisions/', DecisionListView.as_view(), name='decision-list'),
    path('decisions/create/', DecisionCreateView.as_view(), name='decision-create'),
]
