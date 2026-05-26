from django.urls import path

from bakery.views.audit import ActivityLogListView, LoginHistoryListView

urlpatterns = [
    path("audit/activity/", ActivityLogListView.as_view(), name="activity-logs"),
    path("audit/logins/", LoginHistoryListView.as_view(), name="login-history"),
]
