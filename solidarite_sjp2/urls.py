from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # Main app routes
    path('', include(('accounts.urls', 'accounts'), namespace='accounts')),
    # Transactions app for deposits, withdrawals, etc.
    path('transactions1/', include('transact1_regular_deposit.urls', namespace='transact1_regular_deposit')),
    # Loan apps
    path('loan/', include('transact2_loans.urls', namespace='transact2_loans')),
    path('peerloans/', include('transact3_lending.urls', namespace='transact3_lending')),
    # Shares and distributions
    path('shares/', include('transact4_share_mngt.urls', namespace='transact4_share_mngt')),
    path('distributions/', include('transact5_share_distrib.urls', namespace='transact5_share_distrib')),
    # Meetings
    path('meetings/', include(('meeting_Mngt.urls', 'meeting_Mngt'), namespace='meeting_Mngt')),
    # ✅ Ledger app
    path('ledger/', include(('ledger.urls', 'ledger'), namespace='ledger')),
    # ✅ Leadership / Governance app
    path('governa/', include(('governance.urls', 'governance'), namespace='governance')),
]
