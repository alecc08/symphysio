# Symphysio — App Requirements & Design Specification

## 1. Product Vision & Scope

**Symphysio** is a frictionless, mobile-first web application for tracking physiotherapy exercises and physical symptoms. The core principle is **"click and log"**: logging an exercise or symptom should take under 5 seconds with 1 to 2 taps. Behind the minimal interface sits a strictly normalized, time-indexed SQLite database built for downstream time-series visualization and lag-correlation analysis (for example, identifying whether a specific symptom consistently flares 2 to 6 hours after a particular exercise).

* **Target Repository:** `[https://github.com/alserv-org/symphysio](https://github.com/alserv-org/symphysio)` (public)
* **Deployment Model:** Single-container or single-VPS deployment serving both the API and the compiled React PWA.

---

## 2. Architecture & Technology Decisions

### Backend Evaluation & Recommendation

| Option | Attack Surface & CVE Profile | Verdict |
| --- | --- | --- |
| **Node.js + Express** | Large transitive `npm` dependency tree, frequent supply-chain and prototype-pollution CVEs. | **Avoid** for a security-first build. |
| **Python + FastAPI** | Small, auditable dependency graph when strictly pinned; Pydantic v2 enforces strict input typing at the boundary; zero `eval`/template RCE surface when serving JSON only. | **Recommended (Primary)** — optimal balance of security, development speed, and future Python analytics reuse. |
| **Go (`net/http` + `chi`)** | Compiled static binary, near-zero third-party dependencies, smallest possible CVE/RCE footprint. | **Optional Hardened Swap** — identical REST contract and SQLite schema apply if you later want a single zero-runtime binary. |

### Locked Stack (v1)

* **Backend:** Python 3.12+, **FastAPI**, **Uvicorn**, **Pydantic v2**, **aiosqlite** (raw parameterized SQL — no heavy ORM magic), **argon2-cffi** for password hashing, managed via **uv** with a locked `uv.lock`.
* **Database:** **SQLite 3** in WAL (Write-Ahead Logging) mode.
* **Frontend:** **React 19 + TypeScript + Vite**, Tailwind CSS, lightweight custom inline SVGs, and PWA manifest/meta tags.
* **Charts (Phase 2+):** Recharts or Chart.js (only added when building the Insights view).

### Security Hardening Rules (RCE & CVE Prevention)

1. **Zero dynamic execution:** Never use `eval()`, `exec()`, `pickle`, `yaml.load()`, shell commands, or server-side HTML templating. The API accepts and returns strict JSON only.
2. **Parameterized SQL exclusively:** All SQLite queries must use `?` placeholders. Dynamic column/table names are forbidden.
3. **Minimal dependency budget:** Pin exact hashes in `uv.lock` and `package-lock.json`; run `pip-audit` and `npm audit` in GitHub Actions on every push.
4. **Hardened Sessions:** Use opaque 256-bit random session tokens stored as **SHA-256 hashes** in SQLite. Deliver via `HttpOnly`, `Secure`, `SameSite=Lax` cookies (never store tokens in `localStorage`).
5. **Strict HTTP Headers & Rate Limiting:** Enforce `Content-Security-Policy` (no inline scripts), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and IP/account rate limiting on `/api/v1/auth/*`.
6. **Container Isolation:** Run the backend as a non-root user inside a minimal slim image with a read-only root filesystem (writable mount only for the `/data` SQLite directory).

### Mobile Strategy: PWA First, Native Later

Skip Flutter for v1 to avoid maintaining two UI stacks. Configure the React app as a **Progressive Web App (PWA)** so iOS Safari ("Share → Add to Home Screen") and Android Chrome launch Symphysio full-screen without browser chrome:

* Include `manifest.webmanifest` (`"display": "standalone"`), `apple-touch-icon` (180x180 PNG), `<meta name="apple-mobile-web-app-capable" content="yes">`, and `viewport-fit=cover` with CSS `env(safe-area-inset-*)` padding.
* Because all state and logic live behind a clean `/api/v1` REST contract, you can build a Flutter app or Capacitor wrapper later without rewriting a single backend route or database table.

---

## 3. Core UX & "Click and Log" Home Screen

### Home Screen Layout

A single-screen, thumb-reachable grid of large rounded tiles (minimum 120px height on mobile) with high contrast and zero clutter:

| Tile | Color Accent | Tap Flow (1 to 2 Taps) | Why It Matters |
| --- | --- | --- | --- |
| **Physio** | Calm Teal | Tap tile → tap preset exercise (or "Full Routine") → instant save (optional effort 1 to 10 or reps). | Core intervention log. |
| **Symptoms** | Warm Coral | Tap tile → tap symptom + severity (1 to 10 pill bar) → instant save (optional body area/note). | Core outcome log. |
| **Relief / Meds** *(Suggested)* | Soft Indigo | Tap tile → tap Ice, Heat, Stretch, NSAID, Rest → instant save. | Tracks confounders that mask or resolve symptoms. |
| **Triggers / Activity** *(Suggested)* | Warm Amber | Tap tile → tap Long Sitting, Heavy Lift, Run, Poor Sleep → instant save. | Prevents falsely attributing unrelated flare-ups to physio. |

### Supporting UI Elements

* **Retroactive Timestamp Strip:** Inside every quick-log drawer, default to **Now**, with 1-tap chips for **-15m**, **-1h**, **-3h**, and **Custom** so delayed logging preserves lag-correlation accuracy.
* **Undo Toast:** After any 1-tap log, display a subtle bottom pill (`"Logged: Chin Tucks · Undo"`) for 5 seconds to recover from accidental taps without adding confirmation dialogs.
* **Minimal Bottom Navigation:** 3 tabs only — **Log** (Home Grid), **History** (chronological feed with edit/delete), and **Insights** (charts & correlations). Settings live under a top-right gear icon.

---

## 4. Simple, Secure Authentication

* **Registration & Login:** Single minimal form asking only for **Email** and **Password** (minimum 12 characters, checked against common-password lists; no arbitrary symbol rules). No multi-step onboarding wizard.
* **Password Hashing:** `argon2-cffi` (Argon2id with OWASP default parameters).
* **Session Lifecycle:** 30-day rolling expiration on `HttpOnly` cookies, revocable server-side via the `sessions` table.
* **Phase 2 Upgrade:** Add **Passkeys (WebAuthn)** so iOS home-screen users log in with Face ID / Touch ID in one tap.

---

## 5. Analytics-Ready SQLite Database Schema

### SQLite Runtime Configuration

Run these pragmas on every connection initialization:

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

```

### Design Principles for Correlation & Graphing

* **Timestamps:** Store `occurred_at_utc` as Unix epoch **seconds** (`INTEGER`) for fast arithmetic lag queries, alongside `tz_offset_min` (`INTEGER`, e.g., `-300` for EST) for accurate time-of-day grouping (morning vs. evening stiffness) and `logged_at_utc` (`INTEGER`) to audit retroactive entries.
* **Normalized Catalogs:** Exercises, symptoms, and context items live in per-user definition tables (seeded with sensible defaults on signup and editable anytime) rather than free-text strings, ensuring clean grouping in graphs.
* **Strict Indexing:** Composite indexes on `(user_id, occurred_at_utc DESC)` across all log tables.

### SQL Schema (`schema.sql`)

```sql
-- 1. Users & Sessions
CREATE TABLE users (
    id              TEXT PRIMARY KEY,          -- UUIDv7
    email           TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash   TEXT NOT NULL,
    created_at_utc  INTEGER NOT NULL
);

CREATE TABLE sessions (
    token_hash      TEXT PRIMARY KEY,          -- SHA-256 hex of cookie token
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at_utc  INTEGER NOT NULL,
    created_at_utc  INTEGER NOT NULL
);
CREATE INDEX idx_sessions_user ON sessions(user_id);

-- 2. Reusable User Catalogs (Definitions)
CREATE TABLE exercise_definitions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,             -- e.g., "Wall Angels", "Glute Bridge"
    body_region     TEXT,                      -- e.g., "lower_back", "neck", "left_knee"
    default_sets    INTEGER,
    default_reps    INTEGER,
    default_sec     INTEGER,                   -- Hold duration or total time
    icon_key        TEXT NOT NULL DEFAULT 'physio',
    is_archived     INTEGER NOT NULL DEFAULT 0,
    sort_order      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_ex_def_user ON exercise_definitions(user_id, is_archived, sort_order);

CREATE TABLE symptom_definitions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,             -- e.g., "Sharp Pain", "Stiffness", "Tingling"
    default_region  TEXT,
    icon_key        TEXT NOT NULL DEFAULT 'symptom',
    is_archived     INTEGER NOT NULL DEFAULT 0,
    sort_order      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_sym_def_user ON symptom_definitions(user_id, is_archived, sort_order);

CREATE TABLE context_definitions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category        TEXT NOT NULL CHECK (category IN ('relief', 'trigger')),
    name            TEXT NOT NULL,             -- e.g., "Ice Pack", "Ibuprofen", "Long Sitting"
    icon_key        TEXT NOT NULL DEFAULT 'context',
    is_archived     INTEGER NOT NULL DEFAULT 0,
    sort_order      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_ctx_def_user ON context_definitions(user_id, category, is_archived);

-- 3. Time-Series Event Logs
CREATE TABLE exercise_logs (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exercise_id     TEXT NOT NULL REFERENCES exercise_definitions(id),
    occurred_at_utc INTEGER NOT NULL,
    logged_at_utc   INTEGER NOT NULL,
    tz_offset_min   INTEGER NOT NULL,
    sets_done       INTEGER,
    reps_done       INTEGER,
    duration_sec    INTEGER,
    effort_rpe      INTEGER CHECK (effort_rpe BETWEEN 1 AND 10),
    pain_during     INTEGER CHECK (pain_during BETWEEN 0 AND 10),
    note            TEXT
);
CREATE INDEX idx_ex_logs_time ON exercise_logs(user_id, occurred_at_utc DESC);
CREATE INDEX idx_ex_logs_def  ON exercise_logs(user_id, exercise_id, occurred_at_utc DESC);

CREATE TABLE symptom_logs (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symptom_id      TEXT NOT NULL REFERENCES symptom_definitions(id),
    body_region     TEXT,
    occurred_at_utc INTEGER NOT NULL,
    logged_at_utc   INTEGER NOT NULL,
    tz_offset_min   INTEGER NOT NULL,
    severity        INTEGER NOT NULL CHECK (severity BETWEEN 1 AND 10),
    duration_min    INTEGER,
    note            TEXT
);
CREATE INDEX idx_sym_logs_time ON symptom_logs(user_id, occurred_at_utc DESC);
CREATE INDEX idx_sym_logs_def  ON symptom_logs(user_id, symptom_id, occurred_at_utc DESC);

CREATE TABLE context_logs (
    id              TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    context_id      TEXT NOT NULL REFERENCES context_definitions(id),
    occurred_at_utc INTEGER NOT NULL,
    logged_at_utc   INTEGER NOT NULL,
    tz_offset_min   INTEGER NOT NULL,
    intensity       INTEGER CHECK (intensity BETWEEN 1 AND 10),
    note            TEXT
);
CREATE INDEX idx_ctx_logs_time ON context_logs(user_id, occurred_at_utc DESC);

-- 4. Unified Timeline View (simplifies History feed & exports)
CREATE VIEW v_unified_timeline AS
SELECT id, user_id, 'exercise' AS event_type, exercise_id AS def_id,
       occurred_at_utc, tz_offset_min, effort_rpe AS primary_metric, note
FROM exercise_logs
UNION ALL
SELECT id, user_id, 'symptom' AS event_type, symptom_id AS def_id,
       occurred_at_utc, tz_offset_min, severity AS primary_metric, note
FROM symptom_logs
UNION ALL
SELECT id, user_id, 'context' AS event_type, context_id AS def_id,
       occurred_at_utc, tz_offset_min, intensity AS primary_metric, note
FROM context_logs;

```

### Example Lag-Correlation Query

This query directly answers *"Which symptoms frequently occur 1 to 12 hours after a specific exercise?"* and feeds the Insights engine:

```sql
SELECT
    ed.name AS exercise_name,
    sd.name AS symptom_name,
    COUNT(sl.id) AS post_exercise_occurrences,
    ROUND(AVG((sl.occurred_at_utc - el.occurred_at_utc) / 3600.0), 1) AS avg_lag_hours,
    ROUND(AVG(sl.severity), 1) AS avg_severity
FROM exercise_logs el
JOIN exercise_definitions ed ON ed.id = el.exercise_id
JOIN symptom_logs sl
  ON sl.user_id = el.user_id
 AND sl.occurred_at_utc BETWEEN (el.occurred_at_utc + 3600) AND (el.occurred_at_utc + 43200)
JOIN symptom_definitions sd ON sd.id = sl.symptom_id
WHERE el.user_id = ?
GROUP BY ed.id, sd.id
HAVING COUNT(sl.id) >= 3
ORDER BY post_exercise_occurrences DESC;

```

---

## 6. REST API Contract (`/api/v1`)

| Domain | Method & Path | Purpose |
| --- | --- | --- |
| **Auth** | `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` | Account lifecycle & cookie session check. |
| **Catalog** | `GET/POST/PATCH /catalog/exercises`, `/catalog/symptoms`, `/catalog/contexts` | Manage quick-tap buttons (archive instead of hard-delete to preserve history). |
| **Logging** | `POST /logs/exercises`, `POST /logs/symptoms`, `POST /logs/contexts` | Fast single-payload event creation returning the created ID for Undo. |
| **History** | `GET /timeline?from=&to=&limit=50`, `DELETE /logs/{type}/{id}` | Unified paginated feed and Undo/delete support. |
| **Insights** | `GET /analytics/summary?days=30`, `GET /analytics/lag-correlations?min_hr=1&max_hr=12` | Daily counts, severity trends, and exercise-to-symptom lag tables. |
| **Export** | `GET /export/csv`, `GET /export/json` | One-click full data export for physiotherapists or offline analysis. |

---

## 7. Visual Design, Custom SVGs & Simple Animations

### Visual Direction

* **Palette:** Soft off-white canvas (`#F8FAFC`), pure white elevated cards (`#FFFFFF`), deep slate text (`#0F172A`), teal (`#0D9488`) for Physio, warm coral (`#E11D48` / `#F43F5E`) for Symptoms, indigo (`#4F46E5`) for Relief, amber (`#D97706`) for Triggers. Support dark mode via CSS variables (`prefers-color-scheme: dark`).
* **Typography:** System UI stack (`-apple-system, BlinkMacSystemFont, "Inter", sans-serif`) for instant load times and native iOS feel.

### Step-by-Step Guide: Creating Simple, Cohesive SVGs

Keep all iconography bespoke, geometric, and lightweight without importing giant icon packs:

1. **Standardize the Canvas & Grid:**
* Design all button icons on a `24x24` `viewBox` with a 2px safety padding (active drawing area `20x20`).
* Design home-tile hero illustrations on a `48x48` `viewBox`.


2. **Enforce Uniform Stroke Rules:**
* Always set `fill="none"`, `stroke="currentColor"`, `stroke-width="2"`, `stroke-linecap="round"`, and `stroke-linejoin="round"`. Using `currentColor` lets CSS control light/dark mode and button states automatically.


3. **Draft Using Simple Primitives:**
* Stick to basic `<path>`, `<circle>`, `<line>`, and `<rect>` elements. You can draft visually in Figma/Inkscape (aligning points to whole pixels) or hand-write simple paths.


4. **Optimize & Sanitize:**
* Run exported SVGs through **SVGO** (`npx svgo input.svg -o output.svg`) to strip editor metadata, unused IDs, and excessive decimal precision (limit to 2 decimal places).


5. **Wrap as Typed React Components:**
* Store icons in `frontend/src/components/icons/` as pure `.tsx` components accepting `className` and `aria-hidden="true"`. Never inject raw SVG strings via `dangerouslySetInnerHTML`.



#### Starter SVG Icon Components

```tsx
// Physio Tile Icon (Dynamic movement / spine wave + check arc)
export function PhysioIcon({ className = "w-8 h-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
         strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <circle cx="12" cy="5" r="2.2" />
      <path d="M7 12.5c1.8-1.5 3.2-2.5 5-2.5s3.2 1 5 2.5" />
      <path d="M12 10v5.5" />
      <path d="M9 20l3-4.5 3 4.5" />
    </svg>
  );
}

// Symptom Tile Icon (Soft pulse / sensation wave)
export function SymptomIcon({ className = "w-8 h-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
         strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M3 12h4l2.5-6 4 12 2.5-6H21" />
    </svg>
  );
}

// Animated Success Checkmark (pair with CSS stroke-dashoffset below)
export function CheckDrawIcon({ className = "w-6 h-6" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
         strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path className="animate-check-draw" d="M5 13l4 4L19 7" />
    </svg>
  );
}

```

### Simple, Purposeful Animations (CSS-Only)

Avoid heavy JS animation libraries in v1. Animate only GPU-composited properties (`transform`, `opacity`, and `stroke-dashoffset`) so 60fps holds smoothly on mobile devices:

1. **Tactile Tile Press:** Gives immediate physical confirmation on tap.
2. **SVG Checkmark Draw:** Plays inside the tile or confirmation toast when a log is saved.
3. **Bottom Sheet Slide-Up:** Smoothly reveals the quick-pick drawer without jarring screen jumps.
4. **Reduced-Motion Guard:** Respect OS accessibility settings automatically.

```css
/* 1. Tactile Home Tile Press */
.log-tile {
  transition: transform 140ms cubic-bezier(0.22, 1, 0.36, 1), box-shadow 140ms ease;
}
.log-tile:active {
  transform: scale(0.96);
}

/* 2. SVG Checkmark Stroke Draw */
.animate-check-draw {
  stroke-dasharray: 28;
  stroke-dashoffset: 28;
  animation: check-draw 280ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
@keyframes check-draw {
  to { stroke-dashoffset: 0; }
}

/* 3. Quick-Log Bottom Sheet Entrance */
.sheet-enter {
  animation: sheet-up 220ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
@keyframes sheet-up {
  from { opacity: 0; transform: translateY(20px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* 4. Accessibility Override */
@media (prefers-reduced-motion: reduce) {
  .log-tile, .animate-check-draw, .sheet-enter {
    animation: none;
    transition: none;
    stroke-dashoffset: 0;
  }
}

```

---

## 8. Repository Structure & Initialization

Create the public repository under `alserv-org` using GitHub CLI:

```bash
gh repo create alserv-org/symphysio --public --clone
cd symphysio

```

### Monorepo Layout

```text
symphysio/
├── .github/workflows/ci.yml      # pytest, ruff, pip-audit, tsc, npm audit
├── backend/
│   ├── pyproject.toml            # uv-managed minimal deps
│   ├── uv.lock
│   ├── app/
│   │   ├── main.py               # FastAPI app, security headers, SPA static serving
│   │   ├── db.py                 # aiosqlite pool + PRAGMA setup + migrations
│   │   ├── security.py           # Argon2id, opaque session cookies, CSRF check
│   │   ├── schemas.py            # Strict Pydantic v2 models
│   │   └── routers/              # auth.py, catalog.py, logs.py, analytics.py
│   └── migrations/001_init.sql
├── frontend/
│   ├── public/
│   │   ├── manifest.webmanifest  # PWA config for iOS/Android home screen
│   │   └── icons/                # 180x180 apple-touch-icon, 192/512 PNGs
│   └── src/
│       ├── api/client.ts         # Fetch wrapper with credentials: "include"
│       ├── components/icons/     # Custom inline SVGs
│       ├── pages/                # HomeGrid.tsx, History.tsx, Insights.tsx, Auth.tsx
│       └── styles/animations.css
├── Dockerfile                    # Multi-stage: build React -> copy into slim Python image
└── docker-compose.yml            # Mounts ./data:/data for persistent SQLite DB

```

---

## 9. Phased Implementation Plan

1. **Phase 1 — Core MVP:** Initialize repo, SQLite `001_init.sql` migration, Argon2id cookie auth, seeded default exercises/symptoms, React PWA Home Grid with 2-tap logging, Undo toast, and custom SVG/CSS animations.
2. **Phase 2 — Daily Utility:** Unified History timeline with inline edit/delete, Catalog manager (add/reorder/archive custom exercises and symptoms), retroactive timestamp chips, and CSV/JSON export.
3. **Phase 3 — Insights & Polish:** Frequency/severity time-series charts, automated lag-correlation cards (*"Neck stiffness appeared 4 times within 3 to 6 hours of Wall Angels"*), optional WebAuthn Passkeys, and automated SQLite daily backups (`sqlite3 .backup`).
