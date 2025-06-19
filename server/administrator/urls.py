from django.urls import path
from administrator.views import (
    FabricatorView,
    MarketingRepresentativeView,
    DistributorView,
)


urlpatterns = [
    path("fabricator/", FabricatorView.as_view(), name="fabricator-view"),
    path(
        "marketing-representative/",
        MarketingRepresentativeView.as_view(),
        name="marketing-representative-view",
    ),
    path("distributor/", DistributorView.as_view(), name="distributor-view"),
]
