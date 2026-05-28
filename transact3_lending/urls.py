# peerloans/urls.py
from django.urls import path
from .views import (
    PeerToPeerLoanCreateView,    PeerToPeerLoanListView,   PeerLoanRepaymentView,LendingStatusView,
    PeerLendingStatusView, PeerToPeerLoanDetailView, PeerLoanContractDownloadView,BorrowerLoanListView,
    MultiLoanRepaymentView, BorrowerLoanListSearchView)

app_name = "transact3_lending"

urlpatterns = [
    path('create/', PeerToPeerLoanCreateView.as_view(), name='peer_create'),
    path('loans/', PeerToPeerLoanListView.as_view(), name='peer_loan_list'),
    path('repay/<int:pk>/', PeerLoanRepaymentView.as_view(), name='peer_repayment'),
    path('status/', PeerLendingStatusView.as_view(), name='peer_status'),
path('lending-status/', LendingStatusView.as_view(), name='peer_lending-status'),
path('loan/<int:pk>/', PeerToPeerLoanDetailView.as_view(), name='peer_loan_detail'),
    path('multi-repayment/', MultiLoanRepaymentView.as_view(), name='multi_repayment'),  # Multi-repayment view
path('loan/<int:pk>/download-contract/', PeerLoanContractDownloadView.as_view(), name='contract_download'),
    path('borrower-summary/', BorrowerLoanListView.as_view(), name='borrower_lender_summary'),
      path('borrower-Search/',BorrowerLoanListSearchView.as_view(), name='borrower_lender_Search'),
]
