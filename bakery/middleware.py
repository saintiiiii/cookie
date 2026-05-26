from django.shortcuts import redirect
from django.urls import reverse

from bakery.models import EmployeeSecurity


class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._must_redirect_to_password_change(request):
            return redirect("force-password-change")
        return self.get_response(request)

    def _must_redirect_to_password_change(self, request):
        user = request.user
        if not getattr(user, "is_authenticated", False):
            return False

        allowed_paths = {
            reverse("force-password-change"),
            reverse("logout"),
        }
        if request.path in allowed_paths or request.path.startswith("/static/") or request.path.startswith("/media/"):
            return False

        security, _created = EmployeeSecurity.objects.get_or_create(user=user)
        return security.must_change_password
