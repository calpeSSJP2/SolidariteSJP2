# ======================
# Python stdlib
# ======================
from decimal import Decimal
from accounts.services import create_member_account_with_capital
from accounts.utils.rbac import has_any_role, has_role
from django.contrib.auth import logout
from django.contrib import messages
from django.views.generic import RedirectView, TemplateView
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.contrib.auth import logout
from django.contrib import messages
from django.views.generic import RedirectView, TemplateView
from django.views.decorators.cache import never_cache
from django.utils.decorators import method_decorator
# ======================
# Django core
# ======================
from django.utils import timezone
from django.db import transaction
from django.db.models import (    Sum, F, DecimalField, ExpressionWrapper, Value
)
from django.db.models.functions import Coalesce, TruncMonth

from django.contrib.auth import get_user_model,logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import (
    LoginView,
    PasswordResetView,
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView
)
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib import messages

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.urls import reverse, reverse_lazy

from django.views import View
from django.views.generic import (
    CreateView,DeleteView,RedirectView,
    DetailView,
    ListView,
    UpdateView,
    TemplateView,
    RedirectView,
    FormView
)

# ======================
# Local app models
# ======================
from .models import (
    MemberAccount,
    MembersProfile,
    SJP2_Profile,
    SJP2_Account,
    AccountStatusSnapshot
)

from transact2_loans.models import Loan, LoanPayment
from transact3_lending.models import PeerToPeerLoan
from ledger.models import AccountStatement, SystemAccountStatement
from django.http import HttpResponseForbidden
# ======================
# Local app forms
# ======================
from .forms import (
    RegistrationForm,
    SJP2AccountForm,
    SJP2_ProfileForm,
    UserUpdateForm,
    MembersProfileUpdateForm,
    PasswordResetDirectForm
)

# ======================
# Services / utilities
# ======================

# ======================
# User model (ONLY ONE SOURCE)
# ======================
User = get_user_model()




# ==============================
# DECORATOR (ONLY ONE)
# ==============================

def roles_required(*roles):
    def check(user):
        return has_any_role(user, roles)
    return user_passes_test(check)


# ==============================
# CONTEXT CHECK//Best use → access control
# ==============================
def is_member_context(request):
    return (request.user.is_authenticated
        and request.session.get("active_mode") == "CUSTOMER_MODE"
        and request.user.roles.filter(name="ordinary_member").exists() )


class ActiveRoleRequiredMixin:
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):

        if not request.user.is_authenticated:
            return self.handle_no_permission()

        active_role = request.session.get("active_role")

        if active_role not in self.allowed_roles:
            return HttpResponseForbidden("You are not allowed.")

        return super().dispatch(request, *args, **kwargs)

@login_required
def customer_dashboard(request):
    if request.session.get("active_mode") != "CUSTOMER_MODE":
        return redirect("accounts:select_mode")

    profile = get_object_or_404(MembersProfile, user=request.user)
    accounts = MemberAccount.objects.filter(member=profile)

    return render(request, "accounts/customer_dashboard.html", {
        "accounts": accounts
    })


# ==============================
# MODE SWITCHING (FIXED LOGIC)
# ==============================
@login_required
def switch_role(request):
    if request.method == "POST":
        role = request.POST.get("role")

        # 1. Validate role belongs to user
        if not request.user.roles.filter(name=role).exists():
            return HttpResponseForbidden("Invalid role")

        # 2. Set active role (session state)
        request.session["active_role"] = role

        # 3. Map role → mode (KEEP YOUR LOGIC)
        ROLE_MODE_MAP = {
            "ordinary_member": "CUSTOMER_MODE",
            "officer": "STAFF_MODE",
            "manager": "STAFF_MODE",
            "auditor": "AUDIT_MODE",
            "itadmin": "ADMIN_MODE",
            "secretary": "STAFF_MODE",
        }

        request.session["active_mode"] = ROLE_MODE_MAP.get(role)

    return redirect("accounts:dashboard-router")



# ==============================
# CENTRAL ROUTER (LOGIN DESTINATION)
# ==============================
from accounts.utils.rbac import get_user_roles
@login_required

def dashboard_router(request):
    user = request.user
    mode = request.session.get("active_mode")
    roles = get_user_roles(user)

    # If session missing → force mode selection
    if not mode:
        return redirect("accounts:home")  # or select_mode page

    if mode == "CUSTOMER_MODE" and "ordinary_member" in roles:
        return redirect("accounts:customer-dashboard")

    if mode == "STAFF_MODE":
        if "manager" in roles:
            return redirect("accounts:manager-dashboard")
        if "officer" in roles:
            return redirect("accounts:officer-dashboard")
        if "secretary" in roles:
            return redirect("accounts:secretary-dashboard")

    if mode == "AUDIT_MODE" and "auditor" in roles:
        return redirect("accounts:auditor-dashboard")

    if mode == "ADMIN_MODE" and "itadmin" in roles:
        return redirect("accounts:itadmin-dashboard")

    # 🚨 IMPORTANT fallback (stop loop)
    return redirect("accounts:home")

# ==============================
# LOGIN VIEW (CORRECT FLOW)
# ==============================
class CustomLoginView(LoginView):
    template_name = "accounts/user_login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()

        # SET SESSION FIRST
        if has_role(user, "ordinary_member"):
            self.request.session["active_mode"] = "CUSTOMER_MODE"
        elif has_any_role(user, ["officer", "manager", "secretary"]):
            self.request.session["active_mode"] = "STAFF_MODE"
        elif has_role(user, "auditor"):
            self.request.session["active_mode"] = "AUDIT_MODE"
        elif has_role(user, "itadmin"):
            self.request.session["active_mode"] = "ADMIN_MODE"

        return super().form_valid(form)

    def get_success_url(self):
        if self.request.user.is_superuser:
            return reverse("admin:index")
        return reverse("accounts:dashboard-router")



##Define Role-Specific Dashboards, In accounts/views.py, define views for each role:
# yourapp/views.py

@method_decorator(never_cache, name='dispatch')
class LogoutView(RedirectView):
    pattern_name = 'accounts:home'

    def get_redirect_url(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            logout(self.request)
        return super().get_redirect_url(*args, **kwargs)


class CustomLogoutView(LogoutView):
    def dispatch(self, request, *args, **kwargs):
        messages.success(request, "You have been logged out successfully.")
        return super().dispatch(request, *args, **kwargs)


@method_decorator(never_cache, name='dispatch')
class HomeView(TemplateView):
    template_name = 'accounts/ssjp2_home.html'


class RegisterView(FormView, ListView):
    model = User
    template_name = "accounts/registration.html"
    form_class = RegistrationForm
    success_url = reverse_lazy('accounts:Register-success')

    paginate_by = 10  # optional

    def get_queryset(self):
        return User.objects.prefetch_related('roles', 'membersprofile__account').order_by('-id')

    def form_valid(self, form):
        with transaction.atomic():
            form.save()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["users"] = self.get_queryset()
        return context


class UserUpdateView(LoginRequiredMixin,UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = "accounts/edit.html"
    success_url = reverse_lazy("accounts:member-list")

    def form_valid(self, form):
        response = super().form_valid(form)

        user = self.object
        roles = form.cleaned_data["roles"]
        user.roles.set(roles)

        # ✔ sync profile safely
        if any(r.name == "ordinary_member" for r in roles):
            profile, _ = MembersProfile.objects.get_or_create(user=user)
            profile.national_id = self.request.POST.get("national_id")
            profile.address = self.request.POST.get("address")
            profile.save()

        return response

class UserDeleteView(LoginRequiredMixin,DeleteView):
    model = User
    template_name = "accounts/confirm_delete.html"
    success_url = reverse_lazy("accounts:member-list")

class UserListView(LoginRequiredMixin,ListView):
    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    paginate_by = 10 # optional but recommended

    def get_queryset(self):
        return (
            User.objects
            .select_related('membersprofile__account')  # faster joins
            .prefetch_related('roles')  # M2M stays here
            .order_by('-id')
        )

class CustomPasswordResetView(SuccessMessageMixin, PasswordResetView):
    template_name = 'accounts/password_reset_form.html'
    email_template_name = 'accounts/password_reset_email.html'
    subject_template_name = 'accounts/password_reset_subject.txt'
    success_url = reverse_lazy('accounts:password_reset_done')

class CustomPasswordResetDoneView(PasswordResetDoneView):
        template_name = 'accounts/password_reset_done.html'


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'




class MemberAccountCreateView(LoginRequiredMixin,CreateView):
    model = MemberAccount
    fields = ['member', 'shares', 'opened_on']
    template_name = 'accounts/member_account_create.html'
    success_url = reverse_lazy('accounts:member_account-list')

    def form_valid(self, form):
        member_profile = form.cleaned_data['member']
        shares = form.cleaned_data['shares']

        try:
            account, transaction_record = create_member_account_with_capital(
                member_profile=member_profile, shares=shares  )
            messages.success(
                self.request,
                f"Member account {account.account_number} created successfully with initial deposit!"   )
        except Exception as e:
            messages.error(self.request, f"Error creating account: {str(e)}")
            return super().form_invalid(form)

        return redirect(self.success_url)

    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)


# View account detail
class MemberAccountDetailView(LoginRequiredMixin,DetailView):
    model = MemberAccount
    template_name = 'accounts/member_account_detail.html'

class MemberAccountListView(LoginRequiredMixin,ActiveRoleRequiredMixin, ListView):
    allowed_roles = ['manager', 'officer', 'itadmin','ordinary_member']
    model = MemberAccount
    template_name = 'accounts/member_account_list.html'
    context_object_name = 'accounts'
    paginate_by = 5

    def get_queryset(self):
        user = self.request.user
        active_role = self.request.session.get("active_role")  ##To control if we change role

        # Staff roles → see all accounts
        if active_role in ['officer', 'manager', 'itadmin']:
            return MemberAccount.objects.all().order_by('-opened_on')

        # Ordinary member → only their account
        if active_role == 'ordinary_member':
            try:
                return MemberAccount.objects.filter(
                    member=user.membersprofile
                )
            except MembersProfile.DoesNotExist:
                return MemberAccount.objects.none()

        # Others → nothing
        return MemberAccount.objects.none()

class MemberAccountUpdateView(LoginRequiredMixin,UpdateView):
    model = MemberAccount
    fields = ['shares']
    template_name = 'accounts/member_account_status_update.html'
    success_url = '/accounts/'

# accounts/views_account_actions.py



class SuspendAccountView(LoginRequiredMixin,View):
    def post(self, request, pk):
        account = get_object_or_404(MemberAccount, pk=pk)
        account.suspend_account()
        return redirect('accounts:member_account-actions')  # redirect back to list

class CloseAccountView(LoginRequiredMixin,View):
    def post(self, request, pk):
        account = get_object_or_404(MemberAccount, pk=pk)
        account.close_account()
        messages.success(request, f"❌ Account {account.account_number} has been closed.")
        return redirect('accounts:account_detail', pk=pk)

class ActivateAccountView(LoginRequiredMixin,View):
    def post(self, request, pk):
        account = get_object_or_404(MemberAccount, pk=pk)
        account.activate_account()
        messages.success(request, f"✅ Account {account.account_number} is now active.")
        return redirect('accounts:account_detail', pk=pk)

class DormantAccountView(LoginRequiredMixin,View):
    def post(self, request, pk):
        account = get_object_or_404(MemberAccount, pk=pk)
        account.dormant_account()
        messages.success(request, f"😴 Account {account.account_number} is now dormant.")
        return redirect('accounts:account_detail', pk=pk)


# List accounts
class MemberAccountActionView(LoginRequiredMixin,ListView):
    model = MemberAccount
    template_name = 'accounts/member_account_actions.html'
    context_object_name = 'accounts'  # optional: change default "object_list"
    paginate_by = 5  # Show 5 members per page
    #I want to get a list interms of date of open
    def get_queryset(self):
        return MemberAccount.objects.all().order_by('-opened_on')  # Use your actual date field

class SnapshotListView(LoginRequiredMixin, ListView):
    model = AccountStatusSnapshot
    template_name = 'accounts/snapshot_list.html'
    paginate_by = 50  # optional pagination

    def get_queryset(self):
        queryset = super().get_queryset()
        year = self.request.GET.get('year')
        month = self.request.GET.get('month')
        if year:
            queryset = queryset.filter(year=year)
        if month:
            queryset = queryset.filter(month=month)
        return queryset


class SSP2RegisterView(LoginRequiredMixin,FormView):
    template_name = 'accounts/registration.html'
    form_class = RegistrationForm
    success_url = reverse_lazy('accounts:register')  ##Yagombye kugaruka kuri original form, here,'accounts:login' kumuntu ukora other services

    def form_valid(self, form):
        print("Form is valid! Saving user...")
        user = form.save()
        print("User saved:", user)

        # ✅ Add success message
        messages.success(self.request, "Registered successfully! You can now log in.")
        return super().form_valid(form)


class ProfileSuccessView(LoginRequiredMixin,TemplateView):
    template_name = 'accounts/sjp2_profile_success.html'

# Create account


class SJP2AccountCreateView(LoginRequiredMixin,CreateView):
    model = SJP2_Account
    form_class = SJP2AccountForm
    template_name = 'accounts/sjp2_account_create.html'

    def get_success_url(self):
        return reverse('accounts:sjp2create_profile')
# View account detail
class SJP2AccountDetailView(LoginRequiredMixin,DetailView):
    model = SJP2_Account
    template_name = 'accounts/sjp2account_detail.html'
    #success_url = reverse_lazy()
# Update accountto set real account after confirmation



class SJP2AccountUpdateView(UpdateView):
    model = SJP2_Account
    form_class = SJP2AccountForm
    template_name = 'accounts/sjp2_account_create.html'  # 🔁 Match existing
    success_url = reverse_lazy('accounts:profile_success')


class SJP2ProfileCreateView(CreateView):
    model = SJP2_Profile
    form_class = SJP2_ProfileForm
    template_name = 'accounts/sjp2_create_profile.html'
    success_url = reverse_lazy('accounts:profile_success')  # Replace with your correct URL name

    def dispatch(self, request, *args, **kwargs):
        # Prevent duplicate profiles
        if SJP2_Profile.objects.filter(user=request.user).exists():
            messages.warning(request, "You already have a profile.")
            return redirect('accounts:profile_success')  # Adjust to your actual profile detail URL name
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # 🔥 This is the missing line that avoids the IntegrityError
        form.instance.user = self.request.user
        return super().form_valid(form)

class Sjp2AccountActionView(ListView):
    model = SJP2_Account
    template_name = 'accounts/ssjp2_account_actions.html'
    context_object_name = 'ssjp_accounts'  # optional: change default "object_list"
    paginate_by = 5  # Show 5 members per page
        # I want to get a list interms of date of open
    def get_queryset(self):
        return SJP2_Account.objects.all().order_by('id')  # or another field

    # Update account
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_accounts'] = SJP2_Account.objects.count()  # Total registered accounts
        return context

class SJP2AccountDeleteView(LoginRequiredMixin,DeleteView):
    model =  SJP2_Account
    template_name = 'accounts/sjp2account_confirm_delete.html'
    success_url = reverse_lazy('accounts:ssjp2_account-actions')  # Update this to your actual list view name




class PasswordResetDirectView(LoginRequiredMixin,FormView):
    template_name = 'accounts/password_reset.html'
    form_class = PasswordResetDirectForm
    success_url = reverse_lazy('accounts:login')  # Redirect to login after reset

    def form_valid(self, form):
        username = form.cleaned_data['username']
        new_password = form.cleaned_data['new_password1']

        user = User.objects.get(username=username)
        user.set_password(new_password)
        user.save()

        messages.success(self.request, f"Password successfully reset for {username}. You can now log in.")
        return super().form_valid(form)


class MembersProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = MembersProfile
    form_class = MembersProfileUpdateForm
    template_name = 'accounts/memberprofile_edit.html'
    success_url = reverse_lazy('accounts:profile-detail')

    def get_object(self):
        # ✅ Allow user to edit ONLY their own profile
        return MembersProfile.objects.get(user=self.request.user)


    def form_valid(self, form):
        messages.success(self.request, "Profile updated successfully.")
        return super().form_valid(form)


class DashboardStatsMixin:
    def get_dashboard_stats(self):
        today = timezone.now().date()

        # ----------------------------
        # ✅ REGULAR LOANS REMAINING
        # ----------------------------
        regular_remaining = (
            Loan._base_manager
            .filter(status__in=[
                Loan.LoanStatus.APPROVED,
                Loan.LoanStatus.ACTIVE
            ])
            .annotate(
                total_paid=Coalesce(Sum('payments__amount'), Decimal('0.00'))
            )
            .annotate(
                remaining=ExpressionWrapper(
                    F('amount') - F('total_paid'),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                )
            )
            .aggregate(total=Coalesce(Sum('remaining'), Decimal('0.00')))
        )['total']

        # ----------------------------
        # ✅ PEER LOANS REMAINING
        # ----------------------------
        peer_remaining = (
            PeerToPeerLoan._base_manager
            .filter(is_fully_paid=False)
            .annotate(
                total_paid=Coalesce(Sum('repayments__amount'), Decimal('0.00'))
            )
            .annotate(
                remaining=ExpressionWrapper(
                    F('amount') - F('total_paid'),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                )
            )
            .aggregate(total=Coalesce(Sum('remaining'), Decimal('0.00')))
        )['total']

        # ----------------------------
        # ✅ COMBINED TOTAL
        # ----------------------------
        total_remaining_loans = regular_remaining + peer_remaining

        return {
            # KPIs
            'active_loans': Loan._base_manager.filter(
                status=Loan.LoanStatus.ACTIVE
            ).count(),

            # 💰 MAIN RESULT YOU WANT
            'total_loans_remaining': regular_remaining,
            'total_peer_remaining': peer_remaining,
            'total_all_remaining_loans': total_remaining_loans,

            # Optional extras (safe global values)
            'total_loans_requested': (
                Loan._base_manager.aggregate(
                    total=Coalesce(Sum('amount'), Decimal('0.00'))
                )['total']
            ),

            'total_peer_borrowed': (
                PeerToPeerLoan._base_manager.aggregate(
                    total=Coalesce(Sum('amount'), Decimal('0.00'))
                )['total']
            ),
            # KPIs
            'dormant_accounts': MemberAccount.objects.filter(
                status_type=MemberAccount.StatusType.DORMANT
            ).count(),

            'active_accounts': MemberAccount.objects.filter(
                status_type=MemberAccount.StatusType.ACTIVE
            ).count(),

            'total_accounts': MemberAccount.objects.count(),

            # Member accounts
            'total_principal': (
                    MemberAccount.objects.aggregate(total=Sum('principal'))['total']
                    or Decimal('0.00')
            ),

            'total_balance': (
                    MemberAccount.objects.aggregate(total=Sum('balance'))['total']
                    or Decimal('0.00')
            ),

            'total_shares': (
                    MemberAccount.objects.filter(
                        status_type=MemberAccount.StatusType.ACTIVE
                    ).aggregate(total=Sum('shares'))['total'] or 0
            ),

            # Monthly deposits (unchanged, but safe)
            'monthly_deposits': (
                AccountStatement._base_manager
                .filter(
                    transaction_type=AccountStatement.TransactionType.DEPOSIT
                )
                .annotate(month=TruncMonth('date'))
                .values('month')
                .annotate(total=Coalesce(Sum('credit'), Decimal('0.00')))
                .order_by('month')
            ),
        }

class OfficerDashboardView(LoginRequiredMixin,ActiveRoleRequiredMixin, DashboardStatsMixin, TemplateView):
    allowed_roles = ['officer']
    template_name = "accounts/officer_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_dashboard_stats())
        return context

@method_decorator(never_cache, name='dispatch')
class ManagerDashboardView(LoginRequiredMixin,ActiveRoleRequiredMixin, DashboardStatsMixin, TemplateView):
    allowed_roles = ['manager']
    template_name = "accounts/manager_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_dashboard_stats())
        return context

class ITDashboardView(LoginRequiredMixin, DashboardStatsMixin, TemplateView):
    template_name = "accounts/IT_admin_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_dashboard_stats())
        return context

class SecretaryDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/secretary_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.now().date()
        user = self.request.user   ##This help to access your account
        # Get member account
        try:
            member_account = user.membersprofile.account
        except (AttributeError, Loan.DoesNotExist):
            # Handle missing account gracefully
            return context
        ##Personal Info
        context['principal'] = member_account.principal
        context['balance'] = member_account.balance
        context['shares'] = member_account.shares
        context['account_status'] = member_account.status_type

        # KPIs

        context['dormant_accounts'] = MemberAccount.objects.filter(
            status_type=MemberAccount.StatusType.DORMANT ).count()
        context['active_accounts'] = MemberAccount.objects.filter(
            status_type=MemberAccount.StatusType.ACTIVE).count()

        context['total_shares'] = (MemberAccount.objects.filter(status_type=MemberAccount.StatusType.ACTIVE
                                                                ).aggregate(total=Sum('shares'))['total'] or 0)
        context['total_accounts'] = MemberAccount.objects.count()
                # -----------------------------------
        # 🔹 TOTAL LOANS REQUESTED (All)
                # -----------------------------------

        return context


#Each MemberAccount is linked to request.user,Each Loan is linked to the member (e.g., loan.member),
# Each AccountStatement is linked to the member account

class CustomerDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/customer_dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if not is_member_context(request):    ##s_member_context is used to access and controll
            return redirect("accounts:switch_role")
        return super().dispatch(request, *args, **kwargs)



    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        today = timezone.now().date()

        # ---------------------------------------------------
        # PROFILE SAFETY
        # ---------------------------------------------------
        try:
            profile = MembersProfile.objects.get(user=user)
        except MembersProfile.DoesNotExist:
            return context

        # ---------------------------------------------------
        # ACCOUNT SAFETY
        # ---------------------------------------------------
        try:
            account = MemberAccount.objects.get(member=profile)
        except MemberAccount.DoesNotExist:
            context["error"] = "No account linked to your profile."
            return context

        # ---------------------------------------------------
        # LOANS
        # ---------------------------------------------------
        loans = Loan.objects.filter(account=account)

        active_loans = loans.filter(
            status=Loan.LoanStatus.ACTIVE
        ).count()

        total_loan_amount = loans.aggregate(
            total=Coalesce(Sum("amount"), Value(Decimal("0.00")))
        )["total"]

        active_loans_qs = loans.filter(
            status__in=[Loan.LoanStatus.APPROVED, Loan.LoanStatus.ACTIVE]
        ).annotate(
            total_paid=Coalesce(
                Sum("payments__amount"),
                Value(Decimal("0.00")),
                output_field=DecimalField()
            ),
            remaining=ExpressionWrapper(
                F("amount") + F("interest_amount") - F("total_paid"),
                output_field=DecimalField()
            )
        )

        loan_remaining = active_loans_qs.aggregate(
            total=Coalesce(Sum("remaining"), Value(Decimal("0.00")))
        )["total"]

        # ---------------------------------------------------
        # PEER-TO-PEER LOANS
        # ---------------------------------------------------
        peer_loans = PeerToPeerLoan.objects.filter(borrower=account)

        peer_loans_qs = peer_loans.annotate(
            total_paid=Coalesce(
                Sum("repayments__amount"),  # ⚠️ confirm related_name
                Value(Decimal("0.00")),
                output_field=DecimalField()
            ),
            remaining=ExpressionWrapper(
                F("amount") - F("total_paid"),
                output_field=DecimalField()
            )
        )

        peer_remaining = peer_loans_qs.filter(
            is_fully_paid=False
        ).aggregate(
            total=Coalesce(Sum("remaining"), Value(Decimal("0.00")))
        )["total"]
        ##--------------------------------
        # OVERDUE LOANS
        # ---------------------------------------------------
        overdue_loans = Loan.objects.filter(
            account=account,
            status=Loan.LoanStatus.ACTIVE,
            payments__due_date__lt=today
        ).distinct()

        # ---------------------------------------------------
        # CONTEXT
        # ---------------------------------------------------
        context.update({
            "account": account,
            "principal": account.principal,
            "balance": account.balance,
            "shares": account.shares,
            "account_status": account.status_type,

            "active_loans": active_loans,
            "total_loan_amount": total_loan_amount,
            "loan_remaining": loan_remaining,

            "peer_remaining": peer_remaining,
            "overdue_loans": overdue_loans,
            "loans": loans.order_by("-issued_on"),
        })

        return context


@method_decorator(login_required, name='dispatch')
class SmartProfileView(TemplateView):
    template_name = "accounts/smart_profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user

        context["user"] = user
        context["profile"] = getattr(user, "membersprofile", None)
        context["roles"] = user.roles.all()
        context["account"] = user.account

        return context
#Simple mental model
#form_valid() → “what mode is user in?”
#router → “where should they go?”
#dispatch() → “are they allowed to enter this page?”