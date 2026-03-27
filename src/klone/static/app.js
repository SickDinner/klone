const state = {
  blueprint: null,
  status: null,
  rooms: [],
  guards: [],
  datasets: [],
  audit: [],
  ingestStatus: null,
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = `Request failed: ${response.status}`;
    try {
      const payload = await response.json();
      message = payload.detail || message;
    } catch (error) {
      console.error(error);
    }
    throw new Error(message);
  }
  return response.json();
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
}

function formatTime(value) {
  if (!value) {
    return "Not yet";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function shortHash(value) {
  if (!value) {
    return "n/a";
  }
  return `${value.slice(0, 8)}...${value.slice(-8)}`;
}

function chips(items = []) {
  return items
    .filter(Boolean)
    .map((item) => `<span class="chip">${escapeHtml(item)}</span>`)
    .join("");
}

function renderStatusCards(status) {
  const latestSummary = status.latest_ingest?.summary || "No ingest runs recorded yet.";
  document.querySelector("#status-cards").innerHTML = `
    <article class="panel stat-card">
      <h3>System</h3>
      <p>${escapeHtml(status.app_name)} in ${escapeHtml(status.environment)}</p>
      <div class="meta">${chips([`owner_debug_mode: ${status.owner_debug_mode}`, `guards: ${status.guard_count}`])}</div>
    </article>
    <article class="panel stat-card">
      <h3>Datasets</h3>
      <p>${status.dataset_count} governed datasets across ${status.room_count} readable rooms.</p>
      <div class="meta">${chips([`assets: ${status.indexed_asset_count}`, `duplicates: ${status.duplicate_asset_count}`])}</div>
    </article>
    <article class="panel stat-card">
      <h3>Audit Trail</h3>
      <p>${status.audit_event_count} audit events recorded in the indexed mission-control state.</p>
      <div class="meta">${chips([`modules: ${status.module_count}`, `agents: ${status.agent_count}`])}</div>
    </article>
    <article class="panel stat-card">
      <h3>Latest Ingest</h3>
      <p>${escapeHtml(latestSummary)}</p>
      <div class="meta">${chips([
        `status: ${status.latest_ingest?.status || "pending"}`,
        `started: ${formatTime(status.latest_ingest?.started_at)}`,
      ])}</div>
    </article>
  `;
}

function renderDatasets(datasets) {
  const root = document.querySelector("#dataset-list");
  if (!datasets.length) {
    root.innerHTML = '<div class="empty-state">No datasets indexed yet.</div>';
    return;
  }
  root.innerHTML = datasets
    .map(
      (dataset) => `
        <article class="stack-item">
          <small>${escapeHtml(dataset.room_id)}</small>
          <h3>${escapeHtml(dataset.label)}</h3>
          <p>${escapeHtml(dataset.description || dataset.root_path)}</p>
          <div class="meta">${chips([
            `classification_level: ${dataset.classification_level}`,
            `scan_state: ${dataset.scan_state || "pending"}`,
            `last_scan_at: ${formatTime(dataset.last_scan_at)}`,
            `asset_count: ${dataset.asset_count}`,
            `duplicates: ${dataset.duplicate_count}`,
          ])}</div>
        </article>
      `,
    )
    .join("");
}

function renderRooms(rooms) {
  const root = document.querySelector("#room-list");
  root.innerHTML = rooms
    .map(
      (room) => `
        <article class="stack-item">
          <small>${escapeHtml(room.room_type)}</small>
          <h3>${escapeHtml(room.label)}</h3>
          <p>${escapeHtml(room.supervisor)} supervises this ${escapeHtml(room.classification)} room.</p>
          <div class="meta">${chips([
            `status: ${room.status}`,
            `retention: ${room.retention_policy}`,
            `roles: ${room.allowed_roles.join(", ")}`,
          ])}</div>
        </article>
      `,
    )
    .join("");
}

function renderGuards(guards) {
  const root = document.querySelector("#guard-list");
  root.innerHTML = guards
    .map(
      (guard) => `
        <article class="stack-item">
          <small>${guard.active ? "active" : "inactive"}</small>
          <h3>${escapeHtml(guard.name)}</h3>
          <p>${escapeHtml(guard.description)}</p>
        </article>
      `,
    )
    .join("");
}

function renderAudit(events) {
  const root = document.querySelector("#audit-list");
  if (!events.length) {
    root.innerHTML = '<div class="empty-state">No audit events recorded yet.</div>';
    return;
  }
  root.innerHTML = events
    .map(
      (event) => `
        <article class="stack-item">
          <small>${escapeHtml(event.event_type)}</small>
          <h3>${escapeHtml(event.summary)}</h3>
          <p>${escapeHtml(event.actor)} -> ${escapeHtml(event.target_type)} (${escapeHtml(event.room_id || "no-room")})</p>
          <div class="meta">${chips([
            `classification_level: ${event.classification_level}`,
            `created_at: ${formatTime(event.created_at)}`,
          ])}</div>
        </article>
      `,
    )
    .join("");
}

function renderModules(modules) {
  const root = document.querySelector("#modules");
  root.innerHTML = modules
    .map(
      (module) => `
        <article class="card">
          <div class="tag">${escapeHtml(module.supervisor)}</div>
          <h3>${escapeHtml(module.name)}</h3>
          <p>${escapeHtml(module.purpose)}</p>
          <div class="meta">${chips([
            `zone_id: ${module.zone_id}`,
            `stage: ${module.stage}`,
            `status: ${module.status}`,
          ])}</div>
        </article>
      `,
    )
    .join("");
}

function renderAgents(agents) {
  document.querySelector("#agents").innerHTML = agents
    .map(
      (agent) => `
        <article class="stack-item">
          <small>${escapeHtml(agent.layer)}</small>
          <h3>${escapeHtml(agent.name)}</h3>
          <p>${escapeHtml(agent.responsibility)}</p>
          <div class="meta">${chips(agent.watches)}</div>
        </article>
      `,
    )
    .join("");
}

function renderPhases(phases) {
  document.querySelector("#phases").innerHTML = phases
    .map(
      (phase) => `
        <article class="stack-item">
          <small>${escapeHtml(phase.id)}</small>
          <h3>${escapeHtml(phase.title)}</h3>
          <p>${escapeHtml(phase.goal)}</p>
          <div class="meta">${chips(phase.deliverables)}</div>
        </article>
      `,
    )
    .join("");
}

function renderIngestRuns(ingestStatus) {
  const root = document.querySelector("#ingest-runs");
  if (!ingestStatus?.recent_runs?.length) {
    root.innerHTML = '<div class="empty-state">No ingest runs available.</div>';
    return;
  }
  root.innerHTML = ingestStatus.recent_runs
    .map(
      (run) => `
        <article class="stack-item">
          <small>${escapeHtml(run.room_id)}</small>
          <h3>${escapeHtml(run.dataset_label)}</h3>
          <p>${escapeHtml(run.summary || "No summary available.")}</p>
          <div class="meta">${chips([
            `status: ${run.status}`,
            `files: ${run.files_discovered}`,
            `indexed: ${run.assets_indexed}`,
            `duplicates: ${run.duplicates_detected}`,
          ])}</div>
        </article>
      `,
    )
    .join("");
}

function renderAssets(assets) {
  const root = document.querySelector("#asset-table");
  if (!assets.length) {
    root.innerHTML = '<tr><td colspan="7" class="empty-cell">No assets in the current room scope.</td></tr>';
    return;
  }
  root.innerHTML = assets
    .map(
      (asset) => `
        <tr>
          <td>
            <div class="table-title">${escapeHtml(asset.file_name)}</div>
            <div class="table-subtitle">${escapeHtml(shortHash(asset.sha256))}</div>
          </td>
          <td>${escapeHtml(asset.dataset_label)}</td>
          <td>${escapeHtml(asset.asset_kind)}</td>
          <td>${escapeHtml(asset.classification_level)}</td>
          <td>${escapeHtml(asset.extraction_status)}</td>
          <td>${escapeHtml(formatTime(asset.indexed_at))}</td>
          <td><button class="link-button" data-asset-id="${asset.id}" type="button">Inspect</button></td>
        </tr>
      `,
    )
    .join("");
}

function renderAssetDetail(asset) {
  const metadata = asset.metadata
    ? Object.entries(asset.metadata)
        .map(([key, value]) => `<li><strong>${escapeHtml(key)}</strong>: ${escapeHtml(JSON.stringify(value))}</li>`)
        .join("")
    : "<li>No metadata recorded.</li>";
  document.querySelector("#asset-detail").innerHTML = `
    <h3>${escapeHtml(asset.file_name)}</h3>
    <p>${escapeHtml(asset.path)}</p>
    <div class="meta">${chips([
      `room_id: ${asset.room_id}`,
      `classification_level: ${asset.classification_level}`,
      `asset_kind: ${asset.asset_kind}`,
      `extraction_status: ${asset.extraction_status}`,
      `dedup_status: ${asset.dedup_status}`,
      `size_bytes: ${formatBytes(asset.size_bytes)}`,
    ])}</div>
    <ul class="detail-list">
      <li><strong>dataset</strong>: ${escapeHtml(asset.dataset_label)}</li>
      <li><strong>mime_type</strong>: ${escapeHtml(asset.mime_type || "unknown")}</li>
      <li><strong>sha256</strong>: ${escapeHtml(asset.sha256)}</li>
      <li><strong>fs_created_at</strong>: ${escapeHtml(formatTime(asset.fs_created_at))}</li>
      <li><strong>fs_modified_at</strong>: ${escapeHtml(formatTime(asset.fs_modified_at))}</li>
      <li><strong>first_seen_at</strong>: ${escapeHtml(formatTime(asset.first_seen_at))}</li>
      <li><strong>last_seen_at</strong>: ${escapeHtml(formatTime(asset.last_seen_at))}</li>
      ${metadata}
    </ul>
  `;
}

function renderMission(blueprint) {
  document.querySelector("#mission").textContent = blueprint.mission;
  document.querySelector("#hypervisor-answer").textContent = blueprint.hypervisor_answer;
}

function populateRoomFilter(rooms) {
  const select = document.querySelector("#asset-room-filter");
  const current = select.value;
  select.innerHTML = [
    '<option value="">All readable rooms</option>',
    ...rooms.map((room) => `<option value="${escapeHtml(room.id)}">${escapeHtml(room.label)}</option>`),
  ].join("");
  select.value = rooms.some((room) => room.id === current) ? current : "";
}

function populateDatasetFilter(datasets) {
  const select = document.querySelector("#asset-dataset-filter");
  const current = select.value;
  select.innerHTML = [
    '<option value="">All datasets</option>',
    ...datasets.map((dataset) => `<option value="${dataset.id}">${escapeHtml(dataset.label)}</option>`),
  ].join("");
  select.value = datasets.some((dataset) => String(dataset.id) === current) ? current : "";
}

async function refreshAssetBrowser() {
  const roomId = document.querySelector("#asset-room-filter").value;
  const datasetId = document.querySelector("#asset-dataset-filter").value;
  const params = new URLSearchParams();
  if (roomId) {
    params.set("room_id", roomId);
  }
  if (datasetId) {
    params.set("dataset_id", datasetId);
  }
  const assets = await fetchJson(`/api/assets?${params.toString()}`);
  renderAssets(assets);
}

async function loadAssetDetail(assetId) {
  try {
    const asset = await fetchJson(`/api/assets/${assetId}`);
    renderAssetDetail(asset);
  } catch (error) {
    document.querySelector("#asset-detail").textContent = error.message;
  }
}

async function refreshMissionControl() {
  const [blueprint, status, rooms, guards, datasets, audit, ingestStatus] = await Promise.all([
    fetchJson("/api/blueprint"),
    fetchJson("/api/status"),
    fetchJson("/api/rooms"),
    fetchJson("/api/governance/guards"),
    fetchJson("/api/datasets"),
    fetchJson("/api/audit"),
    fetchJson("/api/ingest/status"),
  ]);

  state.blueprint = blueprint;
  state.status = status;
  state.rooms = rooms;
  state.guards = guards;
  state.datasets = datasets;
  state.audit = audit;
  state.ingestStatus = ingestStatus;

  renderMission(blueprint);
  renderStatusCards(status);
  renderDatasets(datasets);
  renderRooms(rooms);
  renderGuards(guards);
  renderAudit(audit);
  renderModules(blueprint.modules);
  renderAgents(blueprint.agents);
  renderPhases(blueprint.build_phases);
  renderIngestRuns(ingestStatus);
  populateRoomFilter(rooms);
  populateDatasetFilter(datasets);
  await refreshAssetBrowser();
}

async function submitIngestForm(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const submitButton = form.querySelector("button[type='submit']");
  const feedback = document.querySelector("#ingest-feedback");
  const payload = Object.fromEntries(new FormData(form).entries());

  submitButton.disabled = true;
  feedback.textContent = "Scanning dataset...";

  try {
    const result = await fetchJson("/api/ingest/scan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    feedback.textContent = `Ingest ${result.run.status}: ${result.run.summary}`;
    await refreshMissionControl();
  } catch (error) {
    feedback.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

function bindEvents() {
  document.querySelector("#ingest-form").addEventListener("submit", submitIngestForm);
  document.querySelector("#asset-refresh").addEventListener("click", refreshAssetBrowser);
  document.querySelector("#asset-room-filter").addEventListener("change", refreshAssetBrowser);
  document.querySelector("#asset-dataset-filter").addEventListener("change", refreshAssetBrowser);
  document.querySelector("#asset-table").addEventListener("click", (event) => {
    const button = event.target.closest("[data-asset-id]");
    if (!button) {
      return;
    }
    loadAssetDetail(button.dataset.assetId);
  });
}

async function main() {
  bindEvents();
  try {
    await refreshMissionControl();
  } catch (error) {
    document.querySelector("#mission").textContent = error.message;
    console.error(error);
  }
}

main();
