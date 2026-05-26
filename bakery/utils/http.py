from django.conf import settings


def _normalized_trusted_proxies():
    return {proxy.strip() for proxy in getattr(settings, "TRUSTED_PROXY_IPS", []) if proxy.strip()}


def client_ip(request):
    if not request:
        return None
    remote_addr = request.META.get("REMOTE_ADDR")
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for and remote_addr in _normalized_trusted_proxies():
        return forwarded_for.split(",")[0].strip()
    return remote_addr


def axes_client_ip(request):
    return client_ip(request)


def user_agent(request):
    if not request:
        return ""
    return request.META.get("HTTP_USER_AGENT", "")[:255]
