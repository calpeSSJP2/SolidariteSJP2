from django.urls import path

from .views import (LoanWorkflowDetailView,LoanWorkflowDashboardView,MoveLoanStageView,
    LoanDetailView, TopUpLoanCreateView,EmergencyLoanRequestView,LoanOptionsView,  LoanPaymentView, LoanListView,MemberLoanListView,LoanRequestView,
    ApproveLoanView,RejectLoanView,LoanSummaryView, LoanTypeSummaryView, TellerAccountSearchView,PendingLoanView,
    LoanPaymentSearchView,LoanPaymentListView, LoanActionView)
from django.views.generic import TemplateView
app_name = 'transact2_loans'
urlpatterns = [
    # List of all loans
    path('loans/', LoanListView.as_view(), name='loan_list'),
    path('success/', TemplateView.as_view(template_name='transact2_loans/transaction_success.html'),
         name='transaction-success'),

    # List of loans by a specific member
    path('loans/member/', MemberLoanListView.as_view(), name='member_loan_list'),

    # Member search for loan requests
    path('loan-request/member-search/', TellerAccountSearchView.as_view(), name='loan_member_search'),

    # Loan request creation for a specific account (note: acc_id is required) if you use int:account_id, paased in views if you use int:acc_id, use acc_id
    path('loan-request/<int:account_id>/', LoanRequestView.as_view(), name='loan_create'),
# Loan payment list (all performed payments)
path('loan-payments/',  LoanPaymentListView.as_view(),  name='loan_payment_list'),

    # Loan action (approve/reject) for a member, by member ID
    path('loan/action/<int:account_id>/', LoanActionView.as_view(), name='loan_action'),

    # Loan details (view a specific loan by its pk)
    path('loans/<int:pk>/', LoanDetailView.as_view(), name='loan_detail'),
path('loans/pending/', PendingLoanView.as_view(), name='pending_loans'),

    # Loan payment for a specific member account, use <loan_id>
    path('loan-payment/<int:member_account>/', LoanPaymentView.as_view(), name='loan_payment'),
#path('loan-payment/<int:loan_id>/', LoanPaymentView.as_view(), name='loan_payment'),
    # Search loan payment details
    path('loan-payment/search/', LoanPaymentSearchView.as_view(), name='loan_payment_search'),

    # Top-up loan for a specific loan (using loan_id)
    path('loans/<int:loan_id>/topup/', TopUpLoanCreateView.as_view(), name='loan_topup'),

    ##emergeny Loan
path( 'loan-request/<int:account_id>/emergency/', EmergencyLoanRequestView.as_view(),
    name='loan_create_emergency'),

    # Approve loan for a specific loan (using loan_id)
    path('loans/<int:loan_id>/approve/', ApproveLoanView.as_view(), name='loan_approve'),

    # Reject loan for a specific loan (using loan_id)
    path('loans/<int:loan_id>/reject/', RejectLoanView.as_view(), name='loan_reject'),

    # Loan summary for a specific loan (using pk)
    path('loan/<int:pk>/summary/', LoanSummaryView.as_view(), name='loan_summary'),

    # Loan type summary (general overview of loan types)
    path('loan-type-summary/', LoanTypeSummaryView.as_view(), name='loan_type_summary'),
path('loan/options/<int:account_id>/',  LoanOptionsView.as_view(),   name='loan_options'),
# Loan workflow)
path( "workflow/<int:loan_id>/",LoanWorkflowDetailView.as_view(),  name="workflow-detail"),
    path( "workflow/move/<int:workflow_id>/",   MoveLoanStageView.as_view(), name="workflow-move" ),
    path( "workflow/dashboard/", LoanWorkflowDashboardView.as_view(),  name="workflow-dashboard" ),
]