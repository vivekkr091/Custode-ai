# CUSTODE Database Migrations & Backup Runbook

## 1. Migration Architecture & History

CUSTODE utilizes Alembic to manage deterministic, version-controlled schema migrations for PostgreSQL (production) and SQLite (testing).

### Migration Lineage (0001 to 0018)

| Revision | Name | Key Tables Created / Modified |
|---|---|---|
| `0001` | `initial_schema` | `organizations`, `users`, `memberships` |
| `0002` | `add_agents` | `agents` |
| `0003` | `add_agent_credentials` | `agent_credentials` |
| `0004` | `add_tools_and_tool_operations` | `tools`, `tool_operations` |
| `0005` | `add_permissions` | `permissions` |
| `0006` | `add_policies_and_policy_versions` | `policies`, `policy_versions` |
| `0007` | `add_runtime_actions` | `runtime_actions` |
| `0008` | `add_risk_assessments` | `risk_assessments` |
| `0009` | `add_decisions` | `decisions` |
| `0010` | `add_approvals` | `approval_requests` |
| `0011` | `add_executions` | `executions` |
| `0012` | `add_auth_and_audit` | `audit_events` |
| `0013` | `add_security_audit_events` | Enhanced security audit fields |
| `0014` | `add_security_findings_and_scans` | `security_scans`, `security_findings` |
| `0015` | `add_llm_interactions` | `llm_interactions` |
| `0016` | `add_mcp_tables` | `mcp_servers`, `mcp_tools`, `mcp_prompts`, `mcp_resources` |
| `0017` | `add_behavior_tables` | `agent_behavior_baselines`, `behavioral_anomalies` |
| `0018` | `add_integrations_and_webhooks` | `integrations`, `webhook_deliveries` |

---

## 2. Production Migration Execution

### Pre-Migration Checklist
1. Verify database is reachable using the readiness probe: `python scripts/wait_for_db.py`.
2. Take a point-in-time snapshot backup before applying migrations.
3. Review pending migrations with Alembic current check.

### Executing Migrations
Execute forward upgrade to latest head revision:

```bash
# Using the dedicated migration script
python scripts/migrate.py

# Or via Docker Compose migration service
docker compose -f docker-compose.prod.yml run --rm migration
```

### Migration Verification
Verify that the `alembic_version` table matches the expected head revision:

```sql
SELECT version_num FROM alembic_version;
```

---

## 3. Database Backup Procedures

### Automated Backup Script
CUSTODE provides a dedicated backup and restore tool: `scripts/backup_restore.py`.

```bash
# PostgreSQL Backup
python scripts/backup_restore.py backup "$DATABASE_URL" /backups/custode_backup_$(date +%Y%m%d_%H%M%S).dump

# SQLite Backup (for testing/local development)
python scripts/backup_restore.py backup custode.db /backups/custode_backup.db
```

### Native PostgreSQL Backup (pg_dump)
```bash
pg_dump \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file=/backups/custode_$(date +%Y%m%d_%H%M%S).dump \
  "$DATABASE_URL"
```

---

## 4. Restoration & Recovery Procedure

### Disaster Recovery Restore
1. Stop backend services to halt writes:
   ```bash
   docker compose -f docker-compose.prod.yml stop backend
   ```
2. Restore database from verified backup:
   ```bash
   python scripts/backup_restore.py restore /backups/custode_backup_<timestamp>.dump "$DATABASE_URL"
   ```
3. Run readiness check to verify data integrity:
   ```bash
   python scripts/wait_for_db.py
   ```
4. Restart application services:
   ```bash
   docker compose -f docker-compose.prod.yml up -d backend
   ```
