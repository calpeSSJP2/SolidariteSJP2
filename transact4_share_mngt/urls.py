from django.urls import path
from .views import ShareIncreaseView, ShareDecreaseView,ShareHistoryView,ShareTransactionSearchView,ShareTransactionReportView
from django.views.generic import TemplateView

app_name = 'transact4_share_mngt'

urlpatterns = [

   ## path('increase/', ShareIncreaseView.as_view(), name='make_increase'),
   ## path('decrease/',  ShareDecreaseView.as_view(), name='make_decrease'),
    path('success/', TemplateView.as_view(template_name='transact4_share_mngt/transaction_share_success.html'), name='share_transaction-success'),
path('history/', ShareHistoryView.as_view(), name='transaction-history'),
    # 🔎 Search for share increase
    path(  'increase/search/',  ShareTransactionSearchView.as_view(
            action_url_name='transact4_share_mngt:share-increase',
            button_text='Increase',
            button_color='success',
            title='Increase Shares – Search Member'  ),  name='share-increase-search'  ),

    # 🔎 Search for share decrease
    path( 'decrease/search/',  ShareTransactionSearchView.as_view(
            action_url_name='transact4_share_mngt:share-decrease',
            button_text='Decrease',
            button_color='danger',
            title='Decrease Shares – Search Member' ),   name='share-decrease-search'  ),

    # 📌 Perform increase
    path('increase/<int:account_id>/',  ShareIncreaseView.as_view(),   name='share-increase' ),

    # 📌 Perform decrease
    path('decrease/<int:account_id>/',  ShareDecreaseView.as_view(),   name='share-decrease' ),
    ##Report
path( "share-report/",  ShareTransactionReportView.as_view(), name="share_trans_report"),
]