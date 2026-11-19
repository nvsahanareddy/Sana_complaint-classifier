# 🧪 Full Testing Report
### Smart Complaint Classification & Similarity Detection
*Tested on: 2026-10-17 | Server: http://127.0.0.1:8000*

---

## ✅ Setup Results

| Step | Result |
|---|---|
| `python -m ml.generate_data` | ✅ 640 complaints saved (80 per category × 8 categories) |
| `python -m ml.train_classifier` | ✅ 100% F1 score on all 8 categories |
| `python -m ml.build_index` | ✅ 640 vectors indexed at 384 dimensions |
| `python seed_demo.py` | ✅ 12 demo map reports already existed |
| `uvicorn app.main:app --reload` | ✅ Server started on http://127.0.0.1:8000 |

---

## 🧪 Test Results (22 Tests)

---

### TEST 1 — Health Check `GET /api/health`
- **Result:** ✅ PASS
- **Response:** `{"status": "ok"}`

---

### TEST 2 — Classify Complaint `POST /api/classify`
- **Input:** `"Big pothole near the school causing accidents for two wheelers"`
- **Result:** ✅ PASS
- **Response:**
  - Category: **Roads and Potholes**
  - Confidence: **84.1%**
  - Top 3: Roads and Potholes (84.1%), Drainage and Sewage (4.9%), Garbage and Sanitation (3.3%)
- **Notes:** Classification is accurate and meaningful.

---

### TEST 3 — Similar Complaints `POST /api/similar`
- **Input:** `"Garbage not collected for a week, smells terrible"`
- **Result:** ✅ PASS
- **Response:** 3 similar matches returned
  - Complaint 172: 78.8% similar — "Garbage not collected in Koramangala" (Resolved)
  - Complaint 166: 78.2% similar — "Garbage not collected in Jayanagar" (Resolved)
  - Complaint 206: 76.1% similar — same text variant (Pending)
- **Notes:** FAISS search works correctly. Similarity scores are realistic.

---

### TEST 4 — Full Analysis `POST /api/analyze`
- **Input:** `"Street light is broken near the park, area is very dark and unsafe at night"`
- **Result:** ✅ PASS
- **Response:**
  - Category: **Street Lights**, Confidence: **87.4%**
  - 3 similar **resolved** complaints returned
  - First match: 74.9% similar, resolved in 13 days
  - `possible_duplicate: false` (correct — different location)

---

### TEST 5 — User Registration `POST /api/auth/register`
- **Input:** `name=Test User, email=testuser_new@example.com, password=test123`
- **Result:** ✅ PASS
- **Response:** User created with ID=4, token returned immediately
- **Notes:** PBKDF2-SHA256 hashing working. Auto-login on register works.

---

### TEST 6 — Submit Complaint `POST /api/complaints`
- **Input:** `"Sewage overflowing on the road in Koramangala and entering nearby houses"`
- **Result:** ✅ PASS (with a bug noted — see Bug #1 below)
- **Response:**
  - Complaint ID: 1, Category: **Drainage and Sewage**
  - Confidence: `0.5690067410469055` ← **⚠️ Not rounded (Bug #1)**
  - Department: Sewerage Board
  - Status: Submitted
  - Notification: "Complaint #1 was classified as Drainage and Sewage and sent to Sewerage Board. Similar complaints were usually resolved in about 7 day(s)."
  - 5 similar matches returned
  - Possible duplicate: False

---

### TEST 7 — Get My Complaints `GET /api/complaints`
- **Result:** ✅ PASS
- **Response:** 1 complaint listed with correct category, status, ward

---

### TEST 8 — Get Notifications `GET /api/notifications`
- **Result:** ✅ PASS
- **Response:** 1 unread notification — "Complaint received"
- **Notes:** Notification was auto-created when complaint was submitted.

---

### TEST 9 — Mark Single Notification Read `POST /api/notifications/{id}/read`
- **Result:** ✅ PASS
- **Response:** `{"ok": true}`

---

### TEST 10 — Mark All Notifications Read `POST /api/notifications/read-all`
- **Result:** ✅ PASS
- **Response:** `{"ok": true}`

---

### TEST 11 — List Map Reports `GET /api/reports`
- **Result:** ✅ PASS
- **Response:**
  - 13 total reports on the map
  - Stats: needs_attention=13, checks=5, closed_this_week=0
  - Sample reports: Garbage/Sanitation, Noise/Pollution, Drainage, Encroachment
  - Reports have correct lat/lng, area, city, status

---

### TEST 12 — Get Current User `GET /api/me`
- **Result:** ✅ PASS
- **Response:** User ID, name, email returned. `is_admin: false` (correct)

---

### TEST 13 — Report Detail `GET /api/reports/{id}`
- **Result:** ✅ PASS
- **Response:**
  - Title, category, status, reporter shown
  - 1 community check listed
  - 3 past similar cases shown
  - Typical resolution: 7 days

---

### TEST 14 — AI Preview Before Submit `POST /api/reports/preview`
- **Input:** "Broken street light near junction" in Koramangala (with lat/lng)
- **Result:** ✅ PASS
- **Response:**
  - Category: Street Lights (80.3% confidence)
  - Department: Electricity Department
  - Typical resolution: 8 days
  - 0 possible duplicates (correct — first such report in area)
  - 3 past cases shown
  - Draft email subject generated: `[Street Lights] Broken street light - Koramangala, Bengaluru`

---

### TEST 15 — Create Map Report `POST /api/reports`
- **Input:** Full report with title, text, category, city, area, lat, lng
- **Result:** ✅ PASS
- **Response:** Report ID=14 created, status=open, correctly assigned to Electricity Department

---

### TEST 16 — Community Check `POST /api/reports/{id}/checks`
- **Input:** `kind=still_there, note="Still broken this morning, very dark at night"`
- **Result:** ✅ PASS
- **Response:** `ok=True, status=open` (status unchanged — needs more checks to progress)

---

### TEST 17 — Invalid Category Rejected `POST /api/reports` with `FAKE_CATEGORY`
- **Result:** ✅ PASS — Correctly returned **422 Unprocessable Entity**

---

### TEST 18 — Non-Admin Status Change Blocked
- **Result:** ✅ PASS — Correctly returned **403 Forbidden**

---

### TEST 19 — Duplicate Detection `POST /api/reports/preview`
- **Input:** Similar text to the just-created street light report, same lat/lng
- **Result:** ✅ PASS — **Duplicate correctly detected!**
  - Similarity: 86.1% (above the 85% threshold)
  - Distance: 0 metres (same coordinates)
  - System correctly flagged it as a possible duplicate

---

### TEST 20 — Logout `POST /api/auth/logout`
- **Result:** ✅ PASS
- **Response:** `{"ok": true}`, session deleted from DB

---

### TEST 21 — Token Rejected After Logout
- **Result:** ✅ PASS — Correctly returned **401 Unauthorized**
- **Notes:** Token is properly invalidated on logout.

---

### TEST 22 — Input Validation Edge Cases
| Sub-test | Expected | Result |
|---|---|---|
| 22a. Text < 5 chars on /classify | 422 | ✅ PASS |
| 22b. Invalid email on register | 422 | ✅ PASS |
| 22c. Duplicate email registration | 409 Conflict | ✅ PASS |
| 22d. Wrong password login | 401 Unauthorized | ✅ PASS |
| 22e. Non-existent report (id=99999) | 404 Not Found | ✅ PASS |
| 22f. k=0 out of range | 422 | ✅ PASS |
| 22g. No auth header on protected route | 401 | ✅ PASS |

---

## 📊 Overall Test Summary

| Category | Tests | Passed | Failed |
|---|---|---|---|
| ML Endpoints | 4 | 4 | 0 |
| Authentication | 5 | 5 | 0 |
| Complaints/Notifications | 5 | 5 | 0 |
| Map Reports & Checks | 5 | 5 | 0 |
| Validation & Security | 7 | 7 | 0 |
| **TOTAL** | **22** | **22** | **0** |

---

## 🐛 Bugs Found During Live Testing

---

### BUG FOUND #1 — Confidence Not Rounded in `/api/complaints` Response
**Severity:** 🟡 Medium
**Endpoint:** `POST /api/complaints`
**File:** [`backend/app/main.py`](file:///c:/Users/dilan/Downloads/complaint-classifier%20(2)/Sana_complaint-classifier/backend/app/main.py#L157) — line 157

**Observed:**
```json
"confidence": 0.5690067410469055
```
**Expected:**
```json
"confidence": 0.569
```
**Why it happens:** In `/api/analyze` (line 106), confidence is rounded: `round(top[0][1], 3)`. But in `/api/complaints` (line 157), the raw float is saved directly to the database and returned without rounding.

**Fix:**
```python
# Line 157 in main.py — change:
confidence = top[0][1]
# to:
confidence = round(top[0][1], 3)
```

---

### BUG FOUND #2 — Classifier 100% Accuracy is Suspicious (Overfitting)
**Severity:** 🟡 Medium
**File:** `backend/ml/train_classifier.py`

**Observed:** Both TF-IDF and embedding classifiers achieved **100% F1 score** on the test set. This sounds great but is actually a warning sign.

**Why it happens:** The synthetic data has very repetitive template-based text (e.g., "Garbage has not been collected in {ward} for a week"). The classifier memorizes the templates rather than learning to understand civic complaint language. On **real-world complaints** with different wording, the accuracy would likely be much lower.

**Impact:** The app will work well with synthetic data but may misclassify real complaints.

**Fix:** Replace `ml/generate_data.py`'s template-based data with real civic complaint data, or add more linguistic variation to the templates.

---

### BUG FOUND #3 — `GET /api/reports` Has No Authentication Required
**Severity:** 🟢 Low
**Endpoint:** `GET /api/reports`
**File:** [`backend/app/reports.py`](file:///c:/Users/dilan/Downloads/complaint-classifier%20(2)/Sana_complaint-classifier/backend/app/reports.py#L226) — line 226

**Observed:** The map reports list (including lat/lng of all reports) is publicly visible without any login. Anyone can access all user-submitted location data.

**Impact:** Privacy concern — location data of all reports is exposed publicly.

**Note:** This may be intentional (public map), but it should be a documented design decision.

---

### BUG FOUND #4 — `checks` Won't Trigger Status to `closed` for Reporter's Own Report
**Severity:** 🟡 Medium
**File:** [`backend/app/reports.py`](file:///c:/Users/dilan/Downloads/complaint-classifier%20(2)/Sana_complaint-classifier/backend/app/reports.py#L172) — `apply_verification()`

**Observed:** In Test 16, the reporter added a `still_there` check on their own report. The `apply_verification` function **excludes the reporter's own checks** from the count. However, in the test environment with only one user account, this means:
- Only 1 user exists to add checks
- The reporter IS the user → their checks are always excluded
- The report can **never progress to `closed`** in a single-user test scenario

**Impact:** In a real deployment with multiple users this is correct behaviour. But with demo/test data it makes verification impossible to demonstrate.

---

### BUG FOUND #5 — `stats.closed_this_week` Always Shows 0
**Severity:** 🟢 Low
**Endpoint:** `GET /api/reports` → `stats.closed_this_week`
**File:** [`backend/app/reports.py`](file:///c:/Users/dilan/Downloads/complaint-classifier%20(2)/Sana_complaint-classifier/backend/app/reports.py#L240) — line 240

**Observed:** Even though demo reports exist with status `fix_to_verify` and `in_progress`, `closed_this_week` is always 0 because **no report has ever been moved to `closed`** (requires admin or neighbour verification threshold).

**Impact:** The stats card always shows 0, making it look like the feature is broken. It would be better to seed at least one closed report in `seed_demo.py`.

---

## 📋 Summary of New Bugs Found During Testing

| # | Severity | Location | Issue |
|---|---|---|---|
| 1 | 🟡 Medium | `main.py:157` | Confidence not rounded in `/api/complaints` response |
| 2 | 🟡 Medium | `train_classifier.py` | 100% accuracy = overfitting on synthetic templates |
| 3 | 🟢 Low | `reports.py:226` | Map reports publicly accessible — location privacy |
| 4 | 🟡 Medium | `reports.py:apply_verification()` | Reporter's own checks excluded — can't verify in single-user test |
| 5 | 🟢 Low | `reports.py:240` + `seed_demo.py` | `closed_this_week` always 0, no closed demo reports seeded |

---

*Combined with the 13 bugs from the initial code analysis, there are now **18 total known issues** in this project.*
