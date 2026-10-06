# CUSTODE Environment & Secret Management Specification

## 1. Environment Variable Reference

| Variable | Type | Default | Required in Production | Description |
|---|---|---|---|---|
| `ENVIRONMENT` | string | `development` | Yes | Deployment environment (`development`, `staging`, `production`). |
| `DEBUG` | boolean | `true` | Yes (`false`) | Enables verbose debug output. **Must be false in production**. |
| `LOG_LEVEL` | string | `INFO` | No | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `SECRET_KEY` | string | *dev placeholder* | Yes | Cryptographic HMAC and data encryption key. **Min 32 characters**. |
| `AUTH_SECRET_KEY` | string | *dev placeholder* | Yes | JWT token signing key. **Min 32 characters**. |
| `AUTH_MODE` | string | `development` | Yes (`production`) | Human authentication mode. Set to `production` for strict credentials. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | integer | `60` | No | Lifetime of user JWT tokens in minutes. |
| `DATABASE_URL` | string | *dev postgres url* | Yes | Async SQLAlchemy connection URL for PostgreSQL. |
| `DATABASE_POOL_SIZE` | integer | `10` | No | SQLAlchemy async engine persistent connection pool size. |
| `DATABASE_MAX_OVERFLOW` | integer | `20` | No | Maximum burst connections beyond pool size. |
| `DATABASE_POOL_TIMEOUT` | integer | `30` | No | Seconds to wait before timing out on connection pool exhaustion. |
| `DATABASE_POOL_RECYCLE` | integer | `1800` | No | Maximum connection age in seconds (prevents stale TCP connections). |
| `CORS_ORIGINS` | JSON list | `["http://localhost:5173"]`| Yes | Allowed CORS origin URLs. Never use `["*"]` in production. |
| `FORWARDED_ALLOW_IPS` | string | `*` | Yes | Trusted reverse-proxy IP addresses for forwarded headers. |
| `MAX_REQUEST_BODY_BYTES` | integer | `10485760` (10MB) | No | Global ingress body size cap before triggering HTTP 413. |

---

## 2. Production Secret Rules & Validation

When `ENVIRONMENT` is set to `production`, `prod`, or `staging`, the platform startup validation enforces the following strict constraints:

1. **Insecure Secret Rejection:**
   - Any `SECRET_KEY` containing `"dev-secret"` or shorter than 32 characters immediately halts process startup with a fatal `ValueError`.
   - Any `AUTH_SECRET_KEY` containing `"dev-auth"` or shorter than 32 characters halts process startup.
2. **Debug Mode Prohibition:**
   - `DEBUG=true` raises `ValueError("DEBUG mode must be set to False in production environment.")`.
3. **Auth Mode Enforcement:**
   - `AUTH_MODE="development"` is strictly rejected in production to prevent bypass via development seeded users.
4. **Credential Leak Prevention:**
   - The string `"custode_dev_password"` in `DATABASE_URL` is blocked.
5. **Log Redaction:**
   - Structured logging filters automatically redact passwords, API keys (`cst_*`), JWT tokens (`Bearer *`), and sensitive dictionary keys (`password`, `secret`, `webhook_secret`, `encryption_key`).

---

## 3. Secret Generation & Rotation Procedure

### Generation
Execute on a secure workstation or bastion host:

```bash
# Generate 256-bit hexadecimal secret
openssl rand -hex 32
```

### Rotation Procedure
1. **JWT Auth Secret Rotation:**
   - Deploy new `AUTH_SECRET_KEY` during a scheduled maintenance window or update token verification logic to support dual keys during rotation.
   - Active user sessions will expire after `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60 minutes) and require re-login.
2. **Database Password Rotation:**
   - Update user password in PostgreSQL: `ALTER USER custode WITH PASSWORD 'new_strong_password';`.
   - Update `DATABASE_URL` in `.env`.
   - Perform zero-downtime rolling restart: `docker compose -f docker-compose.prod.yml up -d --no-deps backend`.
