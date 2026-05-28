from django.urls import path
from .views import AccountStatementCreateView, AccountStatementListView, ExportTransactionsExcelView

urlpatterns = [
    path('statements/create/', AccountStatementCreateView.as_view(), name='create_account_statement'),
    path('statements/', AccountStatementListView.as_view(), name='account_statement_list'),
path('export/excel/', ExportTransactionsExcelView.as_view(), name='export_transactions_excel'),
]
