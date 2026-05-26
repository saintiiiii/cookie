from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import ActivityLog, LoginHistory
from .services import log_activity
from .utils.http import client_ip, user_agent as request_user_agent


@receiver(user_logged_in)
def record_login(sender, request, user, **kwargs):
    LoginHistory.objects.create(
        user=user,
        username=user.get_username(),
        action=LoginHistory.ACTION_LOGIN,
        ip_address=client_ip(request),
        user_agent=request_user_agent(request),
    )
    log_activity(
        user=user,
        action=ActivityLog.ACTION_LOGIN,
        description="User logged in.",
        ip_address=client_ip(request),
    )


@receiver(user_logged_out)
def record_logout(sender, request, user, **kwargs):
    LoginHistory.objects.create(
        user=user if user and user.is_authenticated else None,
        username=user.get_username() if user else "",
        action=LoginHistory.ACTION_LOGOUT,
        ip_address=client_ip(request),
        user_agent=request_user_agent(request),
    )
    log_activity(
        user=user,
        action=ActivityLog.ACTION_LOGOUT,
        description="User logged out.",
        ip_address=client_ip(request),
    )


@receiver(user_login_failed)
def record_failed_login(sender, credentials, request, **kwargs):
    username = credentials.get("username", "")
    LoginHistory.objects.create(
        username=username,
        action=LoginHistory.ACTION_FAILED,
        ip_address=client_ip(request),
        user_agent=request_user_agent(request),
    )
