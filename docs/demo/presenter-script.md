# CUSTODE — Demonstration Presenter Script
**Target Duration:** 5–7 Minutes  
**Target Audience:** Faculty, Hackathon Judges, Enterprise Security Evaluators  
**Key Value Proposition:** Autonomous AI Agents are powerful, but giving them uncontrolled tool access is a major enterprise risk. CUSTODE is the security control plane that ensures every agent action is authenticated, evaluated against policy and risk, approved when necessary, and executed safely with an immutable audit trail.

---

## 0:00 – 1:00 | The Problem & Introduction

### [SCREEN: Login Screen or Architecture Overview]

**Presenter:**
> "Good morning/afternoon, judges and team. Today, autonomous AI agents are being granted tools to query databases, call APIs, and execute financial transactions. But how do enterprise security teams enforce least privilege, prevent hallucinated API calls, or stop rogue operations before they hit production systems?
>
> That is why we built **CUSTODE**—a security-first AI Agent Security and Control Plane. 
>
> CUSTODE acts as an intelligent kernel between agents and the outside world. Every action an agent attempts is intercepted, evaluated against cryptographic permissions, contextual policies, behavioral baselines, and security scanners. Crucially, CUSTODE arbitrates decisions using strict mathematical precedence: **DENY overrides REQUIRE_APPROVAL, which overrides ALLOW**."

---

## 1:00 – 2:15 | The Platform & Fleet Setup

### [SCREEN: Switch to Browser at http://localhost:5173 -> Log in as Security Admin -> Select 'Acme Travel AI']

**Presenter:**
> "Let's log in as our Security Administrator. Notice in our top bar we have multi-tenant isolation. Today we're looking at **Acme Travel AI**, an autonomous travel concierge platform.
>
> If we navigate to our **Agent Identity Registry**, we see the `Travel Assistant Agent`. Just like an employee, it has an identity, environment tier, and cryptographic credentials.
>
> Next, in the **Capabilities Registry**, we see our `Booking Management Tool`. Rather than giving an agent raw API keys or unrestricted curl access, CUSTODE registers tools and distinct operations with baseline risk ratings:
> 1. `search_available_rooms` is a low-risk read operation.
> 2. `cancel_booking` is a medium-risk write operation.
> 3. `create_booking` is a high-risk financial commitment.
>
> In **Policies**, we've published an active rule: any booking action exceeding $500 requires human security authorization. Now let's see how CUSTODE handles real agent actions."

---

## 2:15 – 3:30 | Act 1: Safe Autonomous Execution (Scenario A)

### [SCREEN: Navigate to /runtime-actions -> Click on search_rooms action]

**Presenter:**
> "First, the agent attempts a routine query: searching available hotel rooms in Paris for a guest.
>
> As soon as the action is submitted, CUSTODE's kernel evaluates it in real time:
> - The Permission Engine confirms an active `ALLOW` grant exists.
> - The Policy Engine confirms no guardrail restrictions are triggered.
> - The Risk Engine confirms baseline risk is `LOW`.
>
> The Decision Engine arbitrates an authoritative **ALLOW**.
>
> The action moves to the **Controlled Execution Layer**, where CUSTODE's Execution Guard verifies the decision token and dispatches the call to a verified, deterministic handler. The query succeeds in milliseconds, returning available rooms, without any human friction.
>
> Safe actions proceed automatically."

---

## 3:30 – 4:30 | Act 2: Fail-Closed Protection (Scenario B)

### [SCREEN: Navigate to /runtime-actions -> Click on cancel_reservation action]

**Presenter:**
> "Now, consider an adversarial prompt injection or a hallucinated instruction: the agent attempts to cancel an executive's confirmed booking on `/reservations/RES-448291`.
>
> What happens?
>
> CUSTODE immediately intervenes:
> - The Permission Engine checks the agent's grants and detects an explicit **DENY** (or missing permission).
> - Under CUSTODE's fail-closed architecture, the Decision Engine arbitrates an immediate **BLOCK**.
>
> If we look at the **Controlled Execution Layer**, we see the execution status is **BLOCKED BY GUARD**.
>
> Notice what didn't happen: the agent was **never allowed to touch the downstream booking system**. Downstream APIs are protected from unauthorized execution by design."

---

## 4:30 – 6:00 | Act 3: Human Governance & Approval (Scenario C)

### [SCREEN: Point to Top Navbar showing '1 Pending Approval' -> Click on /approvals]

**Presenter:**
> "Finally, what happens when an action is valid, but represents significant financial or operational risk?
>
> Here, the agent attempts to book a penthouse suite for **$1,250.00**.
>
> The agent has basic permission to book, but our **High-Value Booking Guardrail** triggers because the amount exceeds our $500 threshold. 
>
> Instead of blocking or auto-allowing, CUSTODE arbitrates **REQUIRE_APPROVAL**.
>
> Notice the notification badge in our navbar. As a Security Admin, I open the **Human Governance Approval Inbox**. 
>
> I see the exact structured request: the agent identity, the exact parameters, the policy triggered, and the assessed risk score.
>
> I click **Approve**, enter my audit rationale: *'Executive travel authorized'*, and confirm. 
>
> The approval transitions to **APPROVED**. Now, and only now, does the Execution Guard permit the action to dispatch. 
>
> In the Execution view, we trigger execution: CUSTODE revalidates the cryptographic signature of my approval, executes the booking, and records the booking confirmation code."

---

## 6:00 – 7:00 | Forensics & Conclusion

### [SCREEN: Navigate to /audit -> Filter by Travel Assistant Agent]

**Presenter:**
> "Everything we just saw—from the initial Paris room query to the blocked cancellation to the human approval—is captured in our **Security Audit Trail**.
>
> Each event is cryptographically hashed, correlated with a unified `request_id`, and attributed to either the agent identity or the human reviewer. If compliance auditors ask how a $1,250 transaction occurred, CUSTODE provides a complete, tamper-evident forensic timeline.
>
> In summary:
> - CUSTODE enables enterprises to deploy autonomous agents with confidence.
> - Safe actions run fast.
> - Unauthorized actions are blocked cold.
> - High-risk actions are kept under strict human governance.
>
> Thank you, and we welcome your questions!"
