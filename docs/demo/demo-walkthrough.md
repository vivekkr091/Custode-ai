# CUSTODE — Demonstration Walkthrough Guide
**Version:** v0.1.0-rc1  
**Target Organization:** Acme Travel AI (`acme-travel-ai`)  
**Audience:** Developers, Security Analysts, Hackathon Judges, Faculty  

---

## 1. Overview & Demonstration Architecture

CUSTODE is an enterprise AI Agent Security & Control Plane providing runtime policy enforcement, least-privilege tool authorization, contextual risk evaluation, behavioral anomaly detection, and human approval governance for autonomous AI agents.

This walkthrough guides you through a repeatable 3-act operational demonstration using **Acme Travel AI**—an autonomous travel concierge platform with an agent dispatching actions against real travel reservation capabilities.

```
                      +-----------------------------+
                      |   Travel Assistant Agent    |
                      +--------------+--------------+
                                     |
                                     v
                       [ 1. RuntimeAction Created ]
                                     |
                                     v
                       [ 2. Permission Engine ]
                                     |
                                     v
                       [ 3. Policy & Risk Engine ]
                                     |
                                     v
                       [ 4. Decision Arbitration ]
                                     |
             +-----------------------+-----------------------+
             |                       |                       |
       [ ALLOW ]            [ REQUIRE_APPROVAL ]          [ BLOCK ]
             |                       |                       |
     (Direct Dispatch)       (Human Approval Inbox)     (Execution Guard)
             |                       |                       |
      Auto-Executed           Admin Reviews           Blocked & Audited
      (Scenario A)            & Authorizes              (Scenario B)
                              (Scenario C)
```

---

## 2. Environment Setup & Seeding

### 2.1 Start Backend & Frontend

In Terminal 1 (Backend):
```bash
cd custode/backend
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

In Terminal 2 (Frontend):
```bash
cd custode/frontend
npm run dev
```
Frontend UI will be accessible at: `http://localhost:5173`  
Backend OpenAPI Docs at: `http://localhost:8000/docs`

### 2.2 Seed the Acme Travel AI Demo

Run the automated seeder script:
```bash
python scripts/seed_demo.py
```
*Tip: To reset the demo environment cleanly at any time, run:*
```bash
python scripts/reset_demo.py --yes
```

---

## 3. Demonstration Personas

| Role | Email | Password | Permissions |
| :--- | :--- | :--- | :--- |
| **Security Admin** | `security.admin@custode.io` | `Custode#2026Admin!` | Full governance, approval authority, policy authoring |
| **Security Analyst**| `analyst@custode.io` | `Analyst#2026Secure!` | Action investigation, approval authority |
| **Auditor / Viewer**| `auditor@custode.io` | `Auditor#2026View!` | Read-only forensic inspection and audit review |

---

## 4. Step-by-Step Scenario Walkthrough

### Act 1: Initial Login & Fleet Inspection

1. Navigate to `http://localhost:5173/login`.
2. Enter email: `security.admin@custode.io` and password: `Custode#2026Admin!`.
3. In the top navigation bar, locate the **Organization Switcher** dropdown.
4. Select **Acme Travel AI** (`acme-travel-ai`).
5. Open **Agent Identity Registry** (`/agents`):
   - Observe **Travel Assistant Agent** registered in `development` tier.
6. Open **Callable Capabilities Registry** (`/tools`):
   - Observe **Booking Management Tool** (`booking_tool`) with 3 registered operations:
     * `search_available_rooms` (Read, Low Risk)
     * `cancel_booking` (Write, Medium Risk)
     * `create_booking` (Write, High Risk)
7. Open **Agent-to-Tool Authorization** (`/permissions`):
   - Confirm explicit grants: `ALLOW` for room search, `DENY` for cancel, `ALLOW` for booking.
8. Open **Security Policy Engine** (`/policies`):
   - Inspect active policy **High-Value Booking Guardrail** (`amount > 500` -> `require_approval`).

---

### Act 2: Scenario A — Low-Risk Allowed Action

**Objective:** Demonstrate zero-friction automated execution for safe, authorized agent queries.

1. Navigate to **Runtime Actions** (`/runtime-actions`).
2. Click on the action for `search_rooms` on `/destinations/paris/rooms`.
3. **Inspect the Security Decision:**
   - Decision: <span style="color:#10b981;font-weight:bold;">ALLOW</span>
   - Reason: *Permission check granted; operation risk low; no policy violations.*
4. **Inspect the Controlled Execution:**
   - Status: <span style="color:#10b981;font-weight:bold;">SUCCEEDED</span>
   - Output: Available rooms (`deluxe_king`, `executive_suite`) returned by deterministic handler.
   - Guard validation: Verified with 0ms delay.

---

### Act 3: Scenario B — Blocked Unauthorized Action

**Objective:** Demonstrate fail-closed security preventing unauthorized agent operations.

1. In **Runtime Actions** (`/runtime-actions`), select the action for `cancel_reservation` (`/reservations/RES-448291`).
2. **Inspect the Security Decision:**
   - Decision: <span style="color:#ef4444;font-weight:bold;">BLOCK</span>
   - Reason: *Action blocked because permission check failed: Explicit deny permission matched.*
   - Precedence: Hard `DENY` overrides any potential policy allowance.
3. **Inspect the Controlled Execution:**
   - Navigate to **Controlled Execution Layer** (`/executions`).
   - Find execution for `cancel_reservation`.
   - Status: <span style="color:#ef4444;font-weight:bold;">BLOCKED</span>
   - Error Code: `EXECUTION_BLOCKED_BY_GUARD`.
   - Crucial guarantee: Downstream booking cancellation API was **never reached**.

---

### Act 4: Scenario C — High-Value Action & Human Governance

**Objective:** Demonstrate human-in-the-loop authorization for sensitive transactions.

1. In the top navigation bar, observe the notification badge: **1 Pending Approval**.
2. Navigate to **Human Governance Approval Inbox** (`/approvals`).
3. Select the pending request:
   - Requester: `Travel Assistant Agent`
   - Capability: `Booking Management Tool` (`create_booking`)
   - Resource: `/bookings/hotel_resort_78`
   - Amount: **$1,250.00 USD**
   - Triggering Guardrail: *High-Value Booking Guardrail (amount 1250 > 500 threshold).*
4. Click **Approve Request**:
   - In the modal, provide Reviewer Note: `"Executive itinerary approved per travel policy."`
   - Click **Confirm Approval**.
   - Observe request state immediately transition to <span style="color:#10b981;font-weight:bold;">APPROVED</span>.
5. **Execute the Authorized Action:**
   - Navigate to **Controlled Execution Layer** (`/executions`).
   - Select the newly authorized action and click **Execute Action**.
   - Execution Guard verifies the active cryptographic approval and dispatches to handler.
   - Outcome: Status <span style="color:#10b981;font-weight:bold;">SUCCEEDED</span> with Booking Reference `BK-2026-ACME-90412`.

---

### Act 5: Audit Forensics & Timeline

1. Navigate to **Security Audit Trail** (`/audit`).
2. Filter events by actor or resource:
   - Notice the complete lifecycle timeline:
     1. `ACTION_REGISTERED`
     2. `DECISION_EVALUATED` (`require_approval`)
     3. `APPROVAL_REQUESTED`
     4. `APPROVAL_GRANTED` (Attributed to `security.admin@custode.io`)
     5. `EXECUTION_DISPATCHED`
     6. `EXECUTION_SUCCEEDED`
3. Click any event to view the immutable audit payload, tamper-evident hashes, and correlation `request_id`.

---

## 5. Automated CLI Execution Reference

You can also run the complete lifecycle entirely from the terminal:

```bash
# Seed with Scenario C pre-approved and executed
python scripts/seed_demo.py --approve-c

# Or query backend API directly with curl:
curl -s -X GET "http://localhost:8000/api/v1/organizations" \
  -H "Authorization: Bearer <TOKEN>" | jq .
```
