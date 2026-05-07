from django.urls import path
from .views import (
    TellerTransactionSearchView,
    TellerDepositCreateView,
    WithdrawalCreateView,
    TransferCreateView,
    SJP2TransactionListView,
    SJP2TransactionDetailView,
    ExternalIncomeCreateView,
    ExpenseCreateView)
from django.views.generic import TemplateView

app_name = 'transact1_regular_deposit'

urlpatterns = [
    # ----- Deposit -----
    path('deposit/search/', TellerTransactionSearchView.as_view(
        action_url_name='transact1_regular_deposit:deposit',
        button_text='Deposit',   button_color='success',   title='Deposit – Search Member'), name='teller-deposit-search'),
    path('deposit/<int:account_id>/', TellerDepositCreateView.as_view(), name='deposit'),

    # ----- Withdrawal -----
    path('withdraw/search/', TellerTransactionSearchView.as_view(
        action_url_name='transact1_regular_deposit:withdraw',
        button_text='Withdraw',      button_color='danger',
        title='Withdrawal – Search Member'  ), name='teller-withdraw-search'),
    path('withdraw/<int:account_id>/', WithdrawalCreateView.as_view(), name='withdraw'),

    # ----- Transfer -----
    path('transfer/search/', TellerTransactionSearchView.as_view(
        action_url_name='transact1_regular_deposit:transfer',    button_text='Transfer',
        button_color='info',   title='Transfer – Search Member' ), name='teller-transfer-search'),
    path('transfer/<int:account_id>/', TransferCreateView.as_view(), name='transfer'),

    # ----- Transaction Success -----
    path('success/', TemplateView.as_view(template_name='transact1_regular_deposit/transaction_success.html'), name='transaction-success'),
    path('successIn_EXp/', TemplateView.as_view(template_name='transact1_regular_deposit/transaction_success.html'),
         name='transaction-success'),

    # ----- History -----
      # ----- Transactions List & Detail -----
    path('transactions/', SJP2TransactionListView.as_view(), name='transaction_list'),
    path('transactions/<int:pk>/', SJP2TransactionDetailView.as_view(), name='transaction_detail'),

    # ----- Other Financial Operations -----
    path('external-income/', ExternalIncomeCreateView.as_view(), name='external-income-create'),
    path('record-expense/', ExpenseCreateView.as_view(), name='record-expense'),
]
