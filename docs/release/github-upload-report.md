# CUSTODE — GitHub Repository Upload & Release-Candidate Report
**Release Version:** v0.1.0-rc1  
**Date:** 2026-10-06  
**Target Repository:** `vivekkr091/Custode-ai`  
**Target Remote:** `https://github.com/vivekkr091/Custode-ai.git`  
**Target Branch:** `main`  

---

## 1. Executive Summary

This report documents the preparation, security audit, staging, and push verification of the **CUSTODE AI Agent Security & Control Plane** (Release Candidate `v0.1.0-rc1`) to GitHub.

All security requirements and workspace boundaries were strictly enforced:
- **Workspace Scoping:** Only `/Users/vivekkumar/Downloads/Custode ai/custode/` was initialized and staged.
- **Reference Isolation:** The Sentinel reference repository (`../sentinel-ai/`) and parent workspace were untouched.
- **Aggressive Secret Audit:** Zero `.env` files, credentials, private keys, database files, or auth tokens were tracked or staged.
- **Test Integrity:** 100% test pass rate across all 327 automated backend, security, frontend, and SDK tests.

---

## 2. Repository Metadata & Commit Information

- **GitHub Owner:** `vivekkr091`
- **GitHub Repository:** `Custode-ai`
- **Visibility:** Public
- **Primary Branch:** `main`
- **Remote URL:** `https://github.com/vivekkr091/Custode-ai.git`
- **Local HEAD Commit:** `ba535105911f5b434b2de957fa90d117ec181928`
- **Commit Message:** `Initial CUSTODE v0.1.0-rc1 release candidate`
- **Total Tracked Files:** 418 files (65,122 insertions)

---

## 3. Files Included in Release Candidate

1. **Backend Service (`backend/`):**
   - Application entrypoint, routers, and middlewares (`app/main.py`, `app/api/`)
   - SQLAlchemy async models and database migrations (`app/db/`, `app/db/migrations/` 0001–0018)
   - Core engines: Permission, Policy, Risk, Decision, and Behavior Anomaly Detection (`app/engines/`)
   - Controlled execution layer and deterministic tool handlers (`app/runtime/`)
   - Sentinel scanner adapter boundary (`app/sentinel/`)
   - LLM security gateway & MCP security inspection layer (`app/llm/`, `app/mcp/`)
   - Business services: human approval governance, agent identities, audit event stream, webhooks (`app/services/`)
   - Comprehensive test suites (`backend/tests/` and `backend/tests/security/`)
   - Operational utilities: migration, backup/restore, seeding, and teardown scripts (`backend/scripts/`)
   - Dependencies: `requirements.txt`, `pyproject.toml`
2. **Frontend Console (`frontend/`):**
   - React 18 + TypeScript + Vite modern web application
   - Console pages: Dashboard, Agents, Tools, Permissions, Policies, Approvals, Risk, Decisions, Executions, Audit, Behavioral Security, LLM Gateway, MCP Security, Settings
   - Comprehensive component library, forensic timelines, modals, and cyber-defense theme
   - Frontend unit & integration test suite (`frontend/tests/frontend.test.mjs`)
   - Production Dockerfile and Nginx configuration (`frontend/Dockerfile`, `frontend/nginx.conf`)
3. **Python Agent Security SDK (`sdk/python/`):**
   - Client package: `custode-sdk` (namespace: `custode`)
   - Synchronous and asynchronous clients (`Client`, `AsyncClient`)
   - Full resource APIs: agents, permissions, runtime actions, decisions, approvals, executions, audit, findings, LLM, MCP, integrations
   - Webhook signature verification and parameter masking utilities
   - Quickstart, API reference, and 8 executable examples (`sdk/python/examples/`)
   - SDK test suite (`sdk/python/tests/`)
4. **DevOps & Containerization (`docker/`, Root):**
   - `docker-compose.yml` (Development stack)
   - `docker-compose.prod.yml` (Hardened production stack with resource limits)
   - `docker/Dockerfile.backend` (Hardened non-root Python runtime)
   - `docker/Dockerfile.frontend` (Multi-stage Nginx production build)
   - Nginx reverse proxy configuration (`docker/nginx/`)
   - CI/CD workflow (`.github/workflows/ci.yml`)
5. **Demonstration & Showcase (`scripts/`, `docs/demo/`):**
   - Idempotent demo seeder (`scripts/seed_demo.py`)
   - Safe tenant reset script with production safeguards (`scripts/reset_demo.py`)
   - Demonstration walkthrough guide (`docs/demo/demo-walkthrough.md`)
   - Timed presenter script (`docs/demo/presenter-script.md`)
   - Visual artifact guide (`docs/demo/screenshots/README.md`)
   - Showcase validation report (`docs/demo/demo-showcase-validation-report.md`)
6. **Documentation (`docs/`, Root):**
   - Primary documentation: `README.md`, `LICENSE` (Apache 2.0), `.env.example`
   - Architecture & security specifications (`docs/architecture/`, `docs/security/`)
   - Deployment, operations, DR, and runbooks (`docs/deployment/`)
   - Release notes & readiness report (`docs/release/`)

---

## 4. Files Intentionally Excluded (.gitignore Verification)

The following categories were verified as strictly excluded and absent from the git index:

| Excluded Pattern | Rationale | Verified Status |
| :--- | :--- | :--- |
| `.env`, `.env.*` (except `!.env.example`) | Secret & credential isolation | **EXCLUDED** (0 `.env` files tracked) |
| `*.db`, `*.sqlite`, `*.sqlite3`, `*.bak` | SQLite databases & backup files | **EXCLUDED** (`custode.db` not tracked) |
| `.venv/`, `venv/`, `ENV/` | Python virtual environments | **EXCLUDED** |
| `node_modules/` | Node runtime dependencies | **EXCLUDED** |
| `dist/`, `build/`, `*.egg-info/` | Compiler and bundle artifacts | **EXCLUDED** |
| `*.log`, `logs/` | Runtime service logs | **EXCLUDED** |
| `.DS_Store`, `Thumbs.db` | OS-specific cache metadata | **EXCLUDED** (Cleaned & ignored) |
| `.pytest_cache/`, `.coverage*` | Test and coverage caches | **EXCLUDED** |
| `*.pem`, `*.key`, `*.crt`, `*.p12` | Cryptographic private keys | **EXCLUDED** (0 keys present) |
| `../sentinel-ai/` | Isolated reference repository | **EXCLUDED** (Separate repo) |

---

## 5. Security & Secret Audit Results

An aggressive local scan of all files was conducted prior to staging:
- **Private Keys & Certificates:** None found.
- **Actual API Keys / Access Tokens:** None found. (Only public documentation dummy keys such as `AKIAIOSFODNN7EXAMPLE` were present in tests to verify regex redaction filters).
- **Hardcoded Production Passwords:** None found.
- **Database Connection Strings:** Only standard development defaults present in `.env.example`.
- **Verdict:** **SECRET AUDIT PASSED**

---

## 6. Regression Testing & Release Evidence

| Suite | Component | Tests Run | Result | Duration |
| :--- | :--- | :--- | :--- | :--- |
| **Backend Core** | FastAPI services & engines | 230 | **230 Passed** | 16.00s |
| **Defensive Security** | Red team & hardening tests | 39 | **39 Passed** | 2.01s |
| **Frontend Unit** | Modern web client | 19 | **19 Passed** | 51.24ms |
| **Frontend Production Build** | Vite production bundle | 95 modules | **Built Cleanly** | 411ms |
| **Python SDK** | SDK sync/async client | 39 | **39 Passed** | 0.41s |
| **Total Test Coverage** | Monorepo test suites | **327** | **327 Passed (100%)** | — |

---

## 7. Remote Verification & Authentication Diagnostics

- **Remote URL:** `https://github.com/vivekkr091/Custode-ai.git`
- **Remote Accessibility Check:** Executed `git ls-remote` anonymously; repository confirmed reachable, valid, and empty.
- **Authentication Diagnostic:**
  - When pushing via HTTPS, macOS Keychain (`credential.helper=osxkeychain`) automatically provided cached GitHub credentials belonging to account `24it007-beep` (account ID `247384580`, created 2026-09-09).
  - GitHub returned HTTP 403: `remote: Permission to vivekkr091/Custode-ai.git denied to 24it007-beep.`
  - This confirms that `24it007-beep` is not yet granted write permissions on `vivekkr091/Custode-ai`.
- **Resolution Options (Zero Secret Exposure):**
  1. **Option A (Instant - Recommended):** In GitHub web settings for [Custode-ai Collaborators](https://github.com/vivekkr091/Custode-ai/settings/access), add `24it007-beep` with write access. The existing credentials on this machine will push immediately.
  2. **Option B (Update Local Keychain):** In terminal, run `git push -u origin main` and authenticate with user `vivekkr091`'s Personal Access Token.

---

## 8. Sentinel Reference Repository Isolation

- **Directory:** `/Users/vivekkumar/Downloads/Custode ai/sentinel-ai/`
- **Branch:** `main`
- **Git Status:** `On branch main; nothing to commit, working tree clean`
- **Verdict:** **PASS** (Zero modifications, completely decoupled)

---

## 9. Conclusion & Release Status

The CUSTODE repository `/Users/vivekkumar/Downloads/Custode ai/custode/` is fully initialized, audited, hardened, committed, and ready for deployment at release candidate `v0.1.0-rc1`.
