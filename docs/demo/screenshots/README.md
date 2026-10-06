# CUSTODE — Demonstration Visual Capture Guide & Checklist
**Version:** v0.1.0-rc1  
**Target Organization:** Acme Travel AI (`acme-travel-ai`)  

This directory contains the visual artifact checklist and capture instructions for the CUSTODE release showcase.

---

## Visual Capture Checklist

| Index | Artifact Name | Screen / Path | Key Visible Attributes | Status |
| :--- | :--- | :--- | :--- | :--- |
| **01** | `01-dashboard-fleet.png` | Overview (`/`) | Acme Travel AI selected; active agent, tool counts; system status 'online' | [Verified] |
| **02** | `02-agent-registry.png` | Agents (`/agents`) | `Travel Assistant Agent`, environment `development`, status `active` | [Verified] |
| **03** | `03-tool-capabilities.png` | Tools (`/tools`) | `Booking Management Tool` with `search_available_rooms`, `cancel_booking`, `create_booking` | [Verified] |
| **04** | `04-policy-guardrail.png` | Policies (`/policies`) | `High-Value Booking Guardrail` in `enforce` mode with condition `action.amount > 500` | [Verified] |
| **05** | `05-scenario-a-allowed.png` | Action Detail (`/runtime-actions/:id`) | Paris room search: Decision <span style="color:#10b981;font-weight:bold;">ALLOW</span>, Execution <span style="color:#10b981;font-weight:bold;">SUCCEEDED</span> | [Verified] |
| **06** | `06-scenario-b-blocked.png` | Action Detail (`/runtime-actions/:id`) | Cancellation: Decision <span style="color:#ef4444;font-weight:bold;">BLOCK</span>, Execution <span style="color:#ef4444;font-weight:bold;">BLOCKED BY GUARD</span> | [Verified] |
| **07** | `07-scenario-c-approval-inbox.png` | Approvals (`/approvals`) | Pending request for $1,250.00; Navbar badge showing `1 Pending Approval` | [Verified] |
| **08** | `08-scenario-c-approved-execution.png` | Approvals & Executions | Approval status <span style="color:#10b981;font-weight:bold;">APPROVED</span>; Execution <span style="color:#10b981;font-weight:bold;">SUCCEEDED</span> with confirmation code | [Verified] |
| **09** | `09-audit-trail-forensics.png` | Audit Logs (`/audit`) | Forensic timeline correlating request ID, agent actor, human admin reviewer, and outcome | [Verified] |

---

## Capture Procedure

1. **Seed Demo State:**
   ```bash
   python scripts/seed_demo.py
   ```
2. **Start Services:**
   ```bash
   # Terminal 1: Backend
   cd custode/backend && .venv/bin/uvicorn app.main:app --port 8000
   
   # Terminal 2: Frontend
   cd custode/frontend && npm run dev
   ```
3. **Open Browser:**
   - Navigate to `http://localhost:5173`.
   - Log in using `security.admin@custode.io` / `Custode#2026Admin!`.
   - Switch active organization in header to `Acme Travel AI`.
4. **Capture Screen Frames:**
   - Capture clean browser window frames at 1440x900 or 1920x1080 resolution.
   - Save captures into this directory matching filenames `01-dashboard-fleet.png` through `09-audit-trail-forensics.png`.
