from django.urls import path
from marketing_rep.views import ReportsView


urlpatterns = [
    path("reports/", ReportsView.as_view(), name="reports"),
]
