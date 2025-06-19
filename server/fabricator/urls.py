from django.urls import path
from fabricator.views import FabricatorView


urlpatterns = [
    path("fabricator/", FabricatorView.as_view(), name="fabricator-view"),
]
