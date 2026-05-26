from django.urls import path

from bakery.views.auth import (
    BakeryLoginView,
    BakeryLogoutView,
    BakeryPasswordResetCompleteView,
    BakeryPasswordResetConfirmView,
    BakeryPasswordResetDoneView,
    BakeryPasswordResetView,
    EmployeeCreateView,
    EmployeeDeleteView,
    EmployeeListView,
    EmployeePasswordResetView,
    EmployeeUpdateView,
    ForcePasswordChangeView,
    archive_employee_view,
)

urlpatterns = [
    path("login/", BakeryLoginView.as_view(), name="login"),
    path("logout/", BakeryLogoutView.as_view(), name="logout"),
    path("password-reset/", BakeryPasswordResetView.as_view(), name="password-reset"),
    path("password-reset/done/", BakeryPasswordResetDoneView.as_view(), name="password-reset-done"),
    path("password-reset/<uidb64>/<token>/", BakeryPasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("password-reset/complete/", BakeryPasswordResetCompleteView.as_view(), name="password-reset-complete"),
    path("password-change-required/", ForcePasswordChangeView.as_view(), name="force-password-change"),
    path("employees/", EmployeeListView.as_view(), name="employee-list"),
    path("employees/add/", EmployeeCreateView.as_view(), name="employee-add"),
    path("employees/<int:pk>/edit/", EmployeeUpdateView.as_view(), name="employee-edit"),
    path("employees/<int:pk>/archive/", archive_employee_view, name="employee-archive"),
    path("employees/<int:pk>/delete/", EmployeeDeleteView.as_view(), name="employee-delete"),
    path("employees/<int:pk>/password/", EmployeePasswordResetView.as_view(), name="employee-password-reset"),
]
