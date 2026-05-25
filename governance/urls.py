from django.urls import path
from .views import (
    DashboardView,
    ElectionListView,
    ElectionCreateView,
    ElectionUpdateView,
    ElectionDeleteView,
    ElectionDetailView,
    ElectLeaderView,   # ✅ ADD THIS
)

app_name = "governance"

urlpatterns = [
    # 📊 Dashboard
    path("governa/", DashboardView.as_view(), name="dashboard"),

    # 🗳 Elections CRUD
    path("elections/", ElectionListView.as_view(), name="election_list"),
    path("elections/add/", ElectionCreateView.as_view(), name="election_add"),
    path("elections/<int:pk>/", ElectionDetailView.as_view(), name="election_detail"),
    path("elections/<int:pk>/edit/", ElectionUpdateView.as_view(), name="election_edit"),
    path("elections/<int:pk>/delete/", ElectionDeleteView.as_view(), name="election_delete"),

    # 🏆 Elect Leader
    path("elect/", ElectLeaderView.as_view(), name="elect_leader"),  # ✅ NEW
]