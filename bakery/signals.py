from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import ActivityLog, LoginHistory
from .services import log_activity


def _client_ip(request):
    if not request:
        return None
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _user_agent(request):
    if not request:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")[:255]


@receiver(user_logged_in)
def record_login(sender, request, user, **kwargs):
    LoginHistory.objects.create(
        user=user,
        username=user.get_username(),
        action=LoginHistory.ACTION_LOGIN,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    log_activity(
        user=user,
        action=ActivityLog.ACTION_LOGIN,
        description="User logged in.",
        ip_address=_client_ip(request),
    )


@receiver(user_logged_out)
def record_logout(sender, request, user, **kwargs):
    LoginHistory.objects.create(
        user=user if user and user.is_authenticated else None,
        username=user.get_username() if user else "",
        action=LoginHistory.ACTION_LOGOUT,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
    log_activity(
        user=user,
        action=ActivityLog.ACTION_LOGOUT,
        description="User logged out.",
        ip_address=_client_ip(request),
    )


@receiver(user_login_failed)
def record_failed_login(sender, credentials, request, **kwargs):
    username = credentials.get("username", "")
    LoginHistory.objects.create(
        username=username,
        action=LoginHistory.ACTION_FAILED,
        ip_address=_client_ip(request),
        user_agent=_user_agent(request),
    )
