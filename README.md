# 🦅 PHOENIX PORTAL — Defence R&D Project Management System

[![Architecture: DRDO Cockpit Skeuomorphism](https://img.shields.io/badge/UI-Tactile%20Skeuomorphism-amber.svg)](#part-4--frontend-skeuomorphism)
[![Cache: Redis Cache-Aside](https://img.shields.io/badge/Cache-Redis%20Cache--Aside-red.svg)](#part-2--redis-cache-aside-pattern)
[![Security: Nginx Reverse Proxy & SSL](https://img.shields.io/badge/Security-Nginx%20%2B%20TLS%201.3-green.svg)](#part-5--nginx-reverse-proxy)
[![Clearance: Military RBAC](https://img.shields.io/badge/Clearance-Level%201%20to%205-blue.svg)](#military-rbac-clearance-matrix)

**Phoenix Portal** is a production-grade, tactical Defence Research & Development (DRDO-style) Project Management System engineered with **Python FastAPI**, **PostgreSQL**, **Redis Cache-Aside acceleration**, **Nginx perimeter reverse proxy with SSL termination and rate limiting**, and an **early-2010s skeuomorphic military control-panel aesthetic**.

---

## 📑 Table of Contents
1. [Core Architectural Highlights](#-core-architectural-highlights)
2. [Quickstart — Run With One Command](#-quickstart--run-with-one-command)
3. [System Architecture & Data Flows](#-system-architecture--data-flows)
4. [Redis Cache-Aside Pattern (In-Depth)](#-redis-cache-aside-pattern-in-depth)
5. [Military RBAC Clearance Matrix](#-military-rbac-clearance-matrix)
6. [Nginx Reverse Proxy & Perimeter Defense](#-nginx-reverse-proxy--perimeter-defense)
7. [Project Directory Structure](#-project-directory-structure)
8. [Step-by-Step Viva & Demo Script](#-step-by-step-viva--demo-script)
9. [Viva Q&A Defence Master Guide](#-viva-qa-defence-master-guide)
10. [Automated Performance Benchmark (load_test.py)](#-automated-performance-benchmark)

---

## ⚡ Core Architectural Highlights

| Subsystem | Technology | Architectural Role |
| :--- | :--- | :--- |
| **Backend API** | Python 3.12 + FastAPI + SQLAlchemy 2.0 | High-performance asynchronous REST API, Pydantic validation, connection pooling |
| **Relational Store** | PostgreSQL 16 Alpine | Primary ACID datastore with immutable audit logging on all mutations |
| **Cache & Sessions** | Redis 7 Alpine | **Cache-Aside pattern**, session indexing (`session:{token_hash}`), sliding TTL |
| **Reverse Proxy** | Nginx Alpine (TLS 1.2/1.3) | SSL termination, HTTP->HTTPS 301, IP forwarding, **perimeter 5 req/10s rate limit** |
| **Frontend** | Vanilla JS + HTML5 + Tailwind CSS CDN | **Tactile Cockpit Skeuomorphism** (brushed steel, 3D buttons, LEDs, radar telemetry) |
| **Authentication** | JWT (HS256) + bcrypt hashing | Token revocation via Redis session existence check (sliding expiration) |

---

## 🚀 Quickstart — Run With One Command

The entire application runs end-to-end with **one single command**:

```bash
docker compose up --build
```

### What happens automatically upon startup:
1. **PostgreSQL 16** starts up and prepares the `phoenix_portal` database.
2. **Redis 7** starts with LRU eviction and in-memory persistence.
3. The **FastAPI app container** initializes, verifies database connectivity, runs table migrations (`Base.metadata.create_all`), automatically checks and executes `seed.py` (provisioning 5 users, 10 defence projects, and initial audit logs), and starts Uvicorn with 4 workers.
4. **Nginx** validates the pre-generated 2048-bit RSA SSL certificates (`nginx/ssl/phoenix.crt`), configures perimeter rate limiting, and binds to ports `80` (HTTP) and `443` (HTTPS).

### Accessing the Portal:
- **Secure Cockpit Interface:** Open **[https://localhost](https://localhost)** (accept self-signed SSL warning).
- **HTTP Automatic Redirect:** Visiting `http://localhost` automatically redirects to `https://localhost`.
- **Direct Backend (Optional/Debug):** `http://localhost:8000` (API documentation at `http://localhost:8000/docs`).

---

## 🛠 Manual Local Run (Without Docker)

If running directly on a machine with Python, PostgreSQL, and Redis installed locally:

```bash
# 1. Install dependencies
pip install -r backend/requirements.txt

# 2. Configure environment variables (or copy .env.example to .env)
# Default expects PostgreSQL on localhost:5432 and Redis on localhost:6379

# 3. Seed the database with users and 10 realistic Indian defence projects
python scripts/seed.py

# 4. Start the FastAPI server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🔄 System Architecture & Data Flows

```
                          ┌────────────────────────────────┐
                          │   CLIENT BROWSER (Tactile UI)  │
                          └───────────────┬────────────────┘
                                          │ HTTPS (443)
                                          ▼
                      ┌────────────────────────────────────────┐
                      │             NGINX REVERSE PROXY        │
                      │ ────────────────────────────────────── │
                      │  • Port 80 -> 443 301 Redirect         │
                      │  • SSL Termination (TLS 1.2/1.3)       │
                      │  • Security Headers (HSTS, CSP, DENY)  │
                      │  • Rate Limiting (5 req / 10s per IP)  │
                      └───────────────────┬────────────────────┘
                                          │ Proxy Pass (app:8000)
                                          ▼
                      ┌────────────────────────────────────────┐
                      │         FASTAPI APPLICATION ENGINE     │
                      │ ────────────────────────────────────── │
                      │  • PyJWT Signature Verification        │
                      │  • Redis Session Token Revocation Check│
                      │  • Role-Based Clearance Guard          │
                      │  • Cache-Aside Manager (cache.py)      │
                      │  • Automated Audit Trail Dispatcher    │
                      └──────────────┬──────────────────┬──────┘
                                     │                  │
                1. Cache HIT/MISS    │                  │ 2. Primary Store /
                & Session Validation │                  │    Audit Mutation
                                     ▼                  ▼
                        ┌──────────────────┐    ┌──────────────────┐
                        │     REDIS 7      │    │  POSTGRESQL 16   │
                        │ ──────────────── │    │ ──────────────── │
                        │ • project:{id}   │    │ • users          │
                        │ • projects:list  │    │ • projects       │
                        │ • session:{hash} │    │ • audit_logs     │
                        │ • stats:dash     │    │                  │
                        └──────────────────┘    └──────────────────┘
```

---

## ⚡ Redis Cache-Aside Pattern (In-Depth)

The **Cache-Aside (Lazy-Loading)** pattern is the foundational requirement of Phoenix Portal. The application code directly orchestrates caching rather than delegating it to the database.

### 1. READ Flow (`GET /api/projects` and `GET /api/projects/{id}`):
```
Client Request ──> Compute Cache Key (e.g. "project:3" or "projects:list:p=1:s=10:...")
                         │
                         ▼
                  Check Redis Key?
                     /       \
             (HIT)  /         \  (MISS)
                   ▼           ▼
        Return cached data   Query PostgreSQL DB
        Header: X-Cache: HIT  Header: X-Cache: MISS
        Record Redis latency Store in Redis (TTL: 300s)
                             Record DB query latency
```

* **Header Telemetry:** Every response delivers `X-Cache: HIT` or `X-Cache: MISS` and `X-Response-Time-Ms: <val>`.
* **Terminal Logging:**
  ```text
  [CACHE HIT] project:3 — 3.14ms (Redis)
  [CACHE MISS] project:3 — 46.82ms (PostgreSQL)
  ```

### 2. WRITE Flow (`POST`, `PUT`, `DELETE /api/projects`):
```
Client Mutation ──> 1. Write/Commit to PostgreSQL
                         │
                         ▼
                    2. Invalidate Redis Keys (Delete, DO NOT UPDATE)
                       • Specific key: delete_cache("project:{id}")
                       • Pattern keys: delete_cache_pattern("projects:list:*")
                       • Analytics: delete_cache("stats:dashboard")
                         │
                         ▼
                    3. Write Immutable Audit Trail Entry to PostgreSQL
                       detail: "MODIFIED [MRD-2026-001]... [Cache Invalidation: project:1, 4 list keys]"
                         │
                         ▼
                    4. Log invalidation to Console:
                       [CACHE INVALIDATE] Key evicted: project:1
```

### 3. Redis Session Store & Sliding Expiration:
* When a user logs in via `POST /api/auth/login`, their session is saved in Redis as:
  ```text
  Key: session:<sha256_hash_of_jwt>
  Value: {"user_id": 1, "username": "director", "role": "DIRECTOR", "last_active": "..."}
  TTL: 1800 seconds (30 minutes)
  ```
* **Sliding Expiration:** On every authenticated request, FastAPI refreshes the key's TTL back to 1800s.
* **Instant Token Revocation (Logout):** Calling `POST /api/auth/logout` deletes `session:<token_hash>`. Even if the client presents an unexpired JWT token with a valid cryptographic signature, the request is rejected with **HTTP 401 Unauthorized** because the session key in Redis no longer exists.
* **Admin Session Inspector:** `GET /admin/sessions` scans Redis keys matching `session:*` and outputs real-time remaining TTLs and active personnel.

---

## 🛡 Military RBAC Clearance Matrix

Phoenix Portal implements strict military security levels:

| Role | Clearance Level | Credentials | Permissions & Access Scope |
| :--- | :---: | :--- | :--- |
| **DIRECTOR** | **Level 5 (Alpha)** | `director` / `Director@123` | **Full Authority:** Commission projects, update any project, delete/decommission projects, inspect active Redis sessions (`/admin.html`), view full audit vault, view user list. |
| **SCIENTIST** | **Level 3 (Tactical)** | `scientist1` / `Science@123`<br>`scientist2` / `Science@123`<br>`scientist3` / `Science@123` | **Operational:** View all projects, view dashboard, **update projects where `lead_scientist_id == current_user.id`**. Cannot delete projects or create new ones. Cannot access director admin. |
| **INTERN** | **Level 1 (Observer)** | `intern1` / `Intern@123` | **Read-Only:** View dashboard, explore projects registry, inspect project dossiers. Forbidden from mutating any project or accessing director admin (receives HTTP 403 Red Light Panel). |

---

## 🔒 Nginx Reverse Proxy & Perimeter Defense

Nginx acts as the perimeter shield with the following production-hardened configurations in `nginx/nginx.conf`:

### 1. Perimeter Rate Limiting on Login:
```nginx
# 10MB memory zone tracks ~160,000 distinct IP addresses.
# rate=30r/m (average 1 request per 2 seconds).
# burst=5 nodelay permits an initial tactical burst of 5 attempts, then hard-throttles.
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=30r/m;
limit_req_status 429;

location = /api/auth/login {
    limit_req zone=login_limit burst=5 nodelay;
    ...
}
```
* **Custom HTTP 429 JSON Error:**
  ```json
  { "detail": "Too many attempts. Access throttled." }
  ```

### 2. Strict Security Headers:
* `X-Frame-Options: DENY` (Anti-Clickjacking)
* `X-Content-Type-Options: nosniff` (Anti-MIME Sniffing)
* `Strict-Transport-Security: max-age=31536000; includeSubDomains` (Force HTTPS for 1 year)
* `Referrer-Policy: no-referrer` (Prevent metadata leakage)
* `Content-Security-Policy: default-src 'self' ...` (Whitelist authorized origins)

---

## 🎨 Part 4 — Frontend Skeuomorphism

The frontend is built with pure HTML5, vanilla JavaScript, and Tailwind CSS via CDN, styled with early-2010s tactile aerospace skeuomorphism in `frontend/static/css/skeuomorphic.css`:

1. **Metallic Textured Backdrop:** Dark charcoal & olive-drab metallic base with micro-grid scanlines and brushed carbon highlights.
2. **Raised Panels & Cards:**
   ```css
   box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15), 
               0 8px 24px rgba(0, 0, 0, 0.75);
   border: 1px solid rgba(255, 255, 255, 0.08);
   ```
3. **Tactile Push Buttons:** Physical push buttons with gradient faces, beveled top rim highlight, dark bottom shadow, and depressed `:active` transformation (`transform: translateY(3px)`).
   * **Director Actions:** Brushed-gold/amber push buttons.
   * **Standard Actions:** Gunmetal steel push buttons.
   * **Danger / Delete Actions:** Muted red military toggle-switch buttons.
4. **Cockpit Radar Cache Monitor:** A live radar/sonar instrument console embedded into every operational view. Shows animated radar sweep lines, glowing LEDs, real-time response latency (ms), and exact cache hit/miss status.
5. **Clearance Denied Red Warning Panel:** When an unauthorized role encounters HTTP 403, a military alarm dialog appears with shaking animation and red LED indicators.

---

## 📁 Project Directory Structure

```text
d:\DRDO\
├── backend\
│   ├── app\
│   │   ├── __init__.py
│   │   ├── config.py             # Environment configuration & defaults
│   │   ├── database.py           # SQLAlchemy engine & sessionmaker
│   │   ├── models.py             # SQLAlchemy models (User, Project, AuditLog)
│   │   ├── schemas.py            # Pydantic schemas for request/response validation
│   │   ├── cache.py              # Redis Cache-Aside & Session Manager
│   │   ├── auth.py               # Bcrypt hashing, PyJWT, and RBAC clearance guards
│   │   ├── audit.py              # Automated PostgreSQL audit trail logger
│   │   ├── routers\
│   │   │   ├── __init__.py
│   │   │   ├── auth_router.py    # /api/auth/login, /api/auth/logout, /api/auth/me
│   │   │   ├── projects_router.py# /api/projects CRUD with Cache-Aside
│   │   │   ├── users_router.py   # /api/users
│   │   │   ├── admin_router.py   # /admin/sessions & /api/audit-logs
│   │   │   └── stats_router.py   # /api/stats/dashboard
│   │   └── main.py               # FastAPI entrypoint, middleware, static mounts
│   ├── scripts\
│   │   ├── seed.py               # DB seeder: 5 users, 10 Indian defence projects
│   │   ├── load_test.py          # 200 GET requests performance benchmark
│   │   └── entrypoint.sh         # Container wait-for-db, auto-migrate, seed & uvicorn
│   ├── requirements.txt          # Python dependencies
│   └── Dockerfile                # Multi-stage production container
├── nginx\
│   ├── nginx.conf                # Reverse proxy, SSL, rate limiting, security headers
│   ├── generate_certs.sh         # Linux/Mac OpenSSL certificate generator
│   ├── generate_certs.ps1        # Windows PowerShell certificate generator
│   └── ssl\
│       ├── phoenix.crt           # 2048-bit RSA self-signed SSL Certificate
│       └── phoenix.key           # Private key
├── frontend\
│   ├── static\
│   │   ├── css\
│   │   │   └── skeuomorphic.css  # Skeuomorphic styling, 3D buttons, LEDs, radar
│   │   └── js\
│   │       ├── api.js            # Shared fetch wrapper tracking X-Cache & timing
│   │       └── common.js         # Header, clock, RBAC clearance modal, radar widget
│   ├── login.html                # Recessed login console, role hints, 429 counter
│   ├── dashboard.html            # 4 raised stat cards, Chart.js chart, radar monitor
│   ├── projects.html             # Project table, search/filter, LEDs, commission modal
│   ├── project-detail.html       # Single dossier, steel progress track, served-from box
│   └── admin.html                # Director console, live Redis sessions, audit vault
├── scripts\
│   ├── seed.py                   # Root-level seed script
│   └── load_test.py              # Root-level load test script
├── docker-compose.yml            # Orchestration: nginx, app, postgres, redis
├── .env.example                  # Template environment variables
├── .gitignore                    # Git exclusions
└── README.md                     # Comprehensive documentation & Viva guide
```

---

## 🎬 Step-by-Step Viva & Demo Script

Follow this exact walkthrough to demonstrate every capability required by the evaluation rubric:

### Step 1: Launch the System
```bash
docker compose up --build
```
* Point out in the console logs how **PostgreSQL** and **Redis** initialize first.
* Point out how `entrypoint.sh` runs `seed.py`, creating the 5 users and 10 realistic Indian defence projects (Agni-VI, Akash-NG, TAPAS UAV, Kaveri Engine, QRSAM, etc.).
* Point out how **Uvicorn** starts on port 8000 and **Nginx** handles port 443 with TLS 1.3.

---

### Step 2: Demonstrate Perimeter Rate Limiting on Login (HTTP 429)
1. Open **[https://localhost/login.html](https://localhost/login.html)** in the browser.
2. Click the **"AUTHENTICATE"** button rapidly 6 times in under 10 seconds with an invalid password.
3. **Observation:**
   * On the 6th attempt, Nginx's `limit_req` rule activates.
   * An amber alarm appears: **"PERIMETER RATE LIMIT EXCEEDED: HTTP 429: Max 5 attempts allowed per 10s window."**
   * The **"FAILED ATTEMPTS"** counter increments.
   * Show `nginx/nginx.conf` where `limit_req_zone` and `error_page 429 = @rate_limited` are configured.

---

### Step 3: Role 1 — Director Clearance (Level 5)
1. In the login console, click the **"👑 DIRECTOR"** button to auto-fill `director` / `Director@123`. Click **"AUTHENTICATE & ENTER PORTAL"**.
2. **Dashboard View:**
   * Point out the top header: **`[LEVEL 5 (DIRECTOR)]`** with golden amber badge and live military clock (IST/UTC).
   * Note the **CACHE MONITOR** radar panel updating in real time with response latency in milliseconds.
   * Point out the **Recent Audit Logs** table visible exclusively to the Director.
3. **Projects Registry:** Click **"Projects Registry"** in the top navigation.
   * Notice the search input and division filters ("Missile Systems", "Radar & EW", "Avionics", "Materials").
   * Point out the **"COMMISSION NEW PROJECT"** brushed-gold button (visible only to Director).
4. **Directorate Admin Panel:** Click **"Directorate Admin"** in the top navigation.
   * **Active Redis Sessions Panel:** Observe the session key hash, username (`director`), and the **Remaining TTL counting down in real-time** (auto-refreshes every 10s via `GET /admin/sessions`).
   * **Immutable Audit Trail:** Filter by `LOGIN`, `CREATE`, or `UPDATE`. Show the IP address and detailed cache invalidation logs recorded for every operation.

---

### Step 4: Demonstrate Cache HIT ➔ Edit ➔ Invalidation ➔ Cache MISS
This is the core evaluation test for Part 2:

1. In the browser, navigate to **Projects Registry** (`/projects.html`).
2. Click **"DOSSIER"** on project `#1` (`MRD-2026-001` — Agni-VI Intercontinental Guidance Module).
3. **First Read (Cache Warm-Up):**
   * Observe the top right badge: **`SERVED FROM: CACHE (REDIS)`** or **`DATABASE (POSTGRESQL)`**.
   * Click **"🔄 RE-TEST"**: The badge instantly turns bright emerald green: **`SERVED FROM: CACHE (REDIS)`** with ultra-low latency (e.g. ~2-4ms).
   * Check your terminal output:
     ```text
     [CACHE HIT] project:1 — 3.20ms (Redis)
     ```
4. **Trigger Cache Invalidation (Write Flow):**
   * Click **"ENTER EDIT MODE ✏️"**.
   * Change **Progress Percentage** from `74%` to `78%`.
   * Click **"COMMIT UPDATE (INVALIDATE CACHE)"**.
   * An alert confirms: *"Project committed to PostgreSQL. Redis cache evicted. Re-fetching data now..."*
   * Check the terminal output:
     ```text
     [CACHE INVALIDATE] Key evicted: project:1 (Redis deleted)
     [CACHE INVALIDATE] Pattern 'projects:list:*' evicted 2 key(s) (Redis deleted)
     [CACHE INVALIDATE] Key evicted: stats:dashboard (Redis deleted)
     ```
5. **Subsequent Read (Cache MISS):**
   * The page immediately reloads the project:
     ```text
     [CACHE MISS] project:1 — 42.10ms (PostgreSQL)
     ```
   * The badge shows: **`SERVED FROM: DATABASE (POSTGRESQL)`** with database query timing.
   * Click **"🔄 RE-TEST"** again: It is now cached in Redis:
     ```text
     [CACHE HIT] project:1 — 2.90ms (Redis)
     ```

---

### Step 5: Role 2 — Scientist Clearance (Level 3 & Assigned Editing)
1. Click **"DISCONNECT"** in the top header (demonstrating session revocation in Redis).
2. Login as `scientist1` / `Science@123` (Dr. Tessy Thomas, assigned lead on `MRD-2026-001`).
3. Notice top badge: **`[LEVEL 3 (SCIENTIST)]`** (Steel blue badge).
4. Notice that **"Directorate Admin"** is hidden from the navigation bar.
5. Open Project `#1` (`MRD-2026-001`): Because Dr. Tessy Thomas is the assigned Lead Scientist, the **"ENTER EDIT MODE ✏️"** button is present.
6. Now open Project `#2` (`REW-2026-002` — lead is Dr. V. K. Saraswat):
   * Notice that the **"ENTER EDIT MODE"** button is **hidden**.
   * If a scientist attempts to send a direct `PUT /api/projects/2` via curl/Postman, the backend rejects it with:
     ```json
     { "detail": "INSUFFICIENT CLEARANCE: Only the Director or assigned Lead Scientist can modify this project." }
     ```

---

### Step 6: Role 3 — Intern Clearance (Level 1 & Read-Only Guard)
1. Disconnect and login as `intern1` / `Intern@123` (Aakash Verma).
2. Notice top badge: **`[LEVEL 1 (INTERN)]`** (Olive green badge).
3. Open any project dossier:
   * Notice the clearance alert box: *"CLEARANCE RESTRICTION: Intern level 1 accounts possess read-only clearance. Modifications require Lead Scientist or Directorate authorization."*
4. Attempt to access `https://localhost/admin.html` directly in the URL:
   * The security guard intercepts the request and displays the **Red Warning Light Panel**:
     **"INSUFFICIENT CLEARANCE: Directorate Admin console is restricted to Directors."**

---

### Step 7: Automated Load Testing Benchmark
Run the automated test script to fire 200 requests and show the statistical speedup of Redis:
```bash
python scripts/load_test.py --url https://localhost --requests 200
```
* **Output:**
  * Request #1: `[MISS]` (~40-50ms) querying PostgreSQL.
  * Requests #2-200: `[HIT]` (~2-4ms) served from Redis RAM.
  * Statistical summary of Average, Max, Min, p50, p95, p99 latencies.
  * Speedup summary: **"Redis Cache-Aside is ~15x FASTER than direct DB query!"**

---

## 🎓 Viva Q&A Defence Master Guide

### Q1: Why did you choose Cache-Aside instead of Write-Through or Read-Through caching?
**Answer:**
> In **Cache-Aside (Lazy Loading)**, the application logic directly dictates cache reads and writes. On a cache miss, data is queried from PostgreSQL and written into Redis. On a mutation (write/update/delete), the cached key is invalidated (deleted) rather than updated.
> 
> **Key Advantages for Defence Systems:**
> 1. **Zero Stale Data Risk:** Updating cache in place can lead to race conditions if two updates occur concurrently. Deleting the key guarantees the next reader fetches the authoritative single source of truth from PostgreSQL.
> 2. **Memory Efficiency:** Only actively requested dossiers occupy RAM. Unqueried projects don't waste Redis memory.
> 3. **Fault Tolerance:** If Redis goes down or restarts, the application falls back transparently to PostgreSQL without failing requests.

### Q2: How do you revoke JWTs if JWT tokens are stateless?
**Answer:**
> Standard JWTs cannot be revoked until their `exp` timestamp elapses. In Phoenix Portal, we solve this using **Redis Session Revocation**:
> 1. When the user logs in, we generate the JWT access token and compute its SHA-256 hash (`token_hash`).
> 2. We store a session record in Redis at key `session:{token_hash}` with a 30-minute TTL.
> 3. On every request, our FastAPI dependency `get_current_user` checks Redis first. If `session:{token_hash}` does not exist, the request is immediately rejected with **HTTP 401 Unauthorized** — even if the JWT's cryptographic signature is completely valid.
> 4. When a user clicks "DISCONNECT", we delete the Redis session key. The token is revoked instantly.
> 5. We also implement **sliding expiration**: every active request refreshes the Redis session TTL, ensuring active operators are never abruptly kicked out.

### Q3: How does Nginx rate limiting protect the login endpoint?
**Answer:**
> Nginx uses the **Leaky Bucket algorithm** via `limit_req_zone`:
> * `limit_req_zone $binary_remote_addr zone=login_limit:10m rate=30r/m;`
> * `$binary_remote_addr` consumes only 4 bytes per client IPv4 address, allowing a 10MB zone to store state for ~160,000 distinct IP addresses.
> * `rate=30r/m` permits an average processing rate of 1 request per 2 seconds.
> * `burst=5 nodelay` allows an initial tactical burst of 5 requests within a 10-second window. Any request exceeding this limit is immediately intercepted at the edge and returned as **HTTP 429 Too Many Requests**, preventing credential brute-forcing before packets reach FastAPI.

### Q4: How is Role-Based Access Control (RBAC) enforced?
**Answer:**
> RBAC is enforced in two complementary layers:
> 1. **FastAPI Route-Level Dependencies:** Functions like `require_director` and `require_scientist_or_director` inspect the authenticated user's `role` enum. If clearance is insufficient, FastAPI returns **HTTP 403 Forbidden**.
> 2. **Resource-Level Ownership Verification:** For `PUT /api/projects/{id}`, the endpoint verifies whether the user is a `DIRECTOR` OR if `project.lead_scientist_id == current_user.id`. Even if a scientist is authenticated, they cannot modify projects assigned to a different scientist.
> 3. **Frontend UI Adaptation:** Navigation links, edit buttons, and deletion controls are conditionally rendered based on clearance, and any unauthorized access triggers the red warning panel modal.

### Q5: What security headers are configured in Nginx and why?
**Answer:**
> * `X-Frame-Options: DENY`: Blocks the portal from being embedded inside `<frame>`, `<iframe>`, or `<object>` elements, preventing Clickjacking attacks.
> * `X-Content-Type-Options: nosniff`: Instructs browsers not to sniff MIME types away from the declared `Content-Type`, preventing malicious script execution disguised as images or text.
> * `Strict-Transport-Security (HSTS)`: Forces browsers to communicate exclusively over HTTPS for 1 full year (`max-age=31536000`), protecting against SSL stripping attacks.
> * `Referrer-Policy: no-referrer`: Ensures sensitive internal URLs and parameters are never leaked in the `Referer` header to external CDNs.
> * `Content-Security-Policy (CSP)`: Enforces an explicit whitelist of allowed script, style, and font sources (self, Tailwind CDN, Google Fonts, Chart.js CDN), mitigating Cross-Site Scripting (XSS).

---

## ⚡ Automated Performance Benchmark

To execute the 200-request load test:
```bash
# Against local Docker Nginx (HTTPS)
python scripts/load_test.py --url https://localhost --requests 200

# Or against FastAPI directly (HTTP)
python scripts/load_test.py --url http://localhost:8000 --requests 200
```

### Sample Output:
```text
======================================================================
   PHOENIX PORTAL — DEFENCE R&D CACHE-ASIDE LOAD TEST BENCHMARK
======================================================================
Target URL:       https://localhost
Total Requests:   200
Authentication:   Directorate Clearance (director)
----------------------------------------------------------------------
[AUTH] Transmitting authentication handshake...
[AUTH SUCCESS] Clearance granted. JWT Access Token registered.

[BENCHMARK] Executing 200 GET requests against: /api/projects...
  Req #001 | [MISS] | Status: 200 | Client:  48.12ms | Server:  42.50ms
  Req #002 | [HIT]  | Status: 200 | Client:   4.10ms | Server:   3.20ms
  Req #003 | [HIT]  | Status: 200 | Client:   3.80ms | Server:   2.90ms
  ...
  Req #200 | [HIT]  | Status: 200 | Client:   3.50ms | Server:   2.70ms

======================================================================
                    PERFORMANCE TELEMETRY REPORT
======================================================================
Total Requests Executed:    200
Cache Hits (Redis):         199 (99.5%)
Cache Misses (PostgreSQL):  1 (0.5%)
----------------------------------------------------------------------
PostgreSQL Query Latency (MISS):
  - Average:                48.12 ms
  - Max:                    48.12 ms
  - Min:                    48.12 ms

Redis Cache-Aside Latency (HIT):
  - Average:                3.42 ms
  - Max:                    6.10 ms
  - Min:                    2.50 ms
  - 50th Percentile (p50):  3.20 ms
  - 95th Percentile (p95):  4.50 ms
  - 99th Percentile (p99):  5.20 ms
----------------------------------------------------------------------
[SPEEDUP ACCELERATION] Redis Cache-Aside is 14.1x FASTER than direct DB query!
======================================================================
```

---

## 👥 Seed Accounts Reference

| Role | Username | Password | Full Name | Lab Division |
| :--- | :--- | :--- | :--- | :--- |
| **DIRECTOR** | `director` | `Director@123` | Dr. G. Satheesh Reddy | Directorate General |
| **SCIENTIST** | `scientist1` | `Science@123` | Dr. Tessy Thomas (Agni Lead) | Missile Systems |
| **SCIENTIST** | `scientist2` | `Science@123` | Dr. V. K. Saraswat (Radar Lead) | Radar & EW |
| **SCIENTIST** | `scientist3` | `Science@123` | Dr. K. Sivan (Avionics Lead) | Avionics |
| **INTERN** | `intern1` | `Intern@123` | Aakash Verma (Research Fellow) | Materials |

---

## 📜 Licence & Defence Classification
**RESTRICTED — DEFENCE R&D ESTABLISHMENT USE ONLY.**  
All access attempts, mutations, and session revocations are permanently audited in the immutable PostgreSQL audit vault.
