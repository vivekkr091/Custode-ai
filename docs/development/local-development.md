# CUSTODE Local Development Guide

## 1. Prerequisites

- **macOS or Linux**
- **Python 3.11+**
- **Node.js 20+** and **npm**
- **Docker & Docker Compose** (Optional for containerized run)

---

## 2. Setting Up Backend Development Environment

### Step 2.1: Virtual Environment & Dependencies

```bash
cd custode/backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 2.2: Configure Environment

In `custode/backend/.env`:
```env
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO
AUTH_MODE=development
DATABASE_URL=sqlite+aiosqlite:///custode.db
SECRET_KEY=dev-secret-key-please-change-in-production-min-32-chars
AUTH_SECRET_KEY=dev-auth-jwt-secret-key-please-change-in-production-min-32-chars
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
```

### Step 2.3: Run Development Server

```bash
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API documentation and Swagger UI are accessible at:
- `http://localhost:8000/docs`
- `http://localhost:8000/health/live`
- `http://localhost:8000/health/ready`

---

## 3. Setting Up Frontend Development Environment

```bash
cd custode/frontend

# Install dependencies
npm install

# Start Vite dev server with hot module replacement
npm run dev
```

The frontend dashboard is accessible at:
- `http://localhost:5173`

Development credentials for seeded administrator:
- Email: `admin@custode.io`
- Password: `custode_admin_password`

---

## 4. Running the Complete Automated Test Suite

### Backend Test Suite (Core + Security + Deployment)
```bash
cd custode/backend
.venv/bin/pytest tests/ -v
```

### Frontend Test Suite & Production Build
```bash
cd custode/frontend
npm test
npm run build
```

### Python SDK Test Suite
```bash
cd custode/sdk/python
PYTHONPATH=src ../../backend/.venv/bin/pytest tests/ -v
```

### Docker Compose Verification
```bash
cd custode
docker compose config
```
