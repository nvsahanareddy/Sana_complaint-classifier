# 🏛️ Smart Complaint Classification & Similarity Detection

A modern civic issue reporting and verification platform powered by **FastAPI**, **Sentence Transformers**, **FAISS Vector Search**, and **Leaflet.js**.

---

## 🌟 Key Features

1. **AI Issue Classification**: Auto-categorizes citizen reports into 8 civic departments (Roads, Water, Sanitation, Lights, Drainage, Transport, Pollution, Encroachment) with confidence scores.
2. **Dual-Index Vector Search**:
   - **Seed Index (`complaints.faiss`)**: Cosine similarity search against historical resolved complaints to recommend past resolution steps and estimated resolution times.
   - **Live Index (`LiveIndex`)**: Dynamic in-memory FAISS index built on startup from SQLite BLOB vectors to detect nearby duplicate reports in real-time ($\ge 0.75$ similarity within $250\text{ m}$).
3. **Interactive Neighbourhood Map**: Pin civic issues geographically on an OpenStreetMap (Leaflet.js) interface with city-level navigation (Bengaluru, Delhi, Mumbai, Chennai, Hyderabad, Kolkata, Pune).
4. **Community Verification Workflow**: Issues transition through `open` → `in_progress` → `fix_to_verify` → `closed`. Issues are confirmed and closed when neighbours verify the fix.
5. **AI Pre-Submission Preview & Email Drafting**: Generates a summary, duplicate check, and pre-formatted authority email draft before report submission.
6. **Graceful Degraded Mode**: Health checks remain functional even if ML models are uninitialized, returning informative `503 Service Unavailable` statuses on ML endpoints.

---

## 📁 Project Structure

```
complaint-classifier/
├── README.md
├── .gitignore
├── frontend/                          -> User interfaces
│   ├── civic.html                     (Primary UI: Interactive Leaflet map)
│   ├── civic.js                       (Map interactions, report dialog, AI preview)
│   ├── civic.css                      (Modern design system & theme)
│   ├── index.html                     (Legacy login / registration page)
│   ├── login.js                       (Auth form handling)
│   ├── dashboard.html                 (Legacy complaint dashboard)
│   ├── dashboard.js                   (Complaint list & notifications)
│   ├── api.js                         (Shared API client & utilities)
│   └── style.css                      (Legacy styling)
└── backend/                           -> API + ML Engine
    ├── requirements.txt
    ├── seed_demo.py                   (Seed 12 Bengaluru demo reports & accounts)
    ├── .env.example                   (Configuration template)
    ├── app/                           -> FastAPI application
    │   ├── main.py                    (API router, CORS, lifespan, static mount)
    │   ├── engine.py                  (ML classifier, FAISS search, recommenders)
    │   ├── reports.py                 (Map reports, LiveIndex, checks, auth)
    │   ├── auth.py                    (PBKDF2-SHA256 hashing, session management)
    │   ├── db.py                      (SQLite schema init & connect helper)
    │   └── config.py                  (Paths, thresholds, environment settings)
    ├── ml/                            -> ML training & indexing pipeline
    │   ├── __init__.py
    │   ├── generate_data.py           (Synthetic dataset generator)
    │   ├── train_classifier.py        (Trains LR model on sentence embeddings)
    │   ├── build_index.py             (Encodes dataset & builds FAISS index)
    │   └── seed_demo.py               (Proxy runner for seed script)
    ├── data/
    │   ├── complaints.csv             (Generated dataset: 640 complaints)
    │   └── app.db                     (SQLite database: users, reports, checks)
    └── models/
        ├── classifier.joblib          (Trained Logistic Regression model)
        ├── complaints.faiss           (FAISS seed index)
        └── embeddings.npy             (Normalized float32 embeddings cache)
```

---

## 🚀 Setup & Execution

### 1. Environment Setup
```powershell
# Navigate to backend directory
cd backend

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell
# source .venv/bin/activate     # macOS / Linux

# Install dependencies
pip install -r requirements.txt
```

### 2. Build ML Artifacts (First-time only)
Run these commands in order from the `backend/` folder:
```powershell
python -m ml.generate_data       # Generates backend/data/complaints.csv
python -m ml.train_classifier    # Trains model -> backend/models/classifier.joblib
python -m ml.build_index         # Builds FAISS index -> backend/models/complaints.faiss
```

### 3. Seed Demo Data (Optional)
Populate the interactive map with 12 sample reports across Bengaluru:
```powershell
python seed_demo.py
# Or: python -m ml.seed_demo
```
**Demo Accounts:**
- `demo.reporter@example.com` (Password: `demo-pass-123`)
- `demo.neighbour@example.com` (Password: `demo-pass-123`)

### 4. Start the Application
```powershell
uvicorn app.main:app --reload
```

---

## 🌐 Application Access Points

| URL | Purpose |
|---|---|
| `http://127.0.0.1:8000/` | **Primary Interface** (`civic.html` — interactive map) |
| `http://127.0.0.1:8000/dashboard.html` | Legacy text-based complaint dashboard |
| `http://127.0.0.1:8000/index.html` | Legacy login / registration |
| `http://127.0.0.1:8000/docs` | Swagger interactive API documentation |
| `http://127.0.0.1:8000/redoc` | ReDoc API specifications |

---

## ⚙️ Environment Configuration

Copy `backend/.env.example` to `backend/.env` to customize settings:

```bash
# Admin & Authority Settings
ADMIN_EMAILS=admin@example.com,desk@city.gov   # Emails allowed to modify report statuses
AUTHORITY_EMAIL=grievance@city.gov             # Target address for generated email drafts
VERIFY_THRESHOLD=2                             # Community checks needed to close a report

# Security & CORS Settings
ALLOW_ALL_ORIGINS=true                         # Set false in production
CORS_ORIGINS=http://127.0.0.1:8000,http://localhost:8000

# Testing Flags
ALLOW_SELF_VERIFY=false                        # Set true to test report closure with a single account
```

---

## 🔌 API Reference

### Health & Core ML
| Method | Route | Auth | Description |
|---|---|:---:|---|
| `GET` | `/api/health` | No | System health check and ML engine status (`ready` / `uninitialized`) |
| `POST` | `/api/classify` | No | Returns predicted category, confidence, and top-3 distributions |
| `POST` | `/api/similar` | No | Returns Top-K similar complaints from seed FAISS index |
| `POST` | `/api/analyze` | No | Combines classification with similar resolved complaints and resolution days |

### Authentication
| Method | Route | Auth | Description |
|---|---|:---:|---|
| `POST` | `/api/auth/register` | No | Create user account, hash password via PBKDF2, return token |
| `POST` | `/api/auth/login` | No | Verify credentials, prune expired sessions, return session token |
| `POST` | `/api/auth/logout` | Bearer | Terminate session and invalidate token |
| `GET` | `/api/me` | Bearer | Get current user profile and `is_admin` status |

### Civic Map Reports & Community Checks
| Method | Route | Auth | Description |
|---|---|:---:|---|
| `GET` | `/api/reports` | No | List all map reports and headline stats (`needs_attention`, `checks`, `closed_this_week`) |
| `POST` | `/api/reports/preview` | Bearer | AI pre-submission check: category, duplicate detection, past cases, email draft |
| `POST` | `/api/reports` | Bearer | Create map report and insert embedding into live FAISS index |
| `GET` | `/api/reports/{id}` | No | Fetch detailed report info, neighbour checks, and past cases |
| `POST` | `/api/reports/{id}/checks` | Bearer | Add community verification check (`still_there` / `looks_fixed`) |
| `POST` | `/api/reports/{id}/status` | Admin | Change report status (`open`, `in_progress`, `fix_to_verify`, `closed`) |

### Complaints (Legacy Dashboard)
| Method | Route | Auth | Description |
|---|---|:---:|---|
| `POST` | `/api/complaints` | Bearer | Submit complaint, auto-classify, check duplicates, create notification |
| `GET` | `/api/complaints` | Bearer | List complaints filed by current user |
| `GET` | `/api/notifications` | Bearer | List user notifications and unread count |
| `POST` | `/api/notifications/{id}/read`| Bearer | Mark single notification as read |
| `POST` | `/api/notifications/read-all` | Bearer | Mark all notifications as read |

---

## 🧪 Testing

Execute automated tests against the backend:
```powershell
# In backend/ with .venv active:
python -c "from app.main import app; from fastapi.testclient import TestClient; client = TestClient(app); print(client.get('/api/health').json())"
```
