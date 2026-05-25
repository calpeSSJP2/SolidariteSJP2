from django.urls import path
from django.views.generic import TemplateView
from .views import (
    HomeView, CustomLoginView, CustomLogoutView, RegisterView,UserUpdateView,UserDeleteView,
    MembersProfileUpdateView, UserListView,SmartProfileView,


    ManagerDashboardView,
    OfficerDashboardView,
    CustomerDashboardView,
    ITDashboardView,
    SecretaryDashboardView,
    #VerifierDashboardView,

    CustomPasswordResetView,
    CustomPasswordResetDoneView,
    CustomPasswordResetConfirmView,
    CustomPasswordResetCompleteView,

    MemberAccountCreateView,
    MemberAccountDetailView,
    MemberAccountListView,
    MemberAccountUpdateView,

    SJP2ProfileCreateView,
    ProfileSuccessView,
    SJP2AccountCreateView,
    SJP2AccountDetailView,
    SJP2AccountUpdateView,

    SuspendAccountView,
    CloseAccountView,
    ActivateAccountView,
    DormantAccountView,

    SnapshotListView,
    MemberAccountActionView,
    Sjp2AccountActionView,
    SJP2AccountDeleteView,

    dashboard_router,  switch_role, # ⭐ ADD THIS they were defined as function ,not CBV 0, it is why no as_view
)

app_name = 'accounts'

urlpatterns = [

    # -------------------
    # AUTH
    # -------------------
    path('', HomeView.as_view(), name='home'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path('register/', RegisterView.as_view(), name='register'),

    # -------------------
    # ROUTER (IMPORTANT)
    # -------------------
    path('dashboard/', dashboard_router, name='dashboard-router'),
# -------------------
# MODE SWITCHING
# -------------------
#path('switch-mode/<str:mode>/', switch_mode, name='switch_mode'),
path('switch-role/', switch_role, name='switch_role'),

    # -------------------
    # PROFILE
    # -------------------
    path('profile/edit/', MembersProfileUpdateView.as_view(), name='profile-edit'),
path('profile/', SmartProfileView.as_view(), name='my-profile'),

    # -------------------
    # USERS
    # -------------------
    path('users/', UserListView.as_view(), name='user_list'),
# ✅ ADD EDIT USER
path('users/<int:pk>/edit/', UserUpdateView.as_view(), name='user-edit'),

# ✅ ADD DELETE USER
path('users/<int:pk>/delete/', UserDeleteView.as_view(), name='user-delete'),
    # -------------------
    # DASHBOARDS (CBVs ONLY)
    # -------------------
    path('officer/', OfficerDashboardView.as_view(), name='officer-dashboard'),
    path('manager/', ManagerDashboardView.as_view(), name='manager-dashboard'),
    path('ordinarymember/', CustomerDashboardView.as_view(), name='customer-dashboard'),
   #path('auditor/', AuditorDashboardView.as_view(), name='auditor-dashboard'),
   # path('verifier/', VerifierDashboardView.as_view(), name='verifier-dashboard'),
    path('secretary/', SecretaryDashboardView.as_view(), name='secretary-dashboard'),
    path('itadmin/', ITDashboardView.as_view(), name='itadmin-dashboard'),

    # -------------------
    # PASSWORD RESET
    # -------------------
    path('password-reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),

    # -------------------
    # MEMBER ACCOUNTS
    # -------------------
    path('memberaccounts/', MemberAccountListView.as_view(), name='member_account-list'),
    path('memberaccounts/create/', MemberAccountCreateView.as_view(), name='member_account-create'),
    path('memberaccounts/<int:pk>/', MemberAccountDetailView.as_view(), name='member_account-detail'),
    path('memberaccounts/<int:pk>/update/', MemberAccountUpdateView.as_view(), name='member_account-update'),
    path('memberaccounts/actions/', MemberAccountActionView.as_view(), name='member_account-actions'),

    # -------------------
    # ACCOUNT ACTIONS
    # -------------------
    path('memberaccounts/<int:pk>/suspend/', SuspendAccountView.as_view(), name='suspend_account'),
    path('memberaccounts/<int:pk>/close/', CloseAccountView.as_view(), name='close_account'),
    path('memberaccounts/<int:pk>/activate/', ActivateAccountView.as_view(), name='activate_account'),
    path('memberaccounts/<int:pk>/dormant/', DormantAccountView.as_view(), name='dormant_account'),

    # -------------------
    # SNAPSHOTS
    # -------------------
    path('snapshots/', SnapshotListView.as_view(), name='snapshot-list'),

    # -------------------
    # SJP2 ACCOUNTS
    # -------------------
    path('sjp2/actions/', Sjp2AccountActionView.as_view(), name='ssjp2_account-actions'),
    path('sjp2/create-profile/', SJP2ProfileCreateView.as_view(), name='sjp2create_profile'),
    path('sjp2/profile-success/', ProfileSuccessView.as_view(), name='profile_success'),

    path('sjp2-accounts/create/', SJP2AccountCreateView.as_view(), name='sjp2account-create'),
    path('sjp2-accounts/<int:pk>/', SJP2AccountDetailView.as_view(), name='sjp2account-detail'),
    path('sjp2-accounts/<int:pk>/update/', SJP2AccountUpdateView.as_view(), name='sjp2account-update'),
    path('sjp2-accounts/<int:pk>/delete/', SJP2AccountDeleteView.as_view(), name='sjp2account-delete'),

    # -------------------
    # SUCCESS PAGE
    # -------------------
    path('success/', TemplateView.as_view(
        template_name='accounts/Registration_success.html'
    ), name='Register-success'),

]