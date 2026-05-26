from django.urls import path

from bakery.views.dashboard import DashboardView

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
]
