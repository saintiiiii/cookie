# Enterprise Django Security Remediation

This report is based on the findings documented in `securityfix.md`.

## 1. Executive Security Summary

The application had audit findings around insecure deployment defaults, possible repository credential exposure, unsafe database restore upload behavior, missing transport/session headers, missing authentication throttling, untrusted `X-Forwarded-For` handling, and future SQL injection risk. The remediation hardens settings, removes direct database replacement from the web tier, sanitizes local secrets, adds `django-axes` throttling hooks, validates trusted proxies, and documents production deployment controls.

## 2. Vulnerabilities Detected

| Severity | Finding | Remediation status |
| --- | --- | --- |
| Critical | Development secret key, `DEBUG=True`, wildcard/unsafe host posture | Hardened settings split and production validation |
| Critical | Plaintext credential exposure in repository files | `.env` sanitized, `.env.example` added, rotation required |
| High | SQLite restore upload can replace the full database | Restore upload UI removed and endpoint blocked with `410 Gone` |
| High | Missing secure cookie and security headers | Secure production settings added |
| Medium | No login/password reset rate limiting | `django-axes` integration added |
| Medium | Direct trust of `X-Forwarded-For` | Trusted proxy validation added |
| Low | SQL injection exposure in future code | ORM-first guidance and raw SQL controls documented |

## 3. Critical Severity Findings

### Insecure Settings Defaults

Issue: `securityfix.md` identifies development secret key usage, `DEBUG=True`, and unsafe host configuration as critical. In production, these expose stack traces, cookies signed with known keys, and host-header abuse.

Attack scenario: An attacker probes a production error path, obtains debug output, poisons password-reset links through host-header manipulation, or forges signed values after a secret leak.

Secure replacement:

```python
DEBUG = False
SECRET_KEY = require_secret_key(debug=False)
if "*" in ALLOWED_HOSTS or not ALLOWED_HOSTS:
    raise ImproperlyConfigured("Set DJANGO_ALLOWED_HOSTS to explicit hostnames in production.")
if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured("Set DJANGO_CSRF_TRUSTED_ORIGINS to HTTPS origins.")
```

Deployment strategy: run WSGI/ASGI with `DJANGO_SETTINGS_MODULE=config.settings.production`; keep development defaults only in `config.settings.development`.

### Plaintext Credentials

Issue: `.env` contained secret-like values including a Django key and MySQL password. Even if `.env` is ignored now, any prior commit/share requires rotation.

Attack scenario: Anyone with repository, backup, chat, or artifact access reuses the database password or signs Django cookies/tokens.

Fixes: `.env` now contains blank local placeholders; `.env.example` documents structure without secrets.

Rotation process:

1. Generate a new `DJANGO_SECRET_KEY` and store it in the deployment secret manager.
2. Rotate database and SMTP credentials.
3. Invalidate existing sessions after secret rotation.
4. Remove leaked values from repo history if they were committed.
5. Review CI artifacts and backup archives for leaked copies.

## 4. High Severity Findings

### Unsafe Database Restore Upload

Issue: A web route accepted SQLite files and replaced the application database. This can overwrite users, sessions, permissions, and audit history.

Attack scenario: A compromised admin account uploads a database containing an attacker-controlled superuser/session, permanently taking over the app.

Before:

```python
with open(db_path, "wb") as destination:
    for chunk in uploaded.chunks():
        destination.write(chunk)
```

After:

```python
return HttpResponseGone(
    "Direct database restore uploads are disabled. Use the controlled maintenance restore process."
)
```

Production-safe workflow: restore only during a maintenance window using offline DB tooling, signed backups, hash verification, dual approval, immutable audit records, and post-restore credential/session invalidation.

### Missing Security Headers And Cookie Flags

Issue: The audit required HTTPS redirect, secure cookies, HSTS, frame protection, MIME sniffing protection, proxy SSL handling, and CSRF trusted origins.

Secure production settings:

```python
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
CSRF_TRUSTED_ORIGINS = ["https://app.example.com"]
```

Proxy note: enable `SECURE_PROXY_SSL_HEADER` only when the reverse proxy strips incoming spoofed forwarding headers and sets its own trusted values.

## 5. Medium Severity Findings

### Missing Authentication Throttling

Issue: Login and password reset endpoints had no lockout/rate-limit layer.

Attack scenario: Automated username/password guessing or high-volume password reset email abuse.

Implementation:

```python
INSTALLED_APPS = ["axes", ...]
MIDDLEWARE = [..., "axes.middleware.AxesMiddleware"]
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1
AXES_LOCKOUT_PARAMETERS = ["ip_address", "username"]
AXES_RESET_ON_SUCCESS = True
```

Benefits: scalable lockout storage, audit logging, and central policy controls.

### Spoofed `X-Forwarded-For`

Issue: `client_ip()` trusted `HTTP_X_FORWARDED_FOR` directly.

Before:

```python
if forwarded_for:
    return forwarded_for.split(",")[0].strip()
```

After:

```python
if forwarded_for and remote_addr in settings.TRUSTED_PROXY_IPS:
    return forwarded_for.split(",")[0].strip()
return remote_addr
```

Deployment strategy: configure `DJANGO_TRUSTED_PROXY_IPS` only with internal Nginx/load-balancer IPs.

## 6. Low Severity Findings

### SQL Injection Risk

Current status from `securityfix.md`: ORM is currently used correctly. The risk is future unsafe raw SQL.

Guidelines:

- Use Django ORM and forms/model validation by default.
- If raw SQL is unavoidable, use parameter binding, never string interpolation.
- Code review must reject `cursor.execute(f"...{value}...")`, `.extra()`, and concatenated SQL.
- Keep database users least-privileged.

## 7. Exact Code Fixes

Changed files:

- `config/settings/base.py`: environment parsing helpers, Axes app/backend/middleware, security logging, upload size limits, cookie defaults, CSRF trusted origins, trusted proxy list.
- `config/settings/production.py`: fail-closed validation, HTTPS/cookie/HSTS/header settings, proxy SSL header, database password validation.
- `config/settings/development.py`: explicit non-production security toggles and Axes disabled locally.
- `bakery/utils/http.py`: trusted-proxy client IP extraction and Axes IP callable.
- `bakery/views/__init__.py`: direct DB restore blocked and audit-logged.
- `bakery/templates/bakery/reports.html`: restore upload form removed.
- `requirements/base.txt`: `django-axes` added.
- `.env`: local secret values removed.
- `.env.example`: safe environment contract added.
- `README.md`: production and restore-security notes updated.

## 8. Secure Settings Refactor

Recommended structure:

```text
config/settings/base.py
config/settings/development.py
config/settings/production.py
```

Production runs:

```bash
DJANGO_SETTINGS_MODULE=config.settings.production
```

Development runs:

```bash
DJANGO_SETTINGS_MODULE=config.settings.development
```

## 9. Authentication Hardening

- Keep password complexity validator enabled.
- Use `django-axes` for failed-login throttling.
- Add reverse proxy/IP rate limiting for login and password reset paths.
- Log login success, failure, logout, and password reset completion.
- Consider MFA for admin/superuser accounts.

## 10. Infrastructure Hardening

Nginx recommendations:

```nginx
server {
    listen 443 ssl http2;
    server_name app.example.com;

    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header Referrer-Policy same-origin always;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;
    proxy_pass http://unix:/run/gunicorn/bakery.sock;
}
```

Gunicorn recommendations:

```bash
gunicorn config.wsgi:application \
  --bind unix:/run/gunicorn/bakery.sock \
  --workers 3 \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
```

## 11. Deployment Hardening

- Use a secret manager or protected environment variables; never commit `.env`.
- Run migrations before traffic cutover.
- Run `python manage.py check --deploy` in CI.
- Serve static/media files from Nginx or object storage, not Django.
- Set database users to least privilege.
- Restrict admin URL by VPN, SSO, IP allowlist, or MFA where feasible.

## 12. Production Security Checklist

- `DEBUG=False`
- Unique `DJANGO_SECRET_KEY` from secret manager
- Explicit `DJANGO_ALLOWED_HOSTS`
- Explicit HTTPS `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DJANGO_TRUSTED_PROXY_IPS` set to trusted internal proxies only
- `SECURE_SSL_REDIRECT=True`
- `SESSION_COOKIE_SECURE=True`
- `CSRF_COOKIE_SECURE=True`
- HSTS enabled after TLS validation
- `django-axes` migrations applied
- Restore uploads disabled
- Backups encrypted, signed, tested, and access-controlled
- Logs monitored for lockouts, failed logins, restore attempts, and suspicious admin activity

## 13. Final Enterprise Security Architecture

The secure target architecture is Django behind Nginx/Gunicorn with TLS termination at Nginx, sanitized forwarding headers, production settings that fail closed, secrets injected by the platform, Axes-backed authentication throttling, append-only audit/login history, no web-based database restore, least-privilege database credentials, encrypted verified backups, and CI/CD gates that run Django deployment checks before release.
