from django.urls import path
from marketing_rep.views import ReportsView, DashboardView, TaskView, ProfileView


urlpatterns = [
    path("reports/", ReportsView.as_view(), name="reports"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("tasks/", TaskView.as_view(), name="tasks"),
    path("profile/", ProfileView.as_view(), name="profile"),
]
