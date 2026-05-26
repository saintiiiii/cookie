import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = require_secret_key(debug=False)  # noqa: F405

if "*" in ALLOWED_HOSTS or not ALLOWED_HOSTS:  # noqa: F405
    raise ImproperlyConfigured("Set DJANGO_ALLOWED_HOSTS to explicit hostnames in production.")

if not CSRF_TRUSTED_ORIGINS:  # noqa: F405
    raise ImproperlyConfigured("Set DJANGO_CSRF_TRUSTED_ORIGINS to the HTTPS origins that serve this site.")

SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", True)  # noqa: F405
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", True)  # noqa: F405
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)  # noqa: F405
SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 31_536_000)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", True)  # noqa: F405
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)  # noqa: F405
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

if os.environ.get("DJANGO_SECURE_PROXY_SSL_HEADER", "True").lower() == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not TRUSTED_PROXY_IPS:  # noqa: F405
    raise ImproperlyConfigured("Set DJANGO_TRUSTED_PROXY_IPS to the reverse proxy IPs allowed to supply X-Forwarded-For.")

if os.environ.get("MYSQL_DB") and os.environ.get("MYSQL_PASSWORD", "") in {"", "change-me"}:
    raise ImproperlyConfigured("MYSQL_PASSWORD must be supplied from a secret manager in production.")

if os.environ.get("POSTGRES_DB") and os.environ.get("POSTGRES_PASSWORD", "") in {"", "change-me"}:
    raise ImproperlyConfigured("POSTGRES_PASSWORD must be supplied from a secret manager in production.")
