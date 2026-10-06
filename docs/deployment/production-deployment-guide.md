# CUSTODE Production Deployment Guide

## 1. Overview & Architecture

CUSTODE is a security-first AI Agent Security & Control Plane designed to govern, inspect, and enforce policies on agent tool calls, LLM interactions, and MCP boundary operations.

### High-Availability Production Architecture

```text
               INTERNET / INTERNAL VPC
                          |
                    [TLS / HTTPS]
                          v
         +--------------------------------+
         |     Reverse Proxy (Nginx)      |
         |  - TLS Termination             |
         |  - Security Headers (HSTS/CSP) |
         |  - Rate Limiting (50 r/s)      |
         |  - Ingress Body Cap (10 MB)    |
         +--------------------------------+
             /                        \
      /api/ & /health                   / (SPA Assets)
           v                              v
+-----------------------+     +-----------------------+
|   CUSTODE Backend     |     |   CUSTODE Frontend    |
| (FastAPI / Non-Root)  |     | (Nginx Non-Root / SPA)|
|   Port 8000           |     |   Port 8080           |
+-----------------------+     +-----------------------+
           |
     [Asyncpg Pool]
           v
+-----------------------+
|  PostgreSQL 16 DB     |
| (Isolated Network)    |
| Port 5432 (Internal)  |
+-----------------------+
```

---

## 2. Prerequisites

- **Hardware Requirements:**
  - Minimum: 2 vCPU, 4 GB RAM, 20 GB SSD storage.
  - Recommended: 4 vCPU, 8 GB RAM, 50 GB SSD storage.
- **Software Dependencies:**
  - Docker 24.0+ and Docker Compose v2.20+.
  - OpenSSL 1.1+ (for secret generation).
  - PostgreSQL 16+ (or managed cloud database such as AWS RDS / GCP Cloud SQL).
- **Network Boundaries:**
  - Ingress: Public ports 80 (HTTP) and 443 (HTTPS) exposed only via Reverse Proxy.
  - Internal: Backend (8000), Frontend (8080), and PostgreSQL (5432) isolated on private network `custode-internal-network`.

---

## 3. Step-by-Step Deployment Procedure

### Step 3.1: Clone and Configure Environment

```bash
cd /opt/custode
cp .env.example .env
chmod 600 .env
```

Generate production secrets:

```bash
# Generate SECRET_KEY
openssl rand -hex 32

# Generate AUTH_SECRET_KEY
openssl rand -hex 32

# Generate PostgreSQL strong password
openssl rand -base64 24
```

Populate `.env` with production values:
- `ENVIRONMENT=production`
- `DEBUG=false`
- `SECRET_KEY=<generated-key>`
- `AUTH_SECRET_KEY=<generated-key>`
- `AUTH_MODE=production`
- `DATABASE_URL=postgresql+asyncpg://<user>:<password>@postgres:5432/custode`
- `CORS_ORIGINS=["https://custode.yourdomain.com"]`

### Step 3.2: Verify Configuration Validity

Run configuration verification locally before startup:

```bash
docker compose -f docker-compose.prod.yml config
```

### Step 3.3: Execute Database Migrations

Run database migrations using the dedicated one-off migration container:

```bash
docker compose -f docker-compose.prod.yml run --rm migration
```

### Step 3.4: Launch Production Stack

```bash
docker compose -f docker-compose.prod.yml up -d
```

### Step 3.5: Health Verification

Verify service liveness and readiness:

```bash
# Liveness probe (HTTP 200)
curl -f http://localhost/health/live

# Readiness probe (HTTP 200, checks DB and migrations)
curl -f http://localhost/health/ready
```

Expected readiness output:
```json
{
  "status": "ready",
  "service": "custode-api",
  "checks": {
    "database": "connected",
    "migrations": "current"
  }
}
```

---

## 4. Graceful Shutdown & Zero-Downtime Updates

To stop services gracefully allowing current requests to drain:

```bash
docker compose -f docker-compose.prod.yml stop -t 30
```

To update application versions with zero downtime:
1. Pull new container images.
2. Run database migrations: `docker compose -f docker-compose.prod.yml run --rm migration`.
3. Perform rolling restart: `docker compose -f docker-compose.prod.yml up -d --no-deps backend`.
