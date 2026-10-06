# CUSTODE CI/CD Architecture & Pipeline Specification

## 1. CI Pipeline Architecture

CUSTODE enforces continuous integration via GitHub Actions configured in `.github/workflows/ci.yml`.

### Pipeline Stages

```text
[ Git Push / Pull Request ]
             |
             +-----------------------+-----------------------+-----------------------+
             |                       |                       |                       |
             v                       v                       v                       v
     [ Backend Suite ]       [ Frontend Suite ]       [ Python SDK ]         [ Docker Validate ]
     - Unit & Flow Tests     - Vitest Unit Tests      - Async Client Tests    - Compose Dev Syntax
     - Security Tests (27)   - Production Vite Build  - Replay & HMAC Tests   - Compose Prod Syntax
     - Migration Replay      - TypeCheck (tsc)        - Transport Retries     - Non-Root Dockerfile
             |                       |                       |                       |
             +-----------------------+-----------------------+-----------------------+
                                             |
                                             v
                               [ All Quality Gates Passed ]
```

---

## 2. Gate Criteria & Enforcement

Before code merges into protected branches (`main`, `master`, `develop`), all quality gates must pass:

1. **Backend & Security Test Gate:**
   - 100% pass rate across all backend core tests (191 tests) and security hardening tests (27 tests).
   - Zero regression failures allowed.
2. **Frontend Quality Gate:**
   - Vitest component and router tests (19 tests) must pass.
   - Production bundle compilation (`tsc && vite build`) must succeed with zero TypeScript or bundling errors.
3. **Python SDK Compatibility Gate:**
   - External Python agent SDK test suite (39 tests) must pass.
4. **Database Migration Safety Gate:**
   - Alembic migration test (`test_migrations.py`) executes full upgrade to head and complete downgrade cycle on an ephemeral database.
5. **Infrastructure As Code Gate:**
   - Both `docker-compose.yml` and `docker-compose.prod.yml` must validate cleanly with `docker compose config`.
