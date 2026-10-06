# CUSTODE Operations Runbook

## 1. Daily Operations & Routine Tasks

### Health Monitoring
Execute periodic automated health checks:
- **Liveness:** `GET /health/live` (Checks process health, returns 200).
- **Readiness:** `GET /health/ready` (Checks database connectivity and migration currency, returns 200 or 503).
- **Metrics:** `GET /health/metrics` (Reports uptime, environment, and database state).

### Monitoring Alerts Baseline
| Metric / Check | Alert Condition | Severity | Action |
|---|---|---|---|
| Liveness Probe | HTTP != 200 for 3 consecutive checks | Critical | Process crashed or deadlocked; restart container. |
| Readiness Probe | HTTP != 200 for 2 consecutive checks | High | Database connection severed or migrations out of sync. |
| Memory Usage | Container RSS > 85% of limit | Warning | Inspect memory leaks or high payload batches. |
| Ingress 413s | Rate > 10 / min | Warning | Potential payload flooding or oversized requests. |
| Login 429s | Rate > 20 / min | Warning | Potential brute force attack in progress. |

---

## 2. Log Analysis & Observability

### Log Location & Format
Application logs are formatted as structured JSON containing correlation request IDs:
- Format: `{"timestamp": "...", "level": "INFO", "event": "...", "request_id": "...", "outcome": "SUCCESS", "details": {...}}`
- In Docker: `docker logs -f custode-backend-prod`
- In Reverse Proxy: `docker logs -f custode-proxy-prod`

### Tracing a Request
Every HTTP response carries the `X-Request-ID` header. Search backend logs for any reported error:

```bash
docker logs custode-backend-prod 2>&1 | grep "cst_req_12345678"
```

---

## 3. Incident Playbooks

### Playbook 1: Database Connection Pool Exhaustion (HTTP 503)
**Symptoms:** Readiness probe returns 503 `Database connection unavailable`; backend logs report `TimeoutError: QueuePool limit exceeded`.

**Remediation Steps:**
1. Check active database connections in PostgreSQL:
   ```sql
   SELECT count(*), state FROM pg_stat_activity GROUP BY state;
   ```
2. Identify slow-running queries:
   ```sql
   SELECT pid, now() - query_start AS duration, query FROM pg_stat_activity WHERE state != 'idle' ORDER BY duration DESC;
   ```
3. Terminate stuck connections if necessary:
   ```sql
   SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid = <pid>;
   ```
4. Adjust pool parameters in `.env` if sustained traffic demands higher capacity:
   ```env
   DATABASE_POOL_SIZE=20
   DATABASE_MAX_OVERFLOW=30
   ```
5. Reload backend: `docker compose -f docker-compose.prod.yml restart backend`.

---

### Playbook 2: Webhook Delivery Backlog
**Symptoms:** Anomaly notifications or security audit webhooks are delayed.

**Remediation Steps:**
1. Check delivery attempts and failure logs:
   ```sql
   SELECT status, count(*) FROM webhook_deliveries GROUP BY status;
   ```
2. Verify target endpoint reachability and TLS validity.
3. Review dead-letter deliveries and retry failed payloads via administrative API.
