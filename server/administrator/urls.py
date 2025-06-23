from django.urls import path
from administrator.views import (
    FabricatorView,
    MarketingRepresentativeView,
    DistributorView,
    ReportView,
    DashboardView,
)


urlpatterns = [
    path("fabricator/", FabricatorView.as_view(), name="fabricator-view"),
    path(
        "marketing-representative/",
        MarketingRepresentativeView.as_view(),
        name="marketing-representative-view",
    ),
    path("distributor/", DistributorView.as_view(), name="distributor-view"),
    path("report/", ReportView.as_view(), name="report-view"),
    path("dashboard/", DashboardView.as_view(), name="dashboard-view"),
]
