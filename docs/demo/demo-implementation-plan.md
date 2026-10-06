# CUSTODE — Demonstration & Release Showcase Implementation Plan
**Version:** v0.1.0-rc1  
**Target Organization:** Acme Travel AI (`acme-travel-ai`)  
**Scope:** Controlled Demonstration, Idempotent Seeding, Safe Teardown, and Showcase Workflows  

---

## 1. Executive Summary & Objective

The objective of this showcase is to provide a deterministic, repeatable, and truthful demonstration of **CUSTODE v0.1.0-rc1** (AI Agent Security & Control Plane) for developers, faculty, hackathon evaluators, and enterprise pilot evaluators.

The demonstration illustrates the complete agent action lifecycle through three realistic, synthetic operational scenarios:
1. **Scenario A (Allowed Action):** Read-only room availability query (`search_available_rooms`) evaluated with low risk, pre-approved permissions, resulting in an immediate `ALLOW` decision and successful controlled execution.
2. **Scenario B (Blocked Action):** Unauthorized customer reservation cancellation (`cancel_booking`) lacking valid permissions, resulting in an immediate `BLOCK` decision and runtime execution prevention.
3. **Scenario C (Human Approval Governance):** High-value hotel reservation commitment (`create_booking`, $1,250.00) triggering policy guardrails (`amount > $500`), resulting in a `REQUIRE_APPROVAL` decision, queued in the Human Governance Inbox, followed by authorized review and verified execution.

---

## 2. Architecture & Invariant Alignment

The demonstration strictly adheres to CUSTODE's core security invariants:
- **No Client-Side Authorization:** All security evaluations (permission, policy, behavioral baseline, Sentinel security scanning, risk scoring, decision arbitration, human approval, and execution) occur exclusively on the backend.
- **Fail-Closed Default:** Unmatched permissions or missing policies default to denied or blocked states.
- **Precedence Hierarchy:** `DENY` > `REQUIRE_APPROVAL` > `ALLOW`.
- **Tenant Isolation:** Scoped strictly to synthetic organization `acme-travel-ai`.
- **Controlled Safe Dispatch:** No arbitrary shell, eval(), exec(), or unsanitized subprocesses. Tools are executed via deterministic handlers in `ExecutionRegistry`.
- **Immutable Audit Trail:** Every decision, approval transition, and execution is correlated by `request_id` and logged to the tamper-evident audit store.

---

## 3. Synthetic Data Model: Acme Travel AI

| Entity | Synthetic Identifier / Name | Description | Environment |
| :--- | :--- | :--- | :--- |
| **Organization** | `Acme Travel AI`<br>`slug: acme-travel-ai` | Autonomous corporate travel concierge platform | `development` |
| **Agent** | `Travel Assistant Agent`<br>`type: assistant` | Autonomous booking and itinerary management assistant | `development` |
| **Tool** | `Booking Management Tool`<br>`slug: booking_tool` | Direct hotel inventory and reservation management interface | `development` |
| **Operation A** | `search_available_rooms`<br>`type: read`, `risk: low` | Queries hotel inventory without financial commitment | `development` |
| **Operation B** | `cancel_booking`<br>`type: write`, `risk: medium` | Cancels active customer reservations | `development` |
| **Operation C** | `create_booking`<br>`type: write`, `risk: high` | Commits reservation and financial authorization | `development` |
| **Policy** | `High-Value Booking Guardrail`<br>`enforce` | Mandates human governance for bookings exceeding $500 | `development` |
| **Demo Users** | `security.admin@custode.io` (Admin)<br>`analyst@custode.io` (Analyst)<br>`auditor@custode.io` (Auditor) | Multi-role human governance and review personas | `development` |

---

## 4. Script Architecture

### 4.1 Seed Script (`scripts/seed_demo.py`)
- **Location:** `custode/scripts/seed_demo.py` (and `custode/backend/scripts/seed_demo.py`)
- **Execution Mode:** Standalone CLI script utilizing SQLAlchemy AsyncSession with transaction rollbacks on failure.
- **Idempotency:**
  - Checks for existing `acme-travel-ai` organization; reuses or cleans previous demo runs.
  - Verifies presence of demo users and links organization memberships.
  - Registers agent, tool, operations, permissions, and guardrail policies.
  - Executes Scenario A (`search_available_rooms` -> `ALLOW` -> `SUCCESS`).
  - Executes Scenario B (`cancel_booking` -> `BLOCK` -> `BLOCKED`).
  - Creates Scenario C (`create_booking` -> `REQUIRE_APPROVAL` -> `PENDING_APPROVAL`).
  - Supports `--approve-c` flag to optionally complete Scenario C programmatically.
- **Output:** Structured console report detailing Tenant ID, Agent ID, Action IDs, Decision IDs, and URLs for UI demonstration.

### 4.2 Reset Script (`scripts/reset_demo.py`)
- **Location:** `custode/scripts/reset_demo.py` (and `custode/backend/scripts/reset_demo.py`)
- **Safety Safeguards:**
  - Explicit environment check: Refuses to run if `ENVIRONMENT == "production"` or `DATABASE_URL` contains production host patterns.
  - Strict tenant scoping: Deletes records associated solely with `slug == "acme-travel-ai"`. Never touches default organization `custode-cyber-defense` or real customer data.
  - Dependency-ordered cascading deletion: executions -> approvals -> decisions -> risk assessments -> runtime actions -> permissions -> policy versions -> policies -> operations -> tools -> agents -> memberships -> organization.

---

## 5. UI Demonstration Journey (5–7 Minute Walkthrough)

1. **Dashboard & Fleet Status:**
   - Log into CUSTODE console as `security.admin@custode.io`.
   - Select **Acme Travel AI** in the Organization switcher.
   - Review active agent `Travel Assistant Agent` and registered tool `Booking Management Tool`.
2. **Scenario A (Allowed Action Walkthrough):**
   - Navigate to **Runtime Actions** -> Inspect `search_available_rooms`.
   - View Authorization Decision: `ALLOW` (low risk, read operation, valid permission).
   - View Controlled Execution: Status `SUCCEEDED` with synthetic inventory output.
3. **Scenario B (Blocked Action Walkthrough):**
   - Inspect `cancel_booking`.
   - View Authorization Decision: `BLOCK` with explicit factor: *Missing permission for operation cancel_booking*.
   - View Execution status: `BLOCKED` by ExecutionGuard, verifying execution prevention.
4. **Scenario C (Governance & Approval Walkthrough):**
   - Note header badge showing `1 Pending Approval`.
   - Navigate to **Approvals Inbox** -> Select pending request for `$1,250.00` hotel reservation.
   - Inspect policy violation: `High-Value Booking Guardrail (amount > $500)`.
   - Click **Approve** and provide note `"Executive travel itinerary authorized"`.
   - Navigate to **Controlled Execution**, trigger execution, and observe real-time state transition to `SUCCEEDED` under verified governance.
5. **Audit & Forensics:**
   - Navigate to **Audit Logs** -> Filter by `Travel Assistant Agent`.
   - Inspect end-to-end cryptographic and timeline records linking submission, policy evaluation, reviewer approval, and execution dispatch.

---

## 6. Verification and Regression Checklist

- [x] Backend test suite passes 100% (230 tests in `custode/backend/tests/`).
- [x] Frontend test suite passes 100% (19 tests in `custode/frontend/`).
- [x] Frontend production bundle compiles cleanly (`npm run build`).
- [x] Python SDK test suite passes 100% (39 tests in `custode/sdk/python/`).
- [x] Sentinel reference repo (`sentinel-ai/`) remains pristine and isolated.
- [ ] Implement `seed_demo.py` and `reset_demo.py`.
- [ ] Author presenter script (`docs/demo/presenter-script.md`) and walkthrough (`docs/demo/demo-walkthrough.md`).
- [ ] Document screenshot verification guide (`docs/demo/screenshots/`).
- [ ] Generate showcase validation report (`docs/demo/demo-showcase-validation-report.md`).
