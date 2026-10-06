# CUSTODE Disaster Recovery & Incident Response Guide

## 1. Disaster Recovery Objectives

- **Recovery Point Objective (RPO):** Maximum acceptable data loss duration = **1 hour** (supported by hourly automated WAL/snapshot backups).
- **Recovery Time Objective (RTO):** Maximum acceptable downtime to full service restoration = **15 minutes**.
- **Audit Preservation Guarantee:** Audit logs and security findings are tamper-resistant and must be replicated to offsite cold storage.

---

## 2. Recovery Scenarios

### Scenario A: Corrupted Primary Database
**Objective:** Restore database to the most recent known-good backup.

1. **Halt Incoming Writes:**
   ```bash
   docker compose -f docker-compose.prod.yml stop backend
   ```
2. **Verify Backup Integrity:**
   ```bash
   sha256sum -c /backups/custode_backup_<timestamp>.dump.sha256
   ```
3. **Execute Database Restore:**
   ```bash
   python scripts/backup_restore.py restore /backups/custode_backup_<timestamp>.dump "$DATABASE_URL"
   ```
4. **Execute Verification Probes:**
   ```bash
   python scripts/wait_for_db.py
   ```
5. **Resume Application Traffic:**
   ```bash
   docker compose -f docker-compose.prod.yml start backend
   ```

---

### Scenario B: Complete Host Failure (Cold Standby Reconstruction)
**Objective:** Stand up the full CUSTODE control plane on a new compute instance from version control and backups.

1. **Provision New Host:**
   - Linux instance with Docker 24.0+ and Docker Compose v2.20+.
2. **Retrieve Production Artifacts:**
   - Clone repository: `git clone https://github.com/organization/custode.git /opt/custode`.
   - Restore `.env` from secure secret manager (e.g. AWS Secrets Manager / HashiCorp Vault).
   - Restore latest database dump from secure offsite backup storage.
3. **Restore Database:**
   ```bash
   docker compose -f docker-compose.prod.yml up -d postgres
   python scripts/wait_for_db.py
   python scripts/backup_restore.py restore /backups/latest.dump "$DATABASE_URL"
   ```
4. **Run Migration Check:**
   ```bash
   docker compose -f docker-compose.prod.yml run --rm migration
   ```
5. **Launch Complete Service Mesh:**
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```
6. **DNS / Load Balancer Cutover:**
   - Update DNS A-record or target group to point to the new host IP.
   - Run liveness and readiness curl checks to confirm green status.
