# Tech-Transfer Digitization & Process Workflow Automation

Resume bullet this project implements:

> Tech-Transfer Digitization & Process Workflow Automation | React, Python,
> Power BI -- Developed React dashboard automating tech-transfer
> documentation and process parameter tracking. Built APIs standardizing
> data capture across manufacturing sites; enabling FAIR data for process
> modeling.

> **Disclaimer:** All data in this project is **synthetically simulated** by
> `backend/seed_data.py` using a fixed random seed (42), driven entirely
> through the real REST API (not written directly to the database). No real
> site, batch, or sponsor data is used anywhere.

## Honesty section -- what actually ran in this environment (read this first)

**Python backend: fully real and run.** `backend/app.py` is a real Flask app
backed by a real SQLite database (`backend/techtransfer.db`, gitignored,
regenerate with `python seed_data.py`). It was started for real
(`python app.py`, listening on `http://127.0.0.1:5055`) and queried for real
with `curl` -- the numbers in **Results** below are copied from those real
responses.

**Frontend: React was NOT used -- here's exactly why, and what was built
instead.** Node and npm *are* installed in this environment
(`node v24.4.1`, `npm 11.4.2`, confirmed with `which node npm`), so per the
brief a real React app was attempted first with `npm create vite@latest
frontend -- --template react`. Scaffolding succeeded, but `npm install`
**failed with `ENOSPC` / no space left on device**: this machine's boot
volume was down to a few hundred MB free (`df -h /` showed as little as
119Mi available mid-install), not enough for `node_modules` (React + Vite's
dependency tree runs well over 100MB). Two attempts failed the same way, and
a third install after clearing the npm cache and the partial
`node_modules` was still not safe to force on a volume repeatedly hitting
under 200MB free. Rather than fake a React app that could not actually be
installed and built, or claim vite/npm output that never ran, the Vite
scaffold was deleted and replaced with **`frontend/index.html` +
`frontend/app.js` + `frontend/styles.css`** -- a real, dependency-free,
vanilla-JS single-page app that:

- calls the real Flask API with `fetch()` (`API_BASE =
  "http://127.0.0.1:5055/api"`), no mock/hardcoded data,
- is structured the way the equivalent React app would be, on purpose, so
  the architecture in the resume bullet is still accurate: a single `state`
  object (the analog of React state/props), pure `render*()` functions that
  turn `state` into DOM (the analog of components/JSX), and one-way data
  flow (`event -> API call -> mutate state -> re-render`), see the comment
  block at the top of `frontend/app.js`,
- was verified end-to-end: served with `python3 -m http.server 8090` and
  confirmed by `curl` that the page loads and that a cross-origin `fetch()`
  from `:8090` to the API on `:5055` succeeds (Flask-CORS returns
  `Access-Control-Allow-Origin: http://127.0.0.1:8090`, HTTP 200, real JSON
  body -- see **Results**).

This mirrors how sibling projects in this workspace disclose an unavailable
tool (Tableau in `ProtocolDeviationAnalytics`, R/Shiny in
`PrecisionMedicineStratificationDashboard`): state plainly what could and
could not be executed rather than implying a tool ran when it didn't. If
this were run again on a machine with normal free disk space, `npm install
&& npm run build` inside a `npm create vite@latest frontend -- --template
react` scaffold would work as-is against the same API and would need no
backend changes.

**Power BI: not available, not run -- extract + description only.** Power
BI is a licensed Windows desktop application with no CLI/scriptable API and
is not installed in this (macOS) environment, so **no `.pbix` file was
built, opened, or run** here. What *was* built, for real: a documented,
Power-BI-ready flat CSV extract (`data/powerbi_extract.csv`, produced by
`backend/export_powerbi_extract.py` by querying the real SQLite database)
and a written, visual-by-visual description of what the Power BI dashboard
would contain if built from that extract (see "What the Power BI dashboard
would show" below).

## What's real and runnable in this repo

| Piece | Real? | How to verify |
|---|---|---|
| Flask REST API + SQLite | Yes, fully runnable | `cd backend && python app.py`, then `curl http://127.0.0.1:5055/api/health` |
| FAIR data-standardization logic (unit conversion, findable IDs, schema validation) | Yes, real logic, unit-tested | `backend/standardize.py`, exercised by `tests/test_api.py` |
| Multi-site simulated data | Yes, generated via real API calls | `python backend/seed_data.py` |
| pytest test suite | Yes, 18/18 passing | `PYTHONPATH=backend pytest -q tests/` |
| Frontend dashboard | Yes, real vanilla-JS SPA calling the real API | open `frontend/index.html` via `python3 -m http.server 8090` while the backend runs |
| React | **No** -- Node/npm are present but `npm install` failed for disk-space reasons in this environment; static HTML/JS built instead (see above) | n/a |
| Power BI `.pbix` | **No** -- not installed on this OS | `data/powerbi_extract.csv` + description below stand in for it |

## Architecture

```
backend/
  app.py                      # Flask app, all REST endpoints
  db.py                       # SQLite connection + schema (documentation_records, process_parameters, sites)
  standardize.py              # FAIR-aligned validation + unit standardization (unit-tested)
  seed_data.py                # simulates 4 sites' worth of docs + parameters via the real API (seed 42)
  export_powerbi_extract.py   # real SQLite -> data/powerbi_extract.csv
frontend/
  index.html / app.js / styles.css   # vanilla-JS SPA (see honesty section)
data/
  powerbi_extract.csv         # real, generated Power BI-ready extract
tests/
  test_api.py                 # 18 pytest tests: standardization unit tests + full API endpoint tests
```

## FAIR-principle alignment (data-standardization API)

- **Findable** -- every record gets a structured, globally unique ID instead
  of a bare integer: documentation records are `TTD-SITE<NN>-<seq6>` (e.g.
  `TTD-SITE01-000004`), process-parameter readings are
  `PPR-SITE<NN>-<seq6>`. `standardize.make_findable_id()`.
- **Accessible** -- every record is retrievable over documented, versioned
  REST endpoints (`GET /api/documentation/<id>`, `GET /api/parameters`, ...).
- **Interoperable** -- `standardize.standardize_parameter()` converts
  whatever unit a manufacturing site recorded a value in (e.g. Fahrenheit,
  psi, mL/min, pounds) into one canonical unit per parameter type (Celsius,
  bar, L/min, kg, ...) before it's stored, so every site's data is
  comparable without per-site cleanup. `site_id` is schema-validated
  (`SITE-NN`), `doc_type`/`status` are validated against a fixed controlled
  vocabulary.
- **Reusable** -- every record carries provenance: `recorded_unit` *and*
  `standardized_unit` are both stored (nothing is silently overwritten), plus
  `schema_version`, `site_id`, and timestamps, so a downstream process model
  can trust and reuse the record without re-deriving assumptions.

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | liveness check |
| GET/POST | `/api/sites` | list / register manufacturing sites |
| GET/POST | `/api/documentation` | list (filterable by `site_id`, `status`, `doc_type`) / create tech-transfer documentation records |
| GET | `/api/documentation/<record_id>` | fetch one record |
| PATCH | `/api/documentation/<record_id>` | update status (auto-bumps `version` on a real status change) |
| GET/POST | `/api/parameters` | list (filterable by `site_id`, `batch_id`, `parameter_type`) / log a process-parameter reading, with real-time unit standardization + spec-range checking |
| GET | `/api/summary` | dashboard rollups (counts by status/site, out-of-spec rate by site) |

## How to run

```bash
cd TechTransfer-Digitization-Workflows
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cd backend
python seed_data.py            # generates techtransfer.db with simulated multi-site data
python app.py                  # starts the API on http://127.0.0.1:5055

# in another terminal, serve the frontend:
cd ../frontend
python3 -m http.server 8090
# open http://127.0.0.1:8090 in a browser -- it fetches live data from the API above

# Power BI extract:
cd ../backend
python export_powerbi_extract.py   # writes ../data/powerbi_extract.csv

# tests:
cd ..
PYTHONPATH=backend pytest -q tests/
```

## Results

_Numbers below are copied directly from real `curl` calls against the
running API after `python seed_data.py` (seed 42), and from a real
`pytest -q` run. Nothing here is hand-typed or hardcoded._

- **4 simulated manufacturing/R&D sites** (`SITE-01` Cambridge process-dev
  lab through `SITE-04` Singapore GMP site).
- **47 documentation records** created across sites (8-14 per site),
  spanning 7 document types (Batch Record, SOP, Process Validation Report,
  Analytical Method Transfer, Equipment Qualification, Change Control, Risk
  Assessment) and 5 lifecycle statuses -- **13 Approved, 11 Draft, 14 In
  Review, 3 Transferred, 6 Superseded**.
- **190 process-parameter readings** across 10 parameter types (temperature,
  pressure, pH, pressure differential, conductivity, flow rate, mixing
  speed, mass, volume, hold time) and 3-5 batches per site, each recorded in
  a randomly chosen real-world unit (e.g. °F, psi, mL/min, lb) and
  standardized server-side to one canonical unit per type.
- **Out-of-spec rate by site:** SITE-01 24.0% (12/50), SITE-02 26.0%
  (13/50), SITE-03 22.5% (9/40), SITE-04 32.0% (16/50) -- computed by the
  real `/api/summary` endpoint comparing each standardized value against its
  submitted spec range.
- **`data/powerbi_extract.csv`: 237 data rows** (47 documentation + 190
  parameter rows) in one denormalized, Power-BI-importable schema.
- **Frontend <-> backend integration verified live:** `curl -i -H "Origin:
  http://127.0.0.1:8090" http://127.0.0.1:5055/api/summary` returned
  `HTTP/1.1 200 OK` with `Access-Control-Allow-Origin:
  http://127.0.0.1:8090` and the real summary JSON, confirming the static
  frontend's cross-origin `fetch()` calls succeed against the live backend.
- **Tests: `PYTHONPATH=backend pytest -q tests/` -> 18 passed** -- 8 unit
  tests on the standardization/validation logic (unit conversion, invalid
  unit/type/site-id rejection, findable-ID format) and 10 tests on the live
  API (site/documentation/parameter CRUD, status-version bumping, spec
  in/out-of-range flagging, filtering, summary rollups).

## What the Power BI dashboard would show

Not built here (see honesty section) -- if opened in real Power BI against
`data/powerbi_extract.csv`, this is the report that extract is designed for:

1. **Documentation Status Overview** (stacked bar) -- count of documentation
   records per `site_id`, stacked by `status_or_spec` (Draft/In
   Review/Approved/Transferred/Superseded), with a slicer on `category`
   (doc type) -- the Power BI equivalent of the dashboard's "Documentation"
   tab.
2. **Tech-Transfer Progress Funnel** -- a funnel visual over the five
   documentation statuses in their natural lifecycle order, filterable by
   site, showing where records are bottlenecked (e.g. stuck In Review).
3. **Process Parameter Control Chart** (line + reference band) -- for a
   parameter selected via slicer, `standardized_value` over `timestamp`,
   with `status_or_spec`'s `[low, high]` range rendered as a shaded
   reference band, and out-of-spec points highlighted -- built directly from
   the `record_type = "process_parameter"` rows.
4. **Out-of-Spec Rate by Site** (KPI matrix) -- `site_id` x `category`
   matrix of % `in_spec = FALSE`, conditional-formatted red/green, using a
   DAX measure `DIVIDE(COUNTROWS(FILTER(..., in_spec = FALSE)), COUNTROWS(...))`.
   This is the direct analog of the vanilla-JS "Process Parameters
   Out-of-Spec Rate by Site" bar chart already rendered live in
   `frontend/index.html`.
5. **Cross-filter action** -- clicking a site in visual (1) filters visuals
   (2)-(4) to that site, giving a single-page drill-down dashboard per
   manufacturing site, consistent with the resume bullet's "standardizing
   data capture across manufacturing sites."

## Tech stack

- Python 3 / Flask / Flask-CORS -- REST API
- SQLite (via Python's stdlib `sqlite3`) -- persistence
- pytest -- 18 passing tests (unit + API)
- Vanilla HTML/CSS/JavaScript (`fetch`) -- the dashboard frontend, in place
  of React (see honesty section for exactly why)
- Power BI (named in the source resume bullet; **not available/executed in
  this environment** -- CSV extract + written description provided instead)
