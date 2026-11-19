# 🚀 How to Run Smart Complaint Assistant — Complete Setup & Execution Guide

This document is the definitive guide on **how to run this project**, detailing **all required packages**, system prerequisites, machine learning pipeline execution, database setup, environment configuration, and troubleshooting steps.

---

## 1. System Prerequisites

Before running the project, ensure your environment meets the following specifications:

| Requirement | Recommended Version | Minimum Supported | Notes |
|:---|:---|:---|:---|
| **Operating System** | Windows 10/11, macOS, or Ubuntu 20.04+ | Any modern 64-bit OS | Tested on Windows 11 & Linux |
| **Python** | **Python 3.10** or **3.11** | Python 3.9 | Recommended: 64-bit Python |
| **RAM** | **4 GB** or more | 2 GB | Required during sentence embedding generation |
| **Disk Space** | **~1.5 GB** | 800 MB | PyTorch, Hugging Face models, and dependencies |
| **Web Browser** | Chrome, Edge, Firefox, or Safari | Modern evergreen browser | JavaScript & Web Storage must be enabled |
| **Network** | Internet connection | Required on first run | To download `all-MiniLM-L6-v2` transformer weights |

---

## 2. Required Packages & Dependencies

All dependencies are defined in `backend/requirements.txt`. Below is the complete explanation of each package and its role in the application:

| Package | Version / Target | Role in the Platform |
|:---|:---|:---|
| **`fastapi`** | `^0.115.0` | Asynchronous high-performance REST API web framework, routing, dependency injection. |
| **`uvicorn[standard]`** | `^0.30.0` | Production ASGI web server hosting the FastAPI application on `http://127.0.0.1:8000`. |
| **`sentence-transformers`** | `^3.0.0` | Hugging Face embedding pipeline using `all-MiniLM-L6-v2` to produce 384-dimensional dense semantic vectors. |
| **`torch`** | Auto-installed with sentence-transformers | Deep learning tensor engine executing transformer inference. |
| **`faiss-cpu`** | `^1.8.0` | Facebook AI Similarity Search library executing inner-product cosine similarity searches over complaint vectors. |
| **`scikit-learn`** | `^1.5.0` | Multiclass Logistic Regression / SGDClassifier generating probability confidence scores for 8 civic departments. |
| **`pandas`** | `^2.2.0` | High-performance tabular data structures managing complaint datasets, resolution times, and statistical modes. |
| **`numpy`** | `^1.26.0` | High-performance numerical arrays, vector normalization, and binary BLOB conversion. |
| **`joblib`** | `^1.4.0` | Efficient model serialization, loading and saving `classifier.joblib` to disk. |
| **`httpx`** *(dev / test)* | `^0.27.0` | Asynchronous HTTP test client used by `TestClient` in `backend/test_all_features.py`. |

---

## 3. Step-by-Step Installation & Setup

### Step 1: Open Terminal / Shell in Project Root
Navigate to the root directory where the project is saved:
```powershell
# Windows PowerShell
cd "c:\Users\dilan\Downloads\complaint-classifier (2)\Sana_complaint-classifier"
```
```bash
# macOS / Linux
cd /path/to/Sana_complaint-classifier
```

---

### Step 2: Create and Activate Python Virtual Environment
Always run within an isolated virtual environment to prevent package version conflicts:

#### On Windows (PowerShell):
```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
```
*(If you see an execution policy error in PowerShell, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and reactivate).*

#### On Windows (Command Prompt):
```cmd
cd backend
python -m venv .venv
.venv\Scripts\activate.bat
```

#### On macOS / Linux:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

---

### Step 3: Upgrade Pip & Install Dependencies
With `.venv` active, install the required packages:
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

*(Optional: Install test runner dependencies)*
```powershell
pip install httpx pytest
```

---

### Step 4: Configure Environment Settings (Optional)
Copy the provided environment template:
```powershell
# In backend/ folder:
cp .env.example .env
```

**Key `.env` Configuration Variables:**
```ini
# Admin emails permitted to alter report status (Open -> In Progress -> Closed):
ADMIN_EMAILS=admin@example.com,desk@city.gov

# Department authority email address populated into pre-drafted citizen emails:
AUTHORITY_EMAIL=grievance@city.gov

# Number of neighbour confirmations required to close an issue:
VERIFY_THRESHOLD=2

# Security & CORS settings:
ALLOW_ALL_ORIGINS=true
CORS_ORIGINS=http://127.0.0.1:8000,http://localhost:8000

# Set to true only for single-user local testing to verify own reports:
ALLOW_SELF_VERIFY=false
```

---

## 4. Building Machine Learning Artifacts & Dataset (First Run)

The platform requires three machine learning artifacts:
1. `backend/data/complaints.csv` (Tabular grievance dataset)
2. `backend/models/classifier.joblib` (Trained multiclass model)
3. `backend/models/complaints.faiss` (Pre-computed vector search index)

Run these 3 commands in order from inside the `backend/` folder:

### 1. Generate Synthetic Complaint Dataset
```powershell
python -m ml.generate_data
```
- **Output:** Creates `backend/data/complaints.csv` containing 640 realistic citizen grievances mapped across 8 civic departments.

### 2. Train the Machine Learning Classifier
```powershell
python -m ml.train_classifier
```
- **Output:** Encodes grievances using `SentenceTransformers`, trains a calibrated classifier, and saves `backend/models/classifier.joblib` (achieving ~99% Macro-F1).

### 3. Build the FAISS Vector Search Index
```powershell
python -m ml.build_index
```
- **Output:** Normalizes sentence vectors and builds the static cosine index `backend/models/complaints.faiss` along with `backend/models/embeddings.npy`.

---

## 5. Seeding Demo Accounts & Sample Incident Reports

To explore the application with realistic data immediately, run the automated seeding script:

```powershell
# In backend/ with .venv active:
python seed_demo.py
```

This creates:
- **12 Interactive Incident Reports** pinned across Bengaluru (Indiranagar, Koramangala, Whitefield, Malleshwaram, MG Road) across all status lifecycles (`open`, `in_progress`, `fix_to_verify`, `closed`).
- **2 Pre-Configured Demo Accounts**:
  - **Reporter:** `demo.reporter@example.com` / Password: `demo-pass-123`
  - **Neighbour:** `demo.neighbour@example.com` / Password: `demo-pass-123`
  - *(Or register any new account directly via the UI)*

---

## 6. Starting the Server & Running the Application

### Start Development Server (with Auto-Reload)
From inside the `backend/` directory with `.venv` active:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Start Production Server (Standard Mode)
```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
```

---

## 7. How to Access and Use the Application

Once Uvicorn displays `Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)`, open your browser:

### Key Access Points:

| URL | Purpose | Interface Description |
|:---|:---|:---|
| **`http://127.0.0.1:8000/`** | **Interactive Civic Map (Primary)** | Full Leaflet map view, live community feed, GPS coordinate pinning, 3-step report filing modal, AI pre-checks, and neighbour verification voting. |
| **`http://127.0.0.1:8000/dashboard.html`** | **Citizen Incident Dashboard** | 2-column municipal command center with instant quick-topic chips, live complaints tracker, and notification center. |
| **`http://127.0.0.1:8000/index.html`** | **Portal Authentication** | Full-page citizen sign-in and account registration. |
| **`http://127.0.0.1:8000/docs`** | **Swagger Interactive API** | Live interactive OpenAPI documentation for testing all backend routes directly. |
| **`http://127.0.0.1:8000/redoc`** | **ReDoc API Specifications** | Clean technical REST API documentation. |
| **`http://127.0.0.1:8000/api/health`** | **System Diagnostics** | Real-time JSON health check showing database status and ML engine availability. |

---

## 8. Running Automated Verification Tests

To verify that all components, databases, and machine learning models are functioning with 100% precision, run the automated test suite:

```powershell
# From the project root or backend folder with .venv active:
python backend/test_all_features.py
```

### Expected Output:
```
=================================================================
  TEST RUN SUMMARY: backend/test_all_features.py
=================================================================
[PASS]  1: Public /api/health endpoint returns operational status
[PASS]  2: Simulating missing engine returns clean HTTP 503
[PASS]  3: POST /api/auth/register creates new account with salt
[PASS]  4: POST /api/auth/register rejects duplicate email
[PASS]  5: POST /api/auth/login succeeds with valid credentials
[PASS]  6: POST /api/auth/login rejects invalid password
[PASS]  7: GET /api/me returns user profile and admin status
[PASS]  8: Protected endpoints reject unauthorized requests (401)
[PASS]  9: POST /api/complaints classifies, rounds confidence, notifies
[PASS] 10: GET /api/complaints retrieves submitted complaints list
[PASS] 11: Notifications lifecycle (fetch, read-one, read-all) works
[PASS] 12: GET /api/reports returns active reports and populated stats
[PASS] 13: POST /api/reports/preview provides AI classification & email draft
[PASS] 14: POST /api/reports creates report and updates live FAISS vector index
[PASS] 15: Live FAISS index detects duplicate report within 250m radius
[PASS] 16: GET /api/reports/{id} returns full report details and history
[PASS] 17: POST /api/reports/{id}/checks submits and updates checks cleanly
[PASS] 18: POST /api/reports/{id}/status enforces admin-only access
[PASS] 19: Static web assets and / redirect serve correctly (200 OK)
[PASS] 20: POST /api/auth/logout purges session and revokes access
...
=================================================================
  RESULT: 26 / 26 PASSED (100% SUCCESS, 0 REGRESSIONS)
=================================================================
```

---

## 9. Troubleshooting & Common Issues

### Issue 1: Port 8000 is already in use
**Symptom:** `[Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000): address already in use`  
**Solution:** Either specify an alternate port or terminate the existing process:
```powershell
# Run on port 8080 instead:
uvicorn app.main:app --port 8080 --reload
```
Or kill the process holding port 8000 on Windows:
```powershell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process -Force
```

---

### Issue 2: `503 Service Unavailable: ML Engine Unavailable`
**Symptom:** Clicking "Check with AI" returns `503 Service Unavailable`.  
**Root Cause:** The machine learning model artifacts have not yet been built.  
**Solution:** Run the build pipeline from the `backend/` folder:
```powershell
python -m ml.generate_data
python -m ml.train_classifier
python -m ml.build_index
```

---

### Issue 3: PowerShell Script Execution Policy Error
**Symptom:** `File ... activate.ps1 cannot be loaded because running scripts is disabled on this system.`  
**Solution:** Run this one-time command in your PowerShell window:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.venv\Scripts\activate
```

---

### Issue 4: FAISS Installation on Windows
**Symptom:** `ERROR: Could not find a version that satisfies the requirement faiss`  
**Solution:** The CPU version of FAISS is named **`faiss-cpu`**, not `faiss`. Always install `faiss-cpu`:
```powershell
pip install faiss-cpu
```

---

### Issue 5: First-time Model Download Latency
**Symptom:** Uvicorn hangs for 15–30 seconds during first startup.  
**Explanation:** On the first execution, `SentenceTransformers` downloads the `all-MiniLM-L6-v2` model weights (~90MB) from Hugging Face and caches them locally in `~/.cache/huggingface/hub/`. Subsequent startups load in under 1 second.

---

## 10. Quick-Start Cheat Sheet

```powershell
# 1. Open Terminal & Enter Backend
cd "c:\Users\dilan\Downloads\complaint-classifier (2)\Sana_complaint-classifier\backend"

# 2. Activate Virtual Environment
.venv\Scripts\activate

# 3. Ensure Dependencies are Installed
pip install -r requirements.txt

# 4. Generate Models (only if backend/models/ is empty)
python -m ml.generate_data
python -m ml.train_classifier
python -m ml.build_index

# 5. Start Server
uvicorn app.main:app --reload

# 6. Open Web Browser
# Visit: http://127.0.0.1:8000/
```
