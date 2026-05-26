Act as a senior Django security engineer and penetration-testing-focused backend architect.

Your task is to analyze and fully remediate the following Django security vulnerabilities while preserving system functionality and production stability.

SYSTEM SECURITY FINDINGS:

6. Security Vulnerabilities

Severity: Critical
Vulnerability: Insecure defaults (development secret key, DEBUG=True, wildcard ALLOWED_HOSTS)
Risk: Data exposure, request spoofing, environment compromise
Required Fix:
- Create production-grade settings separation
- Enforce environment validation
- Remove insecure defaults
- Harden deployment configuration

Severity: Critical
Vulnerability: Possible plaintext credential inside README or repository files
Risk: Account compromise and credential leakage
Required Fix:
- Detect exposed secrets
- Remove credentials from source
- Recommend secret rotation process
- Implement .env-based secret management

Severity: High
Vulnerability: SQLite restore upload allows full database replacement
Risk: Complete application compromise through admin/session hijack
Required Fix:
- Remove direct DB upload restore functionality
- Replace with controlled maintenance/admin process
- Add signed backups and verification
- Restrict dangerous operations

Severity: High
Vulnerability: Missing secure cookie and security header configuration
Risk: Session theft, clickjacking, insecure transport
Required Fix:
- Configure:
  - SECURE_SSL_REDIRECT
  - SESSION_COOKIE_SECURE
  - CSRF_COOKIE_SECURE
  - SECURE_HSTS_SECONDS
  - SECURE_HSTS_INCLUDE_SUBDOMAINS
  - SECURE_HSTS_PRELOAD
  - X_FRAME_OPTIONS
  - SECURE_BROWSER_XSS_FILTER
  - SECURE_CONTENT_TYPE_NOSNIFF
- Explain production proxy considerations

Severity: Medium
Vulnerability: No login/password reset rate limiting
Risk: Brute-force attacks and email abuse
Required Fix:
- Add django-axes or equivalent
- Add throttling and lockouts
- Add audit logging
- Add suspicious activity detection

Severity: Medium
Vulnerability: Trusts X-Forwarded-For directly inside views.py line 82
Risk: Spoofed audit logs and fake client IPs
Required Fix:
- Remove direct header trust
- Use secure proxy middleware
- Use validated client IP extraction
- Configure trusted reverse proxies only

Severity: Low
Vulnerability: Potential SQL injection exposure
Risk: Unsafe future development
Current Status:
- ORM currently used correctly
Required Fix:
- Audit raw SQL usage
- Add validation and sanitization patterns
- Add secure query guidelines
- Prevent future unsafe raw SQL implementations

REQUIREMENTS:
- Think like a strict enterprise security auditor
- Explain every vulnerability clearly
- Explain attack scenarios
- Show secure implementation examples
- Generate production-ready Django fixes
- Follow OWASP best practices
- Follow Django security recommendations
- Preserve application functionality
- Avoid breaking migrations unless necessary

GENERATE:
1. Full security audit explanation
2. Step-by-step remediation plan
3. Secure Django settings examples
4. Secure middleware recommendations
5. Secure authentication hardening
6. Secure deployment recommendations
7. Reverse proxy hardening recommendations
8. Environment variable architecture
9. Secure logging recommendations
10. Secure backup/restore architecture
11. Example code patches
12. Before/after vulnerable code examples
13. Security checklist for production deployment

ALSO INCLUDE:
- Recommended packages
- Required pip installs
- .env structure example
- Production-ready settings split
- Secure nginx/gunicorn recommendations
- Admin hardening recommendations
- CSRF/session protection
- File upload security
- Secure backup strategy
- Secret rotation process

OUTPUT FORMAT:
1. Executive Security Summary
2. Critical Vulnerabilities
3. High Severity Vulnerabilities
4. Medium Severity Vulnerabilities
5. Low Severity Vulnerabilities
6. Exact Code Fixes
7. Secure Architecture Recommendations
8. Deployment Hardening
9. Final Security Checklist
10. Enterprise Production Security Structure