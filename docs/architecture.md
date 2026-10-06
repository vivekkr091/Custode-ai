# CUSTODE Architecture Specification

## 1. Executive Summary

CUSTODE is an AI Agent Security & Control Platform. It provides an inline proxy and control plane mediating interactions between autonomous AI agents and external resources (APIs, databases, bash/terminal, MCP tools, filesystem).

## 2. Layered Architecture

```
                    ┌───────────────────────────┐
                    │      AI Agent Caller      │
                    │ (Claude Code, AutoGPT,etc)│
                    └─────────────┬─────────────┘
                                  │
                       Tool Call / Action Request
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          CUSTODE CONTROL PLANE                         │
│                                                                        │
│  [Runtime Action Normalizer] ── Converts raw tool call to Action model │
│               │                                                        │
│               ▼                                                        │
│  [Identity & Auth Resolver] ── Authenticates agent, resolves tenant    │
│               │                                                        │
│               ▼                                                        │
│  [Permission Engine] ──────── Checks RBAC/ABAC tool capabilities       │
│               │                                                        │
│               ▼                                                        │
│  [Sentinel Scanner Adapter] ── Invokes fast sub-ms safety checks       │
│               │                (injection, PII, harmful payload)       │
│               ▼                                                        │
│  [Policy Engine] ──────────── Evaluates organizational rules           │
│               │                                                        │
│               ▼                                                        │
│  [Contextual Risk Engine] ─── Computes aggregate dynamic risk score    │
│               │                                                        │
│               ▼                                                        │
│  [Decision Engine] ────────── Arbitrates final disposition:            │
│                               ALLOW / BLOCK / REQUIRE_APPROVAL         │
└────────────────────────────────────────────────────────────────────────┘
                 │                      │                    │
          ALLOW  │      REQUIRE_APPROVAL│              BLOCK │
                 ▼                      ▼                    ▼
     ┌───────────────────────┐ ┌───────────────────┐ ┌───────────────┐
     │  Controlled Execution │ │  Human Approval   │ │  Action Halt  │
     │  Dispatches to Tool   │ │  Web Dashboard    │ │  Audit & Alert│
     └───────────┬───────────┘ └─────────┬─────────┘ └───────┬───────┘
                 │                       │                   │
                 └───────────────────────┼───────────────────┘
                                         ▼
                            ┌────────────────────────┐
                            │ Audit & Security Event │
                            │ Immutable log & events │
                            └────────────────────────┘
```

## 3. Component Breakdown

- **`app/api/`**: FastAPI routers providing management APIs, runtime action ingestion, health checks, and metrics.
- **`app/runtime/`**: Normalizes heterogeneous agent inputs into standardized `RuntimeAction` contracts and executes authorized actions safely.
- **`app/sentinel/`**: Encapsulates Sentinel AI scanning logic behind an adapter boundary without mutating Sentinel source.
- **`app/engines/`**:
  - `permission/`: Evaluates whether the identified agent has rights to execute the target tool/operation.
  - `policy/`: Evaluates context, data classifications, time, and tenant policies.
  - `risk/`: Calculates multidimensional risk (target criticality, scanner findings, anomaly score).
  - `decision/`: Aggregates outcomes into an actionable decision.
- **`app/approvals/`**: Manages human approval requests, timeouts, and state transitions.
- **`app/audit/`**: Structured audit event persistence for compliance and forensics.
- **`app/events/`**: Asynchronous notification bus for security events (webhooks, alerts, SIEM).

## 4. Runtime Action Layer (Milestone 8)

A `RuntimeAction` represents one concrete action requested by an authenticated agent. It serves as the authoritative, canonical input model across the entire security pipeline:

```
Agent
 ↓
RuntimeAction
 ↓
Permission Engine
 ↓
Policy Engine
 ↓
Risk Engine
 ↓
Decision Engine
 ↓
Approval / Execution
 ↓
Audit
```

### Action Normalization & Canonical Representation
Incoming requests are sanitized and validated by `ActionNormalizer` (`app/runtime/normalizer.py`):
- **Environment**: Normalized to `dev`, `staging`, `prod` and validated against the agent's deployment tier.
- **Action Type**: Canonical lowercase identifier.
- **Resource**: Clean URI/path formatting without trailing slashes.
- **Parameters**: Deep JSON validation ensuring no non-serializable objects, NaN, or Infinity.
- **Amount & Currency**: Rounded decimal conversion and ISO currency uppercase formatting.
- **IP Address**: Canonical IPv4/IPv6 validation.
- **Correlation**: Automatic UUID4 `request_id` generation or validation.

### Strict Hierarchy & Tenant Validation
Before a `RuntimeAction` can be persisted:
1. Organization must exist and be active.
2. Agent must exist, belong to the organization, and be active.
3. Agent environment must match the action environment tier (`development` -> `dev`, `staging` -> `staging`, `production` -> `prod`).
4. Tool must exist, belong to the organization, and be active.
5. Operation must exist, belong to the specified tool, and be active.

### Lifecycle State Machine
`RuntimeAction.status` tracks operational lifecycle, not the final security authorization decision:
- `pending → evaluating` or `pending → cancelled`
- `evaluating → approved`, `evaluating → denied`, or `evaluating → failed`
- `approved → executed` or `approved → failed`
- Terminal states (`executed`, `denied`, `failed`, `cancelled`) cannot revert.

> **Note on Milestone 8 Scope**:
> Milestone 8 implements only the `RuntimeAction` domain model, canonical normalization, hierarchy validation, lifecycle state transitions, service, API endpoints, and database migration.

## 5. Contextual Risk Assessment Layer (Milestone 9)

The Risk Assessment Engine evaluates canonical `RuntimeAction` instances and calculates a normalized contextual risk score (0–100) and risk classification:

```
RuntimeAction
    ↓
Permission Evaluation
    ↓
Policy Evaluation
    ↓
Risk Assessment  (Milestone 9)
    ↓
Decision Engine  (Future Milestone)
```

### Why Risk Engine Does Not Make Authorization Decisions
The Risk Engine answers: *"What is the contextual risk of this action?"*
It does **NOT** answer: *"Should this action ultimately be allowed?"*
Separating risk assessment from policy enforcement and decisioning ensures that risk scoring remains pure, deterministic, and reusable across multiple policies, workflows, and auditing pipelines without prematurely short-circuiting or mutating action states.

### Baseline Risk
Each action inherits the declared baseline risk from its underlying `ToolOperation`:
- **LOW**: 10.0
- **MEDIUM**: 30.0
- **HIGH**: 55.0
- **CRITICAL**: 80.0

### Deterministic Contextual Factors
Contextual contributors are added to the baseline:
- **Environment**: `dev` (+0), `staging` (+5), `prod` (+15).
- **Operation Type**: `read` (+0), `write` (+5), `delete` (+15), `execute` (+15), `transfer` (+20), `admin` (+25), `custom` (+5).
- **Resource Sensitivity**: `public` (+0), `internal` (+5), `sensitive` (+15), `financial` (+20), `credential` (+25), `identity` (+15), `database`/`filesystem`/`cloud` (+10), `unknown` (+5).
- **Monetary Amount**: `0–10k` (+0), `10k–50k` (+10), `50k–100k` (+20), `100k–500k` (+30), `>500k` (+40).
- **Combination Rules**:
  - *Production Destructive Operations*: `prod` + `(delete | execute | admin)` adds an extra +15.
  - *Sensitive Transfers*: `transfer` + `(financial | credential | identity | sensitive)` adds an extra +15.

### Score Aggregation & Centralized Thresholds
Scores are aggregated and strictly capped at 100.0:
- **0 – 24**: `LOW`
- **25 – 49**: `MEDIUM`
- **50 – 74**: `HIGH`
- **75 – 100**: `CRITICAL`

### Explainability & Historical Audit Artifacts
- **Explainability**: An explanation string is synthesized directly from individual contributing factors and scores. No LLMs or non-deterministic heuristics are used.
- **Historical Assessments**: Every risk evaluation persists a new immutable `RiskAssessment` record associated with the target action, preserving a full audit trajectory across changes or re-evaluations. Action fields are never mutated during assessment.

## 6. Authoritative Decision Engine Layer (Milestone 10)

The Decision Engine is the centralized authorization boundary arbitrating the final security disposition of every `RuntimeAction`:

```
Organization
    ↓
Authenticated Agent
    ↓
RuntimeAction
    ↓
Permission Engine (Least-privilege authorization)
    ↓
Policy Engine (Contextual organization rules)
    ↓
Risk Engine (Contextual operational risk assessment)
    ↓
🔥 Decision Engine (Centralized Arbitration)
    ↓
ALLOW / BLOCK / REQUIRE_APPROVAL
    ↓
Future Human Approval / Controlled Execution
    ↓
Audit / Security Events
```

### Separation of Responsibilities
- **Permission Engine**: Answers *"Does this agent have explicit authorization for this operation in this environment?"*
- **Policy Engine**: Answers *"Do active organization policies allow, deny, or require approval for this action?"*
- **Risk Engine**: Answers *"What is the contextual risk score and classification of this action?"*
- **Decision Engine**: Answers *"What authorization decision should CUSTODE enforce based on all contributing engine outcomes?"*

> **Critical Architecture Boundary**:
> The Decision Engine is the authoritative authorization enforcement boundary. It determines whether an action may proceed, is blocked, or requires approval, but it **never executes the action**, does not invoke external tools, and does not alter `RuntimeAction.status` in this milestone.

### Decision Precedence
Authoritative decisions follow strict, deterministic precedence:

```
DENY (BLOCK)
    >
REQUIRE_APPROVAL
    >
ALLOW
```

1. **Permission DENY**: If the Permission Engine returns `deny` (or if no active permission grant matches under default-deny), the final decision is strictly **BLOCK**. This has highest authority.
2. **Policy DENY**: If permission is granted, but an active enforced policy matches with effect `deny`, the final decision is **BLOCK**.
3. **Policy REQUIRE_APPROVAL**: If permission is granted and no policy denies, but an active enforced policy requires approval, the final decision is **REQUIRE_APPROVAL**.
4. **Risk-Based REQUIRE_APPROVAL**: If permission is granted, no policy denies, and no policy requires approval:
   - **CRITICAL** risk → **REQUIRE_APPROVAL**
   - **HIGH** risk → **REQUIRE_APPROVAL**
   - **MEDIUM** risk → continues evaluation (does not trigger approval on its own)
   - **LOW** risk → continues evaluation (does not trigger approval on its own)
   *(Note: Risk alone does not produce a BLOCK decision in this milestone.)*
5. **ALLOW**: Emitted only when permission is granted, no active policy denies or requires approval, and contextual risk does not mandate approval.

### Audit-Mode Policy Behavior
Policies configured with `enforcement_mode = audit` record matches within `evaluation_trace` and contributing `factors`, but they **do not** participate in blocking or requiring approval. An audit-mode policy match cannot override an `ALLOW` disposition.

### Explainability & Structured Evaluation Trace
Every decision generates:
- **Human-Readable Reason**: Dynamically constructed from structured facts without any generative LLM or heuristic code.
- **Evaluation Trace**: A tamper-evident JSON structure recording the intermediate outputs from `permission`, `policy`, and `risk` engines, the final decision, and the `source` of strongest enforcement (`permission`, `policy`, `risk`, or `system`). Risk-based approvals are clearly distinguished from policy-based approvals.

### Historical Decision Audit Records
- Decision records in the `decisions` table are immutable historical audit artifacts.
- Repeated decision evaluations on the same `RuntimeAction` create distinct `Decision` rows with unique UUIDs and timestamps, strictly preserving full audit lineage without mutating past evaluation records or `RuntimeAction.status`.

## 7. Human Governance Approval Workflow & Real-Time Revalidation (Milestone 11)

The Approval Workflow provides human governance over high-risk or policy-mandated agent actions:

```
Decision Engine
    ↓
REQUIRE_APPROVAL
    ↓
ApprovalRequest (Created with Decision Snapshot & Context)
    ↓
Authorized Reviewer Assignment (organization_admin or security_analyst)
    ↓
Real-Time Security Revalidation (Reruns Permissions, Policies, Risk, Decision)
    ↓
APPROVE / REJECT / CANCEL
    ↓
RuntimeAction Status Updated (evaluating -> approved / denied)
    ↓
Future Controlled Execution (Separate Pipeline)
```

### Core Governance Principles
- **Governance, Not Execution**: The approval step confirms that human governance authorization has been granted; it **never executes the action** and does not invoke external tools.
- **Prerequisite Decision**: An `ApprovalRequest` is instantiated only when the authoritative decision is `REQUIRE_APPROVAL`. Requests cannot be created for `ALLOW` or `BLOCK` decisions.
- **Idempotent / Pending Request Reuse**: Only one active pending approval request is allowed per `RuntimeAction`. Subsequent creation attempts return the existing pending approval.

### Reviewer Authorization
Only human organization members with designated governance authority may approve or reject:
- **Authorized**: `organization_admin`, `security_analyst`.
- **Unauthorized**: `developer`, `viewer` (requests fail with `403 Forbidden`).
- Reviewer identity is verified from authenticated user context (`X-User-ID` header) and must belong to the same tenant organization.

### Real-Time Security Revalidation
When an authorized reviewer submits an approval, the system **never trusts stale decision snapshots**. Before finalizing the approval:
1. The target `RuntimeAction` is loaded and confirmed non-terminal.
2. The entire evaluation pipeline (Permission Engine, Policy Engine, Risk Engine, Decision Engine) is re-executed in real time against the current tenant state.
3. The revalidated decision is compared:
   - **Remains `REQUIRE_APPROVAL`**: Approval succeeds; status becomes `approved`.
   - **Becomes `BLOCK`**: Approval fails with `409 Conflict`; action remains blocked.
   - **Becomes `ALLOW`**: The original approval requirement is no longer applicable; approval is marked stale/cancelled and rejected with `409 Conflict`.

### Expiration & Lifecycle State Machine
- **State Graph**: `pending` → `approved`, `rejected`, `expired`, or `cancelled`.
- **Terminal States**: `approved`, `rejected`, `expired`, and `cancelled` are strictly immutable; transitions out of terminal states are rejected with `409 Conflict`.
- **Expiration**: If `now > expires_at`, pending approval requests are treated as `expired` upon access or action attempts.

## 8. Controlled Execution Layer & Execution Guard (Milestone 12)

The Controlled Execution Layer is the authoritative boundary through which approved AI agent actions are executed against registered tool capabilities:

```
RuntimeAction Execution Request
    ↓
Execution Guard
  ├─ 1. Tenant & Entity Scoping Check (Org, Action, Agent, Tool, Op)
  ├─ 2. Idempotency Check (Prevent duplicate execution of succeeded actions)
  ├─ 3. Real-Time Revalidation (Permissions, Policies, Risk, Decision)
  └─ 4. Governance Validation (Verify valid, non-expired ApprovalRequest if REQUIRE_APPROVAL)
    ↓
[BLOCK / APPROVAL_REQUIRED]  ──>  Persist Execution(status="blocked") & Deny Action
    ↓
[ALLOWED]
    ↓
Create Execution(status="running")
    ↓
Parameter Sanitization (Mask secrets, strip dangerous prototype keys)
    ↓
ExecutionRegistry Dispatch (Lookup via tool_slug:op_slug or tool_type:op_type)
    ↓
Safe Deterministic Handler (Strictly NO eval, exec, subprocess, or shell=True)
    ↓
Record Outcome:
  ├─ Succeeded: Execution(status="succeeded", result=...), Action(status="executed")
  └─ Failed:    Execution(status="failed", error_code=...), Action(status="failed")
```

### Core Architecture & Safety Principles
- **No Arbitrary Code Execution**: CUSTODE strictly prohibits `eval()`, `exec()`, `os.system()`, `subprocess`, dynamic string imports, or arbitrary shell invocations.
- **Controlled Static Registry**: Handlers must be registered in the static `ExecutionRegistry` mapping `f"{tool_slug}:{operation_slug}"` or fallback `f"{tool_type}:{operation_type}"`. Unregistered capabilities fail safely with `error_code="HANDLER_NOT_REGISTERED"`.
- **Execution Guard Precedence & Real-Time Revalidation**:
  - The guard re-runs Permission, Policy, Risk, and Decision engines immediately prior to execution.
  - If decision evaluates to `BLOCK`: execution is blocked immediately with `EXECUTION_BLOCKED_BY_GUARD`.
  - If decision evaluates to `REQUIRE_APPROVAL`: the guard requires a valid, approved, non-expired `ApprovalRequest`.
  - If decision evaluates to `ALLOW`: execution proceeds.
- **Idempotency**: An action that has already succeeded cannot be executed twice. Any subsequent execution attempt fails with `409 Conflict` (`DUPLICATE_EXECUTION`).
- **Parameter Sanitization**: All action parameters pass through `sanitize_parameters()` before execution, masking sensitive credentials (`password`, `token`, `api_key`, `secret`) and stripping dangerous prototype pollution keys (`__proto__`, `constructor`, `__class__`).
- **Complete Audit Trail**: Each execution creates a persisted `Execution` record linking `organization_id`, `runtime_action_id`, `agent_id`, `tool_id`, `operation_id`, `decision_id`, `approval_id`, execution duration timestamps, status, result payload, and error codes.



