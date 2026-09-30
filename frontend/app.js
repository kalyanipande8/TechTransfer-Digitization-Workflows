/*
 * Tech-Transfer Digitization Dashboard -- vanilla JS single-page app.
 *
 * This is a REAL, runnable static frontend (no framework, no build step)
 * that fetches from the real Flask API (see backend/app.py) and renders
 * live data. It is structured the way an equivalent React app would be:
 *   - `state` = the single source of truth (like React state)
 *   - `render()` functions = pure(ish) functions that turn state into DOM
 *     (like React components / JSX)
 *   - event listeners call API functions, mutate `state`, then call the
 *     relevant render function -- the same one-way data flow React encourages.
 * See README.md for why this is vanilla JS instead of React in this
 * environment (disk space, not Node availability).
 */

const API_BASE = "http://127.0.0.1:5055/api";

const UNIT_OPTIONS = {
  temperature: ["C", "F", "K"],
  pressure: ["bar", "psi", "kPa", "atm"],
  ph: ["pH"],
  pressure_diff: ["mbar"],
  conductivity: ["mS/cm"],
  flow_rate: ["L/min", "mL/min", "gal/min"],
  mixing_speed: ["rpm"],
  mass: ["kg", "g", "lb"],
  volume: ["L", "mL", "gal"],
  time: ["min", "s", "h"],
};

const state = {
  sites: [],
  documentation: [],
  parameters: [],
  summary: null,
};

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `POST ${path} failed`);
  return data;
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

document.getElementById("tabs").addEventListener("click", (e) => {
  const btn = e.target.closest(".tab");
  if (!btn) return;
  document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
  document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
  btn.classList.add("active");
  document.getElementById(btn.dataset.tab).classList.add("active");
});

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function renderStatus(ok) {
  const el = document.getElementById("apiStatus");
  el.textContent = ok ? "API connected (http://127.0.0.1:5055)" : "API unreachable -- start backend/app.py";
  el.className = "api-status " + (ok ? "ok" : "down");
}

function renderOverview() {
  const s = state.summary;
  if (!s) return;
  document.getElementById("statRow").innerHTML = `
    <div class="stat-tile"><div class="value">${s.total_sites}</div><div class="label">Manufacturing / R&D Sites</div></div>
    <div class="stat-tile"><div class="value">${s.total_documentation_records}</div><div class="label">Documentation Records</div></div>
    <div class="stat-tile"><div class="value">${s.total_process_parameter_records}</div><div class="label">Process Parameter Readings</div></div>
  `;

  const bySite = {};
  s.documentation_by_site.forEach((r) => (bySite[r.site_id] = r.n));
  const maxDoc = Math.max(1, ...Object.values(bySite));
  document.getElementById("docStatusChart").innerHTML = Object.entries(bySite)
    .map(
      ([site, n]) => `
      <div class="bar-row">
        <div class="bar-label">${site}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${(n / maxDoc) * 100}%"></div></div>
        <div class="bar-value">${n}</div>
      </div>`
    )
    .join("");

  document.getElementById("specChart").innerHTML = s.parameter_out_of_spec_by_site
    .map((r) => {
      const rate = r.total ? (r.out_of_spec / r.total) * 100 : 0;
      return `
      <div class="bar-row">
        <div class="bar-label">${r.site_id}</div>
        <div class="bar-track"><div class="bar-fill bad" style="width:${rate}%"></div></div>
        <div class="bar-value">${rate.toFixed(1)}%</div>
      </div>`;
    })
    .join("");
}

function renderSiteSelects() {
  const options = state.sites.map((s) => `<option value="${s.site_id}">${s.site_id} -- ${s.name}</option>`).join("");
  document.querySelectorAll('select[name="site_id"], #docSiteFilter, #paramSiteFilter').forEach((sel) => {
    const keepFirst = sel.id === "docSiteFilter" || sel.id === "paramSiteFilter";
    sel.innerHTML = (keepFirst ? '<option value="">All</option>' : "") + options;
  });
  const statuses = ["Draft", "In Review", "Approved", "Transferred", "Superseded"];
  document.getElementById("docStatusFilter").innerHTML =
    '<option value="">All</option>' + statuses.map((s) => `<option>${s}</option>`).join("");
}

function renderDocTable() {
  const siteFilter = document.getElementById("docSiteFilter").value;
  const statusFilter = document.getElementById("docStatusFilter").value;
  const rows = state.documentation.filter(
    (r) => (!siteFilter || r.site_id === siteFilter) && (!statusFilter || r.status === statusFilter)
  );
  document.querySelector("#docTable tbody").innerHTML = rows
    .map(
      (r) => `
    <tr>
      <td><code>${r.record_id}</code></td>
      <td>${r.site_id}</td>
      <td>${r.doc_type}</td>
      <td>${r.title}</td>
      <td><span class="status-pill">${r.status}</span></td>
      <td>v${r.version}</td>
      <td>${r.owner}</td>
      <td>${r.updated_at}</td>
    </tr>`
    )
    .join("");
}

function renderParamTable() {
  const siteFilter = document.getElementById("paramSiteFilter").value;
  const rows = state.parameters.filter((r) => !siteFilter || r.site_id === siteFilter);
  document.querySelector("#paramTable tbody").innerHTML = rows
    .map(
      (r) => `
    <tr>
      <td><code>${r.parameter_record_id}</code></td>
      <td>${r.site_id}</td>
      <td>${r.batch_id}</td>
      <td>${r.parameter_name}</td>
      <td>${r.recorded_value} ${r.recorded_unit}</td>
      <td>${r.standardized_value} ${r.standardized_unit}</td>
      <td class="${r.in_spec ? "in-spec-yes" : "in-spec-no"}">${r.in_spec ? "Yes" : "NO"}</td>
      <td>${r.recorded_at}</td>
    </tr>`
    )
    .join("");
}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

async function loadAll() {
  try {
    const [sites, documentation, parameters, summary] = await Promise.all([
      apiGet("/sites"),
      apiGet("/documentation"),
      apiGet("/parameters"),
      apiGet("/summary"),
    ]);
    state.sites = sites;
    state.documentation = documentation;
    state.parameters = parameters;
    state.summary = summary;
    renderStatus(true);
    renderSiteSelects();
    renderOverview();
    renderDocTable();
    renderParamTable();
  } catch (err) {
    console.error(err);
    renderStatus(false);
  }
}

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------

document.getElementById("docSiteFilter").addEventListener("change", renderDocTable);
document.getElementById("docStatusFilter").addEventListener("change", renderDocTable);
document.getElementById("paramSiteFilter").addEventListener("change", renderParamTable);

// ---------------------------------------------------------------------------
// Forms
// ---------------------------------------------------------------------------

document.getElementById("paramTypeSelect").addEventListener("change", populateUnitOptions);
function populateUnitOptions() {
  const type = document.getElementById("paramTypeSelect").value;
  document.getElementById("unitSelect").innerHTML = (UNIT_OPTIONS[type] || [])
    .map((u) => `<option>${u}</option>`)
    .join("");
}

document.getElementById("docForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const payload = Object.fromEntries(new FormData(form).entries());
  const resultEl = document.getElementById("docFormResult");
  try {
    const res = await apiPost("/documentation", payload);
    resultEl.textContent = `Created ${res.record_id}`;
    form.reset();
    await loadAll();
  } catch (err) {
    resultEl.textContent = `Error: ${err.message}`;
  }
});

document.getElementById("paramForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const payload = Object.fromEntries(new FormData(form).entries());
  const resultEl = document.getElementById("paramFormResult");
  try {
    const res = await apiPost("/parameters", payload);
    resultEl.textContent = `Created ${res.parameter_record_id} -> standardized: ${res.standardized_value} ${res.standardized_unit} (in spec: ${res.in_spec})`;
    form.reset();
    populateUnitOptions();
    await loadAll();
  } catch (err) {
    resultEl.textContent = `Error: ${err.message}`;
  }
});

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

populateUnitOptions();
loadAll();
setInterval(loadAll, 15000);
