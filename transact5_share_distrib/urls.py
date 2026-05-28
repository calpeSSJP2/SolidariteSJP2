from django.urls import path
from .views import ( InterestPoolCreateView, InterestPoolListView, InterestPoolDetailView,
    DistributeInterestView,InterestPoolExportExcelView,
ApproveInterestPoolView,  # 👈 ADD THIS
)

app_name = "transact5_share_distrib"

urlpatterns = [
    path("", InterestPoolListView.as_view(), name="pool-list"),
    path("<int:pk>/", InterestPoolDetailView.as_view(), name="pool-detail"),
    path("create/", InterestPoolCreateView.as_view(), name="pool-create"),
    path("<int:pk>/distribute/", DistributeInterestView.as_view(), name="distribute"),
# ✅ NEW: manager approval
    path("<int:pk>/approve/", ApproveInterestPoolView.as_view(), name="approve"),
    path( "pool/<int:pk>/export-excel/",  InterestPoolExportExcelView.as_view(),
        name="pool-export-excel" ),
]