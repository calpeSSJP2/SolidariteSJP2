from django.shortcuts import render

from django.views.generic import FormView
from django.urls import reverse_lazy
from django.contrib import messages
from .forms import ElectLeaderForm
from .services import elect_new_leader
from django.views.generic import ListView
from .models import LeadershipTerm
from .forms import LeaderFilterForm
from django.urls import reverse_lazy
from django.views.generic import (
    ListView, CreateView, UpdateView,
    DeleteView, DetailView
)
from .models import Election
from .forms import ElectionForm
from django.db.models import Q
from accounts.models import User
from .models import LeadershipTerm

from accounts.models import User
from .models import LeadershipTerm

class DashboardView(ListView):
    model = LeadershipTerm
    template_name = "governance/leaders_dashboard.html"
    context_object_name = "current_leaders"

    def get_queryset(self):
        active_terms = LeadershipTerm.objects.filter(
            is_active=True
        ).select_related("user", "election", "role")

        leadership_roles = [
            "manager",
            "auditor",
            "officer",
            "verifier",
            "secretary",
            "itadmin",
        ]

        users_without_term = User.objects.filter(
            roles__name__in=leadership_roles
        ).exclude(
            id__in=active_terms.values_list("user_id", flat=True)
        ).distinct()

        fallback_terms = []

        for user in users_without_term:
            for role in user.roles.filter(name__in=leadership_roles):
                fallback_terms.append(
                    LeadershipTerm(
                        user=user,
                        role=role,
                        election=None,
                        started_on=user.date_joined.date(),
                        is_active=True
                    )
                )

        return list(active_terms) + fallback_terms



# 📋 List Elections
class ElectionListView(ListView):
    model = Election
    template_name = "governance/election_list.html"
    context_object_name = "elections"
    paginate_by = 10


# ➕ Create Election
class ElectionCreateView(CreateView):
    model = Election
    form_class = ElectionForm
    template_name = "governance/election_form.html"
    success_url = reverse_lazy("governance:election_list")


# ✏ Update Election
class ElectionUpdateView(UpdateView):
    model = Election
    form_class = ElectionForm
    template_name = "governance/election_form.html"
    success_url = reverse_lazy("governance:election_list")


# 👁 Detail View
class ElectionDetailView(DetailView):
    model = Election
    template_name = "governance/election_detail.html"
    context_object_name = "election"


# ❌ Delete Election
class ElectionDeleteView(DeleteView):
    model = Election
    template_name = "governance/election_confirm_delete.html"
    success_url = reverse_lazy("governance:election_list")

class ElectLeaderView(FormView):
    template_name = "governance/elect_leader.html"
    form_class = ElectLeaderForm
    success_url = reverse_lazy("governance:dashboard")

    def form_valid(self, form):
        user = form.cleaned_data["user"]
        role = form.cleaned_data["role"]
        election = form.cleaned_data["election"]

        elect_new_leader(user, role, election)

        messages.success(self.request, "Leader elected successfully.")
        return super().form_valid(form)