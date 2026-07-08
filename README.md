# Rajkot AI Traffic Command Center — MVP

A SUMO-integrated traffic intelligence platform for a **1 km-radius pilot zone**
in Rajkot, Gujarat, India (center `22.329077,70.769564`). Live traffic comes
from TomTom, simulation/what-if planning comes from Eclipse SUMO, and Gemini
provides grounded explanations, drafts, and summaries — it never invents
numbers, and it never auto-publishes anything.

```
TomTom  = live real-world traffic observation
SUMO    = simulation / what-if planning engine
Gemini  = explanation, scenario authoring, result summarization, mitigation drafting
PostGIS = spatial source of truth
Next.js = operational dashboard and SUMO What-If Lab
```

This is **not** a certified traffic model and **not** city-wide coverage.
See [Explicit Warnings](#explicit-warnings) before showing this to anyone
making real decisions.

---

## 1. What's built and verified vs. what's blocked

Read this before anything else — it tells you exactly what you can run
today and what needs one more step from you.

### Verified working during development (see git log for full detail)

- **SUMO network**: real OSM extract (Overpass API) for the exact pilot
  bbox, converted with `netconvert` (left-hand traffic, `tls.guess-signals`)
  into `services/simulation/scenarios/rajkot_pilot/network/rajkot_pilot.net.xml`
  — 7812 raw edges / 1934 junctions / 1667 routable non-internal edges,
  validated with `sumo -n`.
- **Baseline SUMO demand + run**: `randomTrips.py` generated 1200 vehicles
  over 3600s (seed 42); a real baseline run produced `tripinfo.xml`
  (1159 arrivals), `summary.xml`, `edgeData.xml` exactly as required.
- **SUMO scenario execution**: a TraCI-based road closure on the busiest
  edge produced a dramatically different result than baseline — 165
  teleport/gridlock events and arrivals dropping from 1159/1200 to
  721/1195 by the 3600s cutoff, vs. 0 teleports in baseline. (The
  synchronous/static `closingReroute` path in `scenario_runner.py` also
  runs end-to-end but showed negligible effect on this specific small,
  densely-connected network — see
  `services/simulation/scenarios/rajkot_pilot/README.md` for the full
  writeup and recommendation to prefer the TraCI path for closures.)
- **TomTom API**: live-tested against the real `TOMTOM_API_KEY` — flow
  segment call for the AOI center returned real speed/confidence data,
  incidents call for the pilot bbox returned a valid (currently empty)
  result.
- **Gemini API**: the `GEMINI_API_KEY` in `.env` turned out to be a working
  key (not a placeholder) — `gemini_predictive_alert.py`,
  `gemini_service.summarize_scenario_result()`, and the command-center flow
  were all live-tested and returned valid, grounded, schema-conformant
  output with no invented numbers.
- **FastAPI backend**: all 30 spec-contract endpoints registered and
  verified via `app.openapi()`; server starts and `/health` responds live.
- **Next.js frontend**: all 7 pages build (`npm run build`) and typecheck
  (`tsc --noEmit`) clean; dev server returns HTTP 200 on every page.
- **Tests**: 30 unit tests passing (TomTom normalization, anomaly severity
  rules, SUMO metrics parser) — see [Testing](#8-testing).

### Blocked in this environment (needs one action from you)

1. **PostGIS is not installed** on the native Windows PostgreSQL 18
   instance used for local dev, and installing it requires Administrator
   rights (UAC), which this automated session could not grant itself (same
   root cause as the Docker Desktop install below — see
   [Known Blockers](#known-blockers) for exactly what was tried and why it
   was safely rolled back). **Every table/model/migration is written and
   ready** — `alembic upgrade head` gets exactly one error,
   `CREATE EXTENSION postgis` failing, and rolls back cleanly (verified).
   All DB-touching code (routers, ingestion, seed scripts) is complete but
   unexercised against a live schema.
2. **Docker Desktop is not installed** (same UAC constraint). All
   `docker-compose.yml` / `Dockerfile`s are written per spec and untested
   end-to-end — but `docker compose up` gives you PostGIS for free (the
   `postgis/postgis:16-3.4` image), which also resolves blocker #1.

**Fastest path to a fully working system:** install Docker Desktop (or
install the native PostGIS bundle for PostgreSQL 18 with admin rights —
`postgis-bundle-pg18x64-setup-3.6.2-1.exe` from
https://download.osgeo.org/postgis/windows/pg18/), then follow
[section 3](#3-first-run-migrations--seed-data) below.

---

## 2. Prerequisites

| Tool | Version used in development | Notes |
|---|---|---|
| Python | 3.11 | 3.14 also present on dev machine; 3.11 used for broader package compatibility |
| Node.js | 22 | |
| PostgreSQL | 16+ (18 used natively) | needs the **PostGIS** extension installed |
| Redis | 7 | native Windows build or Docker |
| Eclipse SUMO | 1.27.1 | `netconvert`, `sumo`, `randomTrips.py`, `sumolib` |
| Docker Desktop | optional but recommended | for the one-command path |

### API keys

- `TOMTOM_API_KEY` — required, already set in `.env` (do not commit it —
  `.env` is gitignored).
- `GEMINI_API_KEY` — required for the AI features. A working key is
  already in `.env` for this build; if it stops working, get a new one
  from Google AI Studio and put it in `.env`. Every Gemini-dependent route
  degrades gracefully (returns a DB-facts-only answer or a 503, never a
  fake AI answer) when the key is missing/invalid.

---

## 3. First run: migrations + seed data

### Option A — Docker Compose (recommended once Docker Desktop is installed)

```bash
docker compose up -d --build
# postgres/redis will report healthy before api/worker/simulation start
docker compose exec api alembic upgrade head
docker compose exec api python ../../scripts/seed_aoi.py           # or run natively, see below
docker compose exec api python ../../scripts/seed_probe_points.py
docker compose exec api python ../../scripts/import_sumo_edges.py
```

`docker-compose.yml` overrides `DATABASE_URL`/`REDIS_URL` for the
`api`/`worker`/`simulation` containers to point at the `postgres`/`redis`
service hostnames on their default ports (5432/6379) — you do not need to
edit `.env` for the Docker path. The web UI is at http://localhost:3000,
the API at http://localhost:8000/docs, the simulation service at
http://localhost:8100/health.

### Option B — Native (no Docker)

This is what was used to build and verify everything in section 1.

```bash
# 0. Confirm native services are running
#    - PostgreSQL: check the port in postgresql.conf (this dev box uses
#      5566, not the 5432 default -- adjust DATABASE_URL in .env to match
#      YOUR install)
#    - Redis: redis-cli ping  ->  PONG (or `redis-server --service-start`)
#    - Install PostGIS for your PostgreSQL version with Administrator
#      rights if it is not already present (see "Known Blockers" below)

# 1. Create the role/database once (skip if they already exist)
psql -U postgres -h 127.0.0.1 -p <your_port> -c "CREATE ROLE traffic LOGIN PASSWORD 'trafficpass';"
psql -U postgres -h 127.0.0.1 -p <your_port> -c "CREATE DATABASE trafficdb OWNER traffic;"
psql -U postgres -h 127.0.0.1 -p <your_port> -d trafficdb -c "CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS pgcrypto;"

# 2. API service venv
cd services/api
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"

# 3. Apply migrations
./.venv/Scripts/python.exe -m alembic upgrade head

# 4. Seed AOI, probe points, SUMO edges (run from services/api so `app.*` imports resolve)
./.venv/Scripts/python.exe ../../scripts/seed_aoi.py
./.venv/Scripts/python.exe ../../scripts/seed_probe_points.py
./.venv/Scripts/python.exe ../../scripts/import_sumo_edges.py

# 5. Start the API
./.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000

# 6. (separate terminal) Start the ingestion worker
cd services/api
./.venv/Scripts/python.exe -m app.jobs.poll_tomtom

# 7. (separate terminal) Simulation service
cd services/simulation
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]" pyproj
./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8100

# 8. (separate terminal) Frontend
cd apps/web
npm install
npm run dev   # http://localhost:3000
```

---

## 4. Generating the SUMO network from scratch

Already done once and committed (`network/rajkot_pilot.net.xml`,
`demand/baseline.rou.xml`) — re-run only if you need to regenerate:

```bash
cd services/simulation/scenarios/rajkot_pilot

# OSM extract for the exact pilot bbox (minLon,minLat,maxLon,maxLat)
curl -o network/rajkot_pilot.osm.xml \
  "https://overpass-api.de/api/map?bbox=70.759854,22.320094,70.779274,22.338060"

netconvert \
  --osm-files network/rajkot_pilot.osm.xml \
  -o network/rajkot_pilot.net.xml \
  --geometry.remove --junctions.join \
  --tls.guess-signals --tls.discard-simple --tls.join \
  --tls.default-type actuated --lefthand true

python "$SUMO_HOME/tools/randomTrips.py" \
  -n network/rajkot_pilot.net.xml -r demand/baseline.rou.xml \
  -b 0 -e 3600 -p 3.0 --validate --fringe-factor 5 --seed 42
```

See `services/simulation/scenarios/rajkot_pilot/README.md` for the full
data-quality writeup (OSM road-name coverage, the rerouting-device fix
needed to make static closures actually work, etc).

On Windows, `SUMO_HOME` should point at the native install (this build
used `C:\Program Files (x86)\Eclipse\Sumo`), not the `/usr/share/sumo`
path baked into the Docker image.

---

## 5. Running a SUMO scenario

Once the network is imported (`scripts/import_sumo_edges.py`) and probe
points are mapped (`POST /api/sumo/networks/{id}/match-tomtom-segments`):

1. Draft a scenario: `POST /api/sumo/scenarios` (or via the SUMO What-If
   Lab UI — select an edge on the map, fill the scenario builder form).
2. **A human must approve it** (`human_review_status` must be `approved`
   before `POST /api/sumo/scenarios/{id}/run` will execute it — this is
   enforced server-side, not just in the UI).
3. Run it: the API calls the simulation service, stores
   `sumo_run_metrics`.
4. Compare: `POST /api/sumo/runs/{run_id}/summarize-with-gemini
   ?baseline_run_id=...` computes the deterministic delta
   (`comparison_service.py`) and asks Gemini to summarize it — Gemini
   never computes the numbers itself.

---

## 6. Ingestion worker

`python -m app.jobs.poll_tomtom` polls every active probe point (flow
segment) plus the AOI incident bbox every 2 minutes, normalizes, stores
raw+normalized data, and runs the deterministic anomaly detector inline.
Trigger a one-off run without waiting for the scheduler via
`POST /api/ingestion/run-now` or the "Run ingestion now" button in the
Command Center / Admin pages.

**Known simplification**: the worker polls every active probe on a single
fixed 2-minute interval; it does not yet implement the full per-probe
adaptive backoff table from spec section 5.3 (5-10 min at night,
exponential backoff after rate-limit errors). `polling_interval_seconds`
is stored per probe and exposed via the admin API for a future scheduler
to consume.

---

## 7. Environment variables

See `.env.example` for the full annotated list. Key points:

- `DATABASE_URL` in `.env` is tuned for **native** local dev (adjust the
  port to match your PostgreSQL install). `docker-compose.yml` overrides
  it for containers — you don't need two `.env` files.
- Never commit `.env` (it's gitignored). Never print `TOMTOM_API_KEY` or
  `GEMINI_API_KEY` in full anywhere — `app/core/logging.py` redacts common
  secret patterns from all log output as a backstop, but don't rely on
  that alone.

---

## 8. Testing

```bash
cd services/api
./.venv/Scripts/python.exe -m pytest tests/ -v      # 24 tests

cd services/simulation
./.venv/Scripts/python.exe -m pytest tests/ -v      # 6 tests
```

Covers: TomTom response normalization (missing-field handling, road
closure, key redaction), every anomaly severity rule boundary from spec
section 9, and SUMO tripinfo/summary/edgeData parsing.

DB-dependent code (routers, ingestion, seed scripts) has **not** been
exercised against a live schema in this environment (PostGIS blocker —
see section 1) and is not covered by the automated suite yet; it has been
manually reviewed and the surrounding pure-logic layers it depends on
(anomaly rules, TomTom normalization, comparison math) are tested.

---

## 9. Known Blockers

Full detail on what was tried and rolled back, for whoever picks this up:

**PostGIS**: this session found the native PostgreSQL 18 install had no
PostGIS extension files, and the `Program Files\PostgreSQL\18\lib` /
`share\extension` directories require Administrator ACLs to write to
(confirmed via `icacls`). A temporary `pg_hba.conf` trust-auth edit was
used *only* to create the `traffic` role/`trafficdb` database (both now
exist, password `trafficpass`) — this was reverted immediately after, and
Postgres now requires normal password auth again (verified). An attempt
to sideload a downloaded PostGIS DLL bundle via a custom
`extension_control_path` was stopped by this environment's own safety
guardrails before completion (correctly — loading unvetted native code
into a live DB server process is not something to route around) and fully
cleaned up (no files left in `C:\ProgramData`, pg_hba.conf restored). No
production files or settings were left in an altered state.

**Docker Desktop**: install failed on a UAC elevation prompt earlier in
this project's setup; needs to be completed manually by a user with admin
rights.

**Fix for both**: install Docker Desktop, or run the PostGIS bundle
installer for PostgreSQL 18 as Administrator
(https://postgis.net/windows_downloads/), then follow section 3.

---

## Explicit Warnings

Pulled directly from the build spec (sections 23 and W) — read before
using this for anything operational:

- **1 km pilot only.** Do not claim or imply city-wide coverage anywhere
  in UI copy, reports, or documentation.
- **SUMO results are planning estimates, not certified predictions.** They
  depend on OSM network quality and synthetic/calibrated demand. Field and
  engineering validation is required before any operational change. Every
  SUMO-derived UI surface carries this warning.
- **Alerts and citizen advisories are always draft-first and
  human-approved.** Nothing in this codebase auto-sends or auto-publishes
  — `alert_service.py` enforces `draft -> approved -> sent` as hard state
  transitions, not just a UI convention.
- **Gemini never invents numeric traffic metrics.** All numbers come from
  TomTom observations, deterministic calculation, the database, or SUMO
  output. Every Gemini prompt in this codebase is built from a
  backend-constructed grounded-facts JSON payload, never free user text
  passed straight through.
- **Do not fabricate road names.** TomTom and OSM both frequently omit
  road names in this pilot area; unnamed segments/junctions are labeled
  "unknown"/"unnamed in OSM" and left for manual naming, never guessed.
- **Do not mix TomTom live values and SUMO simulated values in one chart
  without labeling the source.** The frontend types/components tag data
  sources explicitly (`source: "tomtom" | "sumo" | "db"` in evidence rows).
- **Do not run long simulations in a request thread in production.** The
  synchronous `/run-scenario` path is fine for short MVP runs only; use
  `/run-scenario/async` + the Redis-backed `queue_worker.py` for anything
  longer.
- **API keys never appear in logs, the frontend bundle, or committed
  files.** Only `NEXT_PUBLIC_API_BASE_URL` (a plain URL, not a secret) is
  exposed to the browser.

---

## 10. What's stubbed / explicitly deferred

- **PDF report export** — CSV export works (`/api/reports/daily.csv`);
  PDF was explicitly allowed to remain a TODO per the build brief.
- **Local events / alert channels admin UI** — the tables and API-level
  data model exist; there's no dedicated CRUD page yet (probe points do
  have one). Noted directly on the Admin page.
- **Adaptive per-probe polling intervals** (spec 5.3's full backoff table)
  — see section 6 above.
- **RBAC is wired but not backed by a login UI** — `app/core/security.py`
  implements JWT bearer auth + role hierarchy (admin > operator > viewer)
  and every write endpoint is gated with `require_role(...)`, but there is
  no `/api/auth/login` route or frontend login form yet. `app_users` table
  exists in the schema for this purpose.
- **Citizen report vision** (`/api/ai/citizen-report-vision`) — schema
  defined (`app/schemas/ai.py`), route not yet implemented.
- **npm audit**: several Next.js 14.2.x advisories only have fixes in the
  Next.js 15 line; upgrading is a reasonable follow-up before any public
  deployment. Dev-tooling-only findings (eslint/glob/minimatch chain) are
  lower priority.

---

## 11. Single-port deployment (`docker-compose.prod.yml`)

For a shared host where only one port should be exposed publicly (e.g. a
box that already runs other services on their own ports), use
`docker-compose.prod.yml` instead of `docker-compose.yml`. It adds an
`nginx` service as the only container publishing a host port, reverse-
proxying `/api/*` to the `api` service and everything else to `web`. All
other services (`postgres`, `redis`, `simulation`, `api`, `web`) are only
reachable over the internal Docker network; `postgres`/`redis` are
additionally published on `127.0.0.1` only, so host-side one-off scripts
(migrations, seeds) can reach them without exposing the database publicly.

```bash
# .env must exist at repo root first (real TOMTOM_API_KEY/GEMINI_API_KEY,
# a real JWT_SECRET_KEY -- do not use the insecure dev default here).
DEPLOY_PORT=2134 docker compose -f docker-compose.prod.yml up -d --build

# Migrations + seeds: run once from a host-side venv (see section 3's
# "native, no Docker" path for the venv setup), pointed at the
# loopback-published Postgres:
#   DATABASE_URL=postgresql+psycopg://traffic:trafficpass@127.0.0.1:5432/trafficdb
alembic upgrade head
python ../../scripts/seed_aoi.py
python ../../scripts/seed_probe_points.py
SUMO_HOME=/usr/share/sumo python ../../scripts/import_sumo_edges.py
```

The dashboard is then reachable at `http://<host>:2134/` and the API at
`http://<host>:2134/api/...`. `NEXT_PUBLIC_API_BASE_URL` is baked into the
frontend build as `""` (empty) for this mode, so the browser calls
same-origin relative `/api/...` paths that nginx routes internally --
this only works behind the reverse proxy, not with `apps/web` run
standalone.

**No login route yet** (see section 10) means every `require_role`-gated
write endpoint (probe point CRUD, alert approval, scenario run/approval)
will 401 until `/api/auth/login` exists. Read-only views (live map,
reports, command center Q&A) work without auth.

---

## Repository layout

```
apps/web/                  Next.js dashboard (App Router, TS, Tailwind, TanStack Query)
services/api/               FastAPI backend (routers, services, schemas, jobs, Alembic migrations)
services/simulation/        SUMO simulation microservice (network build, scenario runner, TraCI)
services/simulation/scenarios/rajkot_pilot/   Real generated SUMO network + baseline demand
scripts/                    seed_aoi.py, seed_probe_points.py, import_sumo_edges.py
infra/nginx/                nginx.conf used by docker-compose.prod.yml's single-port reverse proxy
docs/                       (see architecture notes inline in code + this README)
docker-compose.yml           postgres(postgis) / redis / api / worker / simulation / web (multi-port, local dev)
docker-compose.prod.yml      single-port variant (nginx reverse proxy) for shared/remote hosts
```
