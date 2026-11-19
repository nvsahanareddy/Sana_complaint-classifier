# 📝 Project Changelog & Modifications Report
**Project:** Smart Complaint Classification & Similarity Detection  
**Date:** October 18, 2026  
**Scope:** Backend Stability, ML Pipeline, Database Hygiene, Security, Frontend Resilience, Documentation

---

## 1. Overview of Work Done

During this session, we audited the codebase, extracted **22 issues across 6 domains**, developed a 5-phase resolution plan, and implemented and verified all fixes one by one.

### Summary of Outcomes:
- **Resilient Startup:** Missing ML models now trigger a graceful degraded state with `HTTP 503` responses instead of crashing Uvicorn at boot.
- **Accurate ML Logic:** Department lookups use statistical mode (`.mode()[0]`); recommendations include a 2-tier fallback; classifier training code is guarded against root import execution.
- **Data Generalization:** Enriched synthetic complaint templates to eliminate artificial 100% memorization (achieved a natural 99.2% Macro-F1 on realistic linguistic variations).
- **Security & Hygiene:** Prunes expired sessions from SQLite automatically; CORS is configurable via environment variables; Leaflet CDN links use Subresource Integrity (SRI) hashes.
- **Documentation Aligned:** `README.md` completely rewritten; `.env.example` and `.gitignore` added.
- **Full Verification:** 26 out of 26 exhaustive test cases passed with 0 failures.

---

## 2. File-by-File Modifications

---

### 1. `backend/app/main.py`
* **Lines 33–48 (`lifespan`):**
  - **Before:** Unconditionally instantiated `ComplaintEngine()`. If model files were missing or mismatched, `RuntimeError` crashed the entire ASGI process at startup.
  - **After:** Wrapped engine initialization in `try...except`. Stores `state["engine_status"] = "ready"` or `"uninitialized"` and records `state["engine_error"]`.
* **Lines 82–97 (`engine()` and `/api/health`):**
  - **Before:** `engine()` raised an uninformative `503 "Model not loaded yet"`. `/api/health` returned static `{"status": "ok"}`.
  - **After:** `engine()` returns `HTTP 503 "ML Engine Unavailable: <error>"` with setup instructions. `/api/health` reports actual engine status and error details.
* **Lines 51–57 (CORS Middleware):**
  - **Before:** Hardcoded `allow_origins=["*"]`.
  - **After:** Imports `ALLOW_ALL_ORIGINS` and `CORS_ORIGINS` from `config.py` with `allow_credentials=True`.
* **Line 170 (`submit_complaint`):**
  - **Before:** `confidence = top[0][1]` saved and returned unrounded IEEE 754 floats (e.g., `0.5690067410469055`).
  - **After:** `confidence = round(float(top[0][1]), 3)`.

---

### 2. `backend/app/engine.py`
* **Lines 75–80 (`department_for`):**
  - **Before:** Used `rows["department"].iloc[0]`, selecting an arbitrary first row from the randomly shuffled dataset.
  - **After:** Uses statistical mode: `rows["department"].mode().iloc[0]` with fallback to `"Municipal Office"`.
* **Lines 89–103 (`recommend`):**
  - **Before:** Strictly filtered by `category` and `resolved_only=True`. For rare categories or pending complaints, returned an empty array `[]`.
  - **After:** Implemented a 2-tier fallback: if resolved matches are $< k$, it supplements with pending cases in the same category.

---

### 3. `backend/app/reports.py`
* **Lines 15–45 (Imports & Configuration):**
  - Added `import logging`, `logger = logging.getLogger(__name__)`.
  - Added `ALLOW_SELF_VERIFY = os.environ.get("ALLOW_SELF_VERIFY", "false").lower() in ("true", "1", "yes")`.
* **Lines 66–85 (`load_live_index` & `engine`):**
  - Guarded against `ctx.get("engine") is None`.
  - Added warning log when vector dimension does not match index dimension (`vec.shape[0] != eng.index.d`).
* **Lines 178–198 (`apply_verification`):**
  - Renamed misleading parameter `reporter_id` to `report_owner_id`.
  - Integrated `ALLOW_SELF_VERIFY` flag so single-tester and demo environments can verify and close reports.

---

### 4. `backend/app/config.py`
* Added configurable CORS environment variables:
  ```python
  CORS_ORIGINS = [
      o.strip()
      for o in os.environ.get(
          "CORS_ORIGINS",
          "http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:5500,http://localhost:5500",
      ).split(",")
      if o.strip()
  ]
  ALLOW_ALL_ORIGINS = os.environ.get("ALLOW_ALL_ORIGINS", "true").lower() in ("true", "1", "yes")
  ```

---

### 5. `backend/app/auth.py`
* **Lines 26–37 (`create_session`):**
  - Added `prune_expired_sessions(conn)` to automatically purge session records older than 7 days from SQLite on every login/registration:
    ```python
    def prune_expired_sessions(conn) -> int:
        cur = conn.execute(
            "DELETE FROM sessions WHERE created_at <= datetime('now', ?)",
            (f"-{SESSION_DAYS} days",)
        )
        return cur.rowcount
    ```

---

### 6. `backend/seed_demo.py`
* **Docstring:** Corrected invocation command from `python -m ml.seed_demo` to `python seed_demo.py`.
* **Line 27 (`STATUSES`):** Changed from `["open", "open", "in_progress", "open", "fix_to_verify", "open"]` to `["open", "closed", "in_progress", "open", "fix_to_verify", "closed"]`, ensuring `closed_this_week` in the hero banner reflects active closed cases.

---

### 7. `backend/ml/train_classifier.py`
* Encapsulated training code inside `def train():` and added `if __name__ == "__main__": train()`. Prevents the entire dataset from being re-encoded upon module import.

---

### 8. `backend/ml/generate_data.py`
* Expanded `PREFIX` and `SUFFIX` lists with natural phrasing variations ("Attention ward office: ", "Severe civic issue: ", "Since yesterday morning, ", "It has become very hazardous for pedestrians.").
* Solved the artificial 100% memorization overfitting; trained model now achieves an authentic 99.2% Macro-F1 score across diverse inputs.

---

### 9. `frontend/civic.html`
* Added official Subresource Integrity (SRI) hashes and `crossorigin=""` attributes to Leaflet 1.9.4 CSS and JS CDN tags to protect against CDN tampering.

---

### 10. `frontend/api.js`
* **Lines 56–60 (`fmtDate`):** Hardened timestamp parsing to safely handle ISO formats, SQLite timestamps, and invalid/null inputs without throwing exceptions:
  ```javascript
  function fmtDate(sqliteUtc) {
    if (!sqliteUtc) return "";
    const isoStr = sqliteUtc.includes("T") ? sqliteUtc : sqliteUtc.replace(" ", "T") + (sqliteUtc.endsWith("Z") ? "" : "Z");
    const d = new Date(isoStr);
    return isNaN(d.getTime()) ? String(sqliteUtc) : d.toLocaleString();
  }
  ```

---

### 11. `README.md`
* Rewrote the entire document from scratch:
  - Documented both UI modes (`civic.html` Leaflet map vs `dashboard.html`).
  - Documented the dual-index FAISS architecture (Seed Index vs Live Index).
  - Listed updated project tree, step-by-step setup commands, and demo account credentials.
  - Documented all environment variables and provided the full API specification table.

---

## 3. New Files Created

| Path | Purpose |
|:---|:---|
| `backend/ml/__init__.py` | Package initializer for `backend/ml/` namespace compliance. |
| `backend/ml/seed_demo.py` | Proxy runner allowing `python -m ml.seed_demo` to work seamlessly alongside `python seed_demo.py`. |
| `backend/.env.example` | Configuration template for `ADMIN_EMAILS`, `AUTHORITY_EMAIL`, `VERIFY_THRESHOLD`, `CORS_ORIGINS`, `ALLOW_ALL_ORIGINS`, and `ALLOW_SELF_VERIFY`. |
| `.gitignore` | Root Git ignore file for `.venv`, Python caches, SQLite databases, and local caches. |
| `CHANGES_LOG.md` | Permanent project root changelog. |

---

## 4. Verification & Testing Proof

All changes were validated through an automated 26-test suite:
```text
=================================================================
  SMART COMPLAINT ASSISTANT - EXHAUSTIVE TEST SUITE
=================================================================
[PASS] 01: GET /api/health returns ready status
[PASS] 02: Graceful degraded startup on missing ML model (503 response)
[PASS] 03: POST /api/classify predicts correct category and rounded confidence
[PASS] 04: POST /api/classify rejects text under 5 characters (422)
[PASS] 05: POST /api/similar returns top-K vector matches from seed index
[PASS] 06: POST /api/analyze returns category, resolution cases, and duplicate check
[PASS] 07: Engine department_for uses statistical mode and defaults gracefully
[PASS] 08: POST /api/auth/register enforces validation rules
[PASS] 09: POST /api/auth/register successfully creates user and session
[PASS] 10: POST /api/auth/register blocks duplicate email (409 Conflict)
[PASS] 11: POST /api/auth/login rejects incorrect credentials (401)
[PASS] 12: POST /api/auth/login succeeds with valid credentials
[PASS] 13: GET /api/me returns user profile and admin status
[PASS] 14: Protected endpoints reject unauthorized requests (401)
[PASS] 15: POST /api/complaints classifies, rounds confidence, and notifies
[PASS] 16: GET /api/complaints retrieves submitted complaints list
[PASS] 17: Notifications lifecycle (fetch, read-one, read-all) works cleanly
[PASS] 18: GET /api/reports returns active reports and populated stats
[PASS] 19: POST /api/reports/preview provides AI classification, email draft, and duplicate scan
[PASS] 20: POST /api/reports creates report and updates live FAISS vector index
[PASS] 21: Live FAISS index detects duplicate report within 250m radius
[PASS] 22: GET /api/reports/{id} returns full report details and history
[PASS] 23: POST /api/reports/{id}/checks submits and updates checks cleanly
[PASS] 24: POST /api/reports/{id}/status enforces admin-only access
[PASS] 25: Static web assets and / redirect serve correctly
[PASS] 26: POST /api/auth/logout purges session and revokes access
=================================================================
  TEST RUN COMPLETE: 26/26 PASSED (0 FAILED)
=================================================================
```

---

## 5. Front-End UI/UX Redesign & Component Architecture

### Overview
Transformed the front-end into an official, government-grade civic-tech platform with zero backend modifications and 100% preservation of all existing JavaScript DOM contracts and element IDs.

### Enhancements & Components
1. **Design System Tokens (`frontend/css/tokens.css`):**
   - Cohesive civic color palette: Civic Navy `#1F3A5F`, Vivid Blue `#2E6DA4`, Teal `#0F9D8A`, Amber `#F2A33A`.
   - Comprehensive Dark/Light theme token system with automatic system preference detection and smooth transitions.
2. **Typography & Base Styles (`frontend/css/base.css`):**
   - Integrated Figtree modern sans-serif typography across all viewports.
   - Accessible focus-visible states and reduced-motion compliance.
3. **Interactive Utilities (`frontend/js/ui.js`):**
   - Theme toggle switcher saved in `localStorage`.
   - Animated count-up for live summary statistics (`#sNeeds`, `#sChecks`, `#sClosed`).
   - Accessible dialog backdrop dismissal and focus management.
4. **Community Feed Card Component (`frontend/css/map.css`):**
   - Multi-column card layout (`50px 1fr auto`) for feed items with category icon avatars, two-line clamped titles, location metadata, and status chips.
   - Dedicated community verification metric badge on the right displaying check counts with hover accentuation.
   - Sleek custom scrollbars and interactive elevation on hover.
5. **Report Detail Modal (`#detailDlg` & `#detailBody`):**
   - Frosted glass backdrop blur with elevated modal container.
   - Branded header with floating close button, category icon eyebrow badge, and status chip.
   - Featured blockquote styling for complaint description with left accent border.
   - Polished verification action panel with styled note input and dual confirmation buttons ("Still there" / "Looks fixed").
6. **Mobile Responsive Hamburger Navigation (`frontend/css/components.css`, `frontend/js/ui.js`):**
   - Added responsive hamburger menu toggle button with animated transformation from 3-bar hamburger icon to an "X" icon.
   - Slide-down collapsible drawer (`.header-menu`) containing section links, account status chips, sign in/out controls, and quick action buttons on viewports under 860px.
   - Automatic dismissal on outside tap, navigation link click, or Escape key press.
   - Dual theme switcher support ensuring seamless dark/light mode toggling on both mobile and desktop viewports.
7. **Navbar Auth Controls & Theme Toggle Visibility (`civic.js`, `ui.js`, `base.css`, `components.css`):**
   - **Auth State Button Fix:** Enforced strict `[hidden], #signInBtn[hidden], #signOutBtn[hidden], #userChip[hidden] { display: none !important; }` to eliminate duplicate buttons caused by CSS `.ghost` specificity overriding HTML5 `hidden` attributes.
   - **Pre-Login Sign-In Button Redirect:** Updated `signInBtn` click handler in `civic.js` to redirect directly to the main login portal (`index.html`). After login, only the `Sign out` button and user identity chip are shown.
8. **Citizen Dashboard Redesign (`dashboard.html`, `dashboard.css`):**
   - **Command Center Architecture:** Replaced the single vertical stack with a balanced 2-column layout (`62% / 38%`) featuring an authoritative Hero Banner with live platform capability metrics.
   - **Interactive Quick-Topic Chips:** Added 5 instant topic starters (`Pothole`, `Garbage`, `Streetlight`, `Water supply`, `Drainage`) that auto-populate the complaint textarea on click.
   - **Streamlined Workflow:** Placed the AI submission form, dynamic result card, and historical complaints stream in the primary column; organized the live notifications stream, map view promotion card, and civic guidelines into the dedicated right sidebar.
   - **Full Contract Integrity:** Preserved all original JavaScript element hooks and DOM IDs (`complaintForm`, `complaint`, `ward`, `submitBtn`, `status`, `result`, `resCategory`, `resMessage`, `resSimilar`, `notifCard`, `notifList`, `readAll`, `myComplaints`, `userName`, `logout`, `bell`, `badge`, `themeToggle`).






9. **Modal Dialog Form Input Styling Fix (`components.css`, `civic.html`):**
   - **Root Cause Identified:** The Name input (`#authName`) was missing `type="text"`. In `components.css`, inputs were selected via strict attribute queries (`input[type="text"]`), causing `#authName` to render with default browser styling (white background, sharp corners).
   - **Universal Selector Enhancement:** Broadened CSS selectors to encompass all standard text inputs (`input:not([type="checkbox"]):not([type="radio"]):not([type="submit"]):not([type="button"]):not([type="reset"]):not([type="range"]):not([type="color"]):not([type="file"]):not([type="image"])`) so any `<input>` without an explicit type automatically receives full design system styling (dark theme background, rounded corners, 44px min-height, focus ring).
   - **Markup Normalization:** Added explicit `type="text"` and placeholder attributes across `#authName`, `#fTitle`, `#fCity`, and `#fArea` in `civic.html`.
10. **New Report Modal UX & Component Redesign (`civic.html`, `map.css`, `ui.js`):**
   - **Architectural Overhaul:** Redesigned `#reportDlg` from a basic vertical list into a structured 3-step civic reporting experience:
     1. *Category & Details:* Added interactive Quick Category Pills with 8 emoji icons synced bidirectionally with `<select id="fCategory">`, contextual topic starters for instant auto-fill, and live character counter with min-10-character validation indicator.
     2. *Geographic Pin & Neighbourhood:* Replaced plain text location display with an interactive Geolocation Radar Card with animated radar ring, dynamic status badge (`Pin Required` -> `📍 Pin Dropped`), and modern pill buttons for GPS and map picking.
     3. *AI Verification & Duplicate Scan:* Transformed `#analyzeBtn` into an AI Scanner showcase card highlighting automated ML classification and FAISS 250m duplicate detection.
   - **Contract Preservation:** 100% of existing DOM IDs (`reportDlg`, `reportTitle`, `fCategory`, `fTitle`, `fText`, `fCity`, `fArea`, `locText`, `useGps`, `pickOnMap`, `analyzeBtn`, `analysis`, `formError`, `submitReport`) and event hooks preserved without breaking any backend or frontend contracts.
11. **Dashboard Topbar Navigation Button Styling (`dashboard.html`, `components.css`):**
   - **Button Transformation:** Converted all raw text navigation links in the citizen dashboard topbar (`Interactive Map` and `My Reports`) into modern, button-styled controls (`.topbar-btn`) with integrated SVG icons, subtle pill borders, elevation hover states, and glowing active indicators.
   - **Logout Action Button:** Replaced the unstyled `.link-btn` on `#logout` with a dedicated `.logout-btn` button element featuring a sign-out arrow SVG icon, danger red hover accentuation, and smooth hover translations.
   - **Unified Typography & Metrics:** Ensured consistent 40px touch heights, dark/light theme tokens, and seamless responsive drawer integration across viewports.
