const state = {
  blueprint: null,
  status: null,
  rooms: [],
  guards: [],
  datasets: [],
  audit: [],
  ingestStatus: null,
  ingestQueue: [],
  ingestQueueSelectionId: null,
  ingestPreview: null,
  ingestManifest: null,
  memory: {
    roomId: "",
    events: [],
    episodes: [],
    selection: null,
    detail: null,
    provenanceDetail: null,
    contextPayload: null,
    answer: null,
  },
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
      <div class="meta">${chips([`owner_debug_mode: ${status.owner_debug_mode}`, `guards: ${status.guard_count}`, `queue_depth: ${state.ingestStatus?.queue_depth ?? 0}`])}</div>
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

function renderIngestPreview(preflight) {
  const root = document.querySelector("#ingest-preview");
  if (!preflight) {
    root.className = "detail-card empty-state";
    root.textContent = "Run a preflight preview to inspect the manifest before indexing.";
    return;
  }

  const warningMarkup = preflight.warnings?.length
    ? `<ul class="manifest-list warning-list">${preflight.warnings
        .map((warning) => `<li>${escapeHtml(warning)}</li>`)
        .join("")}</ul>`
    : '<div class="empty-state">No preview warnings.</div>';

  const breakdownMarkup = preflight.asset_kind_breakdown?.length
    ? `<ul class="manifest-list">${preflight.asset_kind_breakdown
        .map(
          (item) =>
            `<li><strong>${escapeHtml(item.asset_kind)}</strong>: ${item.count} files, ${formatBytes(item.total_size_bytes)}</li>`,
        )
        .join("")}</ul>`
    : '<div class="empty-state">No files discovered in this preview.</div>';

  const sampleMarkup = preflight.sample_assets?.length
    ? `<ul class="manifest-list">${preflight.sample_assets
        .map((item) => {
          const canonical =
            item.canonical_dataset_label && item.canonical_relative_path
              ? `duplicate of ${item.canonical_dataset_label}/${item.canonical_relative_path}`
              : item.dedup_status === "duplicate"
                ? `duplicate of asset ${item.canonical_asset_id}`
                : "unique";
          return `<li><strong>${escapeHtml(item.relative_path)}</strong>: ${escapeHtml(item.planned_action)}, ${escapeHtml(item.asset_kind)}, ${formatBytes(item.size_bytes)} (${escapeHtml(canonical)})</li>`;
        })
        .join("")}</ul>`
    : '<div class="empty-state">No sample assets available.</div>';

  root.className = "detail-card";
  root.innerHTML = `
    <h3>Preflight Manifest</h3>
    <p>${escapeHtml(preflight.request.label)} resolves to ${escapeHtml(preflight.room_label)} without writing a dataset or asset row.</p>
    <div class="meta">${chips([
      `room: ${preflight.room_id}`,
      `can_start_ingest: ${preflight.can_start_ingest}`,
      `files: ${preflight.files_discovered}`,
      `size: ${formatBytes(preflight.total_size_bytes)}`,
      `new: ${preflight.planned_new_assets}`,
      `updated: ${preflight.planned_updated_assets}`,
      `unchanged: ${preflight.planned_unchanged_assets}`,
      `duplicates: ${preflight.duplicates_detected}`,
      `existing_dataset: ${preflight.existing_dataset_slug || "new_dataset"}`,
      `access: ${preflight.access_guard.decision}`,
    ])}</div>
    <ul class="detail-list">
      <li><strong>normalized_root_path</strong>: ${escapeHtml(preflight.normalized_root_path)}</li>
      <li><strong>classification_guard</strong>: ${escapeHtml(preflight.classification_guard.reason)}</li>
      <li><strong>access_guard</strong>: ${escapeHtml(preflight.access_guard.reason)}</li>
    </ul>
    <div class="preview-grid">
      <section class="preview-block">
        <h4>Kind Breakdown</h4>
        ${breakdownMarkup}
      </section>
      <section class="preview-block">
        <h4>Sample Assets</h4>
        ${sampleMarkup}
      </section>
    </div>
    <section class="preview-block warning-list">
      <h4>Warnings</h4>
      ${warningMarkup}
    </section>
  `;
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
            `manifest: ${run.has_manifest ? "available" : "missing"}`,
          ])}</div>
          <div class="meta">
            <button class="link-button" data-ingest-run-id="${run.id}" type="button" ${run.has_manifest ? "" : "disabled"}>Inspect Manifest</button>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderIngestQueueJobs(queueJobs) {
  const root = document.querySelector("#ingest-queue-jobs");
  if (!queueJobs?.length) {
    root.innerHTML = '<div class="empty-state">No queued ingest jobs available.</div>';
    return;
  }
  root.innerHTML = queueJobs
    .map((job) => {
      const selected = String(state.ingestQueueSelectionId || "") === String(job.id);
      return `
        <article class="stack-item ${selected ? "memory-selected" : ""}">
          <small>${escapeHtml(job.room_id)}</small>
          <h3>${escapeHtml(job.label)}</h3>
          <p>${escapeHtml(job.description || job.normalized_root_path)}</p>
          <div class="meta">${chips([
            `status: ${job.status}`,
            `collection: ${job.collection}`,
            `attempts: ${job.attempt_count}`,
            `last_run_id: ${job.last_run_id || "none"}`,
          ])}</div>
          <div class="meta">
            <button class="link-button" data-queue-action="inspect" data-queue-job-id="${job.id}" type="button">Inspect</button>
            <button class="link-button" data-queue-action="execute" data-queue-job-id="${job.id}" type="button" ${job.can_execute ? "" : "disabled"}>Execute</button>
            <button class="link-button" data-queue-action="cancel" data-queue-job-id="${job.id}" type="button" ${job.can_cancel ? "" : "disabled"}>Cancel</button>
            <button class="link-button" data-queue-action="manifest" data-queue-job-id="${job.id}" type="button" ${job.last_run_id ? "" : "disabled"}>Inspect Run Manifest</button>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderIngestQueueDetail(job) {
  const root = document.querySelector("#ingest-queue-detail");
  if (!job) {
    root.className = "detail-card empty-state";
    root.textContent = "Select a queued ingest job.";
    return;
  }

  root.className = "detail-card";
  root.innerHTML = `
    <h3>Queue Job ${job.id}</h3>
    <p>${escapeHtml(job.label)} in ${escapeHtml(job.room_id)} persists the ingest request for manual execution and retry.</p>
    <div class="meta">${chips([
      `status: ${job.status}`,
      `classification: ${job.classification_level}`,
      `collection: ${job.collection}`,
      `attempt_count: ${job.attempt_count}`,
      `last_run_id: ${job.last_run_id || "none"}`,
    ])}</div>
    <ul class="detail-list">
      <li><strong>normalized_root_path</strong>: ${escapeHtml(job.normalized_root_path)}</li>
      <li><strong>created_at</strong>: ${escapeHtml(formatTime(job.created_at))}</li>
      <li><strong>updated_at</strong>: ${escapeHtml(formatTime(job.updated_at))}</li>
      <li><strong>started_at</strong>: ${escapeHtml(formatTime(job.started_at))}</li>
      <li><strong>completed_at</strong>: ${escapeHtml(formatTime(job.completed_at))}</li>
      <li><strong>last_error</strong>: ${escapeHtml(job.last_error || "none")}</li>
    </ul>
  `;
}

function renderIngestRunManifest(manifest) {
  const root = document.querySelector("#ingest-run-detail");
  if (!manifest) {
    root.className = "detail-card empty-state";
    root.textContent = "Select an ingest run manifest.";
    return;
  }

  const breakdownMarkup = manifest.asset_kind_breakdown?.length
    ? `<ul class="manifest-list">${manifest.asset_kind_breakdown
        .map(
          (item) =>
            `<li><strong>${escapeHtml(item.asset_kind)}</strong>: ${item.count} files, ${formatBytes(item.total_size_bytes)}</li>`,
        )
        .join("")}</ul>`
    : '<div class="empty-state">No asset-kind breakdown stored.</div>';

  const sampleMarkup = manifest.sample_assets?.length
    ? `<ul class="manifest-list">${manifest.sample_assets
        .map((item) => {
          const canonical =
            item.canonical_dataset_label && item.canonical_relative_path
              ? `duplicate of ${item.canonical_dataset_label}/${item.canonical_relative_path}`
              : item.dedup_status === "duplicate"
                ? `duplicate of asset ${item.canonical_asset_id}`
                : "unique";
          return `<li><strong>${escapeHtml(item.relative_path)}</strong>: ${escapeHtml(item.planned_action)}, ${escapeHtml(item.asset_kind)}, ${formatBytes(item.size_bytes)} (${escapeHtml(canonical)})</li>`;
        })
        .join("")}</ul>`
    : '<div class="empty-state">No sample assets stored for this run.</div>';

  const warningMarkup = manifest.warnings?.length
    ? `<ul class="manifest-list">${manifest.warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}</ul>`
    : '<div class="empty-state">No manifest warnings stored.</div>';

  root.className = "detail-card";
  root.innerHTML = `
    <h3>Run ${manifest.run.id} Manifest</h3>
    <p>${escapeHtml(manifest.run.dataset_label)} in ${escapeHtml(manifest.run.room_id)} captured a bounded snapshot of what this ingest run processed.</p>
    <div class="meta">${chips([
      `status: ${manifest.run.status}`,
      `classification: ${manifest.run.classification_level || "unknown"}`,
      `collection: ${manifest.run.collection || "unknown"}`,
      `files: ${manifest.run.files_discovered}`,
      `indexed: ${manifest.run.assets_indexed}`,
      `new: ${manifest.run.new_assets}`,
      `updated: ${manifest.run.updated_assets}`,
      `unchanged: ${manifest.run.unchanged_assets}`,
      `duplicates: ${manifest.run.duplicates_detected}`,
      `size: ${formatBytes(manifest.total_size_bytes)}`,
    ])}</div>
    <ul class="detail-list">
      <li><strong>normalized_root_path</strong>: ${escapeHtml(manifest.normalized_root_path)}</li>
      <li><strong>started_at</strong>: ${escapeHtml(formatTime(manifest.run.started_at))}</li>
      <li><strong>completed_at</strong>: ${escapeHtml(formatTime(manifest.run.completed_at))}</li>
    </ul>
    <div class="preview-grid">
      <section class="preview-block">
        <h4>Kind Breakdown</h4>
        ${breakdownMarkup}
      </section>
      <section class="preview-block">
        <h4>Sample Assets</h4>
        ${sampleMarkup}
      </section>
    </div>
    <section class="preview-block warning-list">
      <h4>Warnings</h4>
      ${warningMarkup}
    </section>
  `;
}

function syncIngestQueueSelection() {
  if (!state.ingestQueue?.length) {
    state.ingestQueueSelectionId = null;
    renderIngestQueueDetail(null);
    return;
  }

  const selected =
    state.ingestQueue.find((job) => String(job.id) === String(state.ingestQueueSelectionId || "")) ||
    state.ingestQueue[0];
  state.ingestQueueSelectionId = selected.id;
  renderIngestQueueDetail(selected);
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

function populateMemoryRoomFilter(rooms) {
  const select = document.querySelector("#memory-room-filter");
  const current = state.memory.roomId || select.value;
  const fallbackRoomId = rooms.find((room) => room.id === "restricted-room")?.id || rooms[0]?.id || "";
  select.innerHTML = rooms
    .map((room) => `<option value="${escapeHtml(room.id)}">${escapeHtml(room.label)}</option>`)
    .join("");
  select.value = rooms.some((room) => room.id === current) ? current : fallbackRoomId;
  state.memory.roomId = select.value;
}

function renderMemoryEvents(events) {
  const root = document.querySelector("#memory-events");
  if (!events.length) {
    root.innerHTML = '<div class="empty-state">No memory events match the current filters.</div>';
    return;
  }
  root.innerHTML = events
    .map((event) => {
      const selected =
        state.memory.selection?.kind === "event" &&
        String(state.memory.selection.id) === String(event.id);
      return `
        <article class="stack-item ${selected ? "memory-selected" : ""}">
          <small>${escapeHtml(event.event_type)}</small>
          <h3>${escapeHtml(event.title)}</h3>
          <p>${escapeHtml(event.evidence_text)}</p>
          <div class="meta">${chips([
            `status: ${event.status}`,
            `occurred_at: ${formatTime(event.occurred_at)}`,
            `provenance_refs: ${event.provenance_summary?.source_refs?.length || 0}`,
          ])}</div>
          <button class="link-button memory-link" data-memory-kind="event" data-memory-id="${event.id}" type="button">
            Inspect event
          </button>
        </article>
      `;
    })
    .join("");
}

function renderMemoryEpisodes(episodes) {
  const root = document.querySelector("#memory-episodes");
  if (!episodes.length) {
    root.innerHTML = '<div class="empty-state">No memory episodes match the current filters.</div>';
    return;
  }
  root.innerHTML = episodes
    .map((episode) => {
      const selected =
        state.memory.selection?.kind === "episode" &&
        String(state.memory.selection.id) === String(episode.id);
      return `
        <article class="stack-item ${selected ? "memory-selected" : ""}">
          <small>${escapeHtml(episode.episode_type)}</small>
          <h3>${escapeHtml(episode.title)}</h3>
          <p>${escapeHtml(episode.summary)}</p>
          <div class="meta">${chips([
            `status: ${episode.status}`,
            `start_at: ${formatTime(episode.start_at)}`,
            `end_at: ${formatTime(episode.end_at)}`,
            `provenance_refs: ${episode.provenance_summary?.source_refs?.length || 0}`,
          ])}</div>
          <button class="link-button memory-link" data-memory-kind="episode" data-memory-id="${escapeHtml(episode.id)}" type="button">
            Inspect episode
          </button>
        </article>
      `;
    })
    .join("");
}

function renderMemoryDetail(kind, detail) {
  const root = document.querySelector("#memory-detail");
  if (!detail) {
    root.className = "detail-card empty-state";
    root.textContent = "Select a memory event or episode.";
    return;
  }

  const provenanceItems = (detail.provenance || [])
    .map(
      (item) =>
        `<li><strong>${escapeHtml(item.provenance_type)}</strong>: ${escapeHtml(item.source_table)}:${escapeHtml(item.source_record_id)}</li>`,
    )
    .join("");
  const correctionSummary =
    kind === "event"
      ? [
          `status: ${detail.status}`,
          `superseded_by_id: ${detail.superseded_by_id ?? "none"}`,
          `corrected_by_role: ${detail.corrected_by_role || "none"}`,
        ]
      : [
          `status: ${detail.status}`,
          `corrected_by_role: ${detail.corrected_by_role || "none"}`,
          `linked_events: ${detail.linked_events?.length || 0}`,
        ];
  const linkedSection =
    kind === "event"
      ? `
        <li><strong>linked_entities</strong>: ${(detail.linked_entities || [])
          .map((item) => `${escapeHtml(item.entity_type)}:${escapeHtml(item.canonical_name)}`)
          .join(", ") || "none"}</li>
        <li><strong>episode_memberships</strong>: ${(detail.episode_memberships || [])
          .map((item) => escapeHtml(item.episode.id))
          .join(", ") || "none"}</li>
      `
      : `
        <li><strong>linked_events</strong>: ${(detail.linked_events || [])
          .map((item) => `${escapeHtml(item.event.event_type)}:${escapeHtml(item.event.id)}`)
          .join(", ") || "none"}</li>
      `;

  root.className = "detail-card";
  root.innerHTML = `
    <h3>${escapeHtml(detail.title)}</h3>
    <p>${escapeHtml(kind === "event" ? detail.evidence_text : detail.summary)}</p>
    <div class="meta">${chips([
      `kind: ${kind}`,
      ...correctionSummary,
      `source_refs: ${detail.provenance_summary?.source_refs?.length || 0}`,
    ])}</div>
    <ul class="detail-list">
      <li><strong>id</strong>: ${escapeHtml(detail.id)}</li>
      <li><strong>room_id</strong>: ${escapeHtml(detail.room_id)}</li>
      <li><strong>classification_level</strong>: ${escapeHtml(detail.classification_level)}</li>
      <li><strong>recorded_at</strong>: ${escapeHtml(formatTime(detail.recorded_at || detail.created_at))}</li>
      ${linkedSection}
      <li><strong>provenance</strong>: ${provenanceItems ? `<ul class="detail-list nested-list">${provenanceItems}</ul>` : "none"}</li>
    </ul>
  `;
}

function renderProvenanceEntries(entries = []) {
  if (!entries.length) {
    return "<li>none</li>";
  }
  return entries
    .map((item) => {
      const fieldText = item.source_field ? ` field ${escapeHtml(item.source_field)}` : "";
      const basisValue =
        item.basis_value !== null && item.basis_value !== undefined && item.basis_value !== ""
          ? `=${escapeHtml(item.basis_value)}`
          : "";
      return `
        <li>
          <span class="detail-line">
            <strong>${escapeHtml(item.provenance_type)}</strong>
            <span class="detail-token">${escapeHtml(item.source_table)}:${escapeHtml(item.source_record_id)}</span>
            <span>${escapeHtml(item.basis_type)}${basisValue}</span>
            ${fieldText ? `<span>${fieldText}</span>` : ""}
          </span>
        </li>
      `;
    })
    .join("");
}

function renderMemoryProvenance(kind, provenanceDetail) {
  const root = document.querySelector("#memory-provenance");
  if (!provenanceDetail) {
    root.className = "detail-card empty-state";
    root.textContent = "No provenance detail loaded yet.";
    return;
  }

  const owner = kind === "event" ? provenanceDetail.event : provenanceDetail.episode;
  const summary = provenanceDetail.provenance_summary || {};
  const sourceRefs = summary.source_refs || [];
  const membershipBasis = provenanceDetail.membership_basis || [];

  root.className = "detail-card";
  root.innerHTML = `
    <h3>Provenance Lens</h3>
    <p>Read-only provenance slices for ${escapeHtml(kind)} ${escapeHtml(owner.id)} inside room ${escapeHtml(owner.room_id)}.</p>
    <div class="meta">${chips([
      `total: ${summary.total_count || 0}`,
      `source_lineage: ${summary.source_lineage_count || 0}`,
      `seed_basis: ${summary.seed_basis_count || 0}`,
      `membership_basis: ${summary.membership_basis_count || 0}`,
      `source_refs: ${sourceRefs.length}`,
    ])}</div>
    <div class="provenance-grid">
      <section class="provenance-column">
        <h4>Source Lineage</h4>
        <ul class="detail-list compact-list">${renderProvenanceEntries(provenanceDetail.source_lineage || [])}</ul>
      </section>
      <section class="provenance-column">
        <h4>Seed Basis</h4>
        <ul class="detail-list compact-list">${renderProvenanceEntries(provenanceDetail.seed_basis || [])}</ul>
      </section>
      <section class="provenance-column">
        <h4>${kind === "episode" ? "Membership Basis" : "Full Provenance"}</h4>
        <ul class="detail-list compact-list">${renderProvenanceEntries(
          kind === "episode" ? membershipBasis : provenanceDetail.provenance || [],
        )}</ul>
      </section>
    </div>
    <ul class="detail-list">
      <li><strong>source_refs</strong>: ${sourceRefs.map((item) => escapeHtml(item)).join(", ") || "none"}</li>
      <li><strong>owner_status</strong>: ${escapeHtml(owner.status)}</li>
      <li><strong>correction_reason</strong>: ${escapeHtml(owner.correction_reason || "none")}</li>
    </ul>
  `;
}

function renderMemoryContext(contextPayload) {
  const root = document.querySelector("#memory-context");
  if (!contextPayload) {
    root.className = "detail-card empty-state";
    root.textContent = "No memory context loaded yet.";
    return;
  }

  root.className = "detail-card";
  root.innerHTML = `
    <h3>Context Payload</h3>
    <p>Scope ${escapeHtml(contextPayload.query_scope.scope_kind)} over room ${escapeHtml(contextPayload.room_id)}.</p>
    <div class="meta">${chips([
      `included: ${contextPayload.included_context.length}`,
      `excluded: ${contextPayload.excluded_context.length}`,
      `warnings: ${contextPayload.warnings.length}`,
      `memory_write_enabled: ${contextPayload.memory_write_enabled}`,
    ])}</div>
    <ul class="detail-list">
      <li><strong>included_context</strong>: ${contextPayload.included_context
        .map((item) => `${escapeHtml(item.memory_kind)}:${escapeHtml(item.memory_id)} (${escapeHtml(item.inclusion_reason)})`)
        .join(", ") || "none"}</li>
      <li><strong>excluded_context</strong>: ${contextPayload.excluded_context
        .map((item) => `${escapeHtml(item.memory_kind)}:${escapeHtml(item.memory_id || "n/a")} (${escapeHtml(item.exclusion_reason)})`)
        .join(", ") || "none"}</li>
      <li><strong>source_refs</strong>: ${contextPayload.context_package.provenance_summary.source_refs
        .map((item) => escapeHtml(item))
        .join(", ") || "none"}</li>
      <li><strong>warnings</strong>: ${contextPayload.warnings.map((item) => escapeHtml(item)).join(", ") || "none"}</li>
    </ul>
  `;
}

function renderMemoryAnswer(answer) {
  const root = document.querySelector("#memory-answer");
  if (!answer) {
    root.className = "detail-card empty-state";
    root.textContent = "No memory answer generated yet.";
    return;
  }

  const contentBlocks = answer.source_backed_content.length
    ? answer.source_backed_content
        .map(
          (item) => `
            <li>
              <strong>${escapeHtml(item.content)}</strong>
              <div class="meta">${chips(item.source_refs)}</div>
            </li>
          `,
        )
        .join("")
    : "<li>No source-backed content returned.</li>";

  root.className = "detail-card";
  root.innerHTML = `
    <h3>Read-Only Answer</h3>
    <p>${escapeHtml(answer.question)}</p>
    <div class="meta">${chips([
      `supported: ${answer.supported}`,
      `llm_call_performed: ${answer.llm_call_performed}`,
      `memory_write_enabled: ${answer.memory_write_enabled}`,
    ])}</div>
    <ul class="detail-list">
      ${contentBlocks}
      <li><strong>derived_explanation</strong>: ${escapeHtml(answer.derived_explanation || "none")}</li>
      <li><strong>uncertainty</strong>: ${answer.uncertainty.map((item) => escapeHtml(item)).join(", ") || "none"}</li>
      <li><strong>limitations</strong>: ${answer.limitations.map((item) => escapeHtml(item)).join(", ") || "none"}</li>
    </ul>
  `;
}

function selectedMemoryScopeParams() {
  const selection = state.memory.selection;
  const roomId = state.memory.roomId || document.querySelector("#memory-room-filter").value;
  if (!selection || !roomId) {
    return null;
  }
  const params = new URLSearchParams({ room_id: roomId });
  if (selection.kind === "event") {
    params.set("event_id", String(selection.id));
  } else {
    params.set("episode_id", String(selection.id));
  }
  return params;
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

async function loadMemorySelection(kind, id, options = {}) {
  const { refreshAnswer = true } = options;
  const roomId = state.memory.roomId || document.querySelector("#memory-room-filter").value;
  if (!roomId) {
    return;
  }

  state.memory.selection = { kind, id: String(id) };
  renderMemoryEvents(state.memory.events);
  renderMemoryEpisodes(state.memory.episodes);

  const scopeParams = new URLSearchParams({ room_id: roomId });
  if (kind === "event") {
    scopeParams.set("event_id", String(id));
  } else {
    scopeParams.set("episode_id", String(id));
  }

  const detailUrl =
    kind === "event"
      ? `/api/memory/events/${id}?room_id=${encodeURIComponent(roomId)}`
      : `/api/memory/episodes/${encodeURIComponent(id)}?room_id=${encodeURIComponent(roomId)}`;
  const provenanceUrl =
    kind === "event"
      ? `/api/memory/events/${id}/provenance?room_id=${encodeURIComponent(roomId)}`
      : `/api/memory/episodes/${encodeURIComponent(id)}/provenance?room_id=${encodeURIComponent(roomId)}`;

  try {
    const [detail, provenanceDetail, contextPayload] = await Promise.all([
      fetchJson(detailUrl),
      fetchJson(provenanceUrl),
      fetchJson(`/api/memory/context/payload?${scopeParams.toString()}`),
    ]);
    state.memory.detail = detail;
    state.memory.provenanceDetail = provenanceDetail;
    state.memory.contextPayload = contextPayload;
    renderMemoryDetail(kind, detail);
    renderMemoryProvenance(kind, provenanceDetail);
    renderMemoryContext(contextPayload);
    if (refreshAnswer) {
      await refreshMemoryAnswer();
    }
  } catch (error) {
    document.querySelector("#memory-detail").className = "detail-card empty-state";
    document.querySelector("#memory-detail").textContent = error.message;
    renderMemoryProvenance(null, null);
  }
}

async function refreshMemoryAnswer(event) {
  if (event) {
    event.preventDefault();
  }
  const params = selectedMemoryScopeParams();
  if (!params) {
    renderMemoryAnswer(null);
    return;
  }
  const questionInput = document.querySelector("#memory-question");
  const question = questionInput.value.trim() || "Summarize this context";
  params.set("question", question);
  try {
    const answer = await fetchJson(`/api/memory/context/answer?${params.toString()}`);
    state.memory.answer = answer;
    renderMemoryAnswer(answer);
  } catch (error) {
    document.querySelector("#memory-answer").className = "detail-card empty-state";
    document.querySelector("#memory-answer").textContent = error.message;
  }
}

async function refreshMemoryContextOnly() {
  const params = selectedMemoryScopeParams();
  if (!params) {
    renderMemoryContext(null);
    return;
  }
  try {
    const payload = await fetchJson(`/api/memory/context/payload?${params.toString()}`);
    state.memory.contextPayload = payload;
    renderMemoryContext(payload);
  } catch (error) {
    document.querySelector("#memory-context").className = "detail-card empty-state";
    document.querySelector("#memory-context").textContent = error.message;
  }
}

function chooseMemorySelection(events, episodes) {
  const current = state.memory.selection;
  if (current) {
    const stillExists =
      current.kind === "event"
        ? events.some((event) => String(event.id) === String(current.id))
        : episodes.some((episode) => String(episode.id) === String(current.id));
    if (stillExists) {
      return current;
    }
  }
  if (events.length) {
    return { kind: "event", id: String(events[0].id) };
  }
  if (episodes.length) {
    return { kind: "episode", id: String(episodes[0].id) };
  }
  return null;
}

async function refreshMemoryExplorer(event) {
  if (event) {
    event.preventDefault();
  }

  const roomId = document.querySelector("#memory-room-filter").value;
  if (!roomId) {
    renderMemoryEvents([]);
    renderMemoryEpisodes([]);
    renderMemoryDetail(null, null);
    renderMemoryProvenance(null, null);
    renderMemoryContext(null);
    renderMemoryAnswer(null);
    return;
  }

  state.memory.roomId = roomId;
  const status = document.querySelector("#memory-status-filter").value;
  const eventType = document.querySelector("#memory-event-type-filter").value.trim();
  const episodeType = document.querySelector("#memory-episode-type-filter").value.trim();
  const ingestRunId = document.querySelector("#memory-ingest-run-filter").value.trim();
  const includeCorrected = document.querySelector("#memory-include-corrected").checked;

  const eventParams = new URLSearchParams({
    room_id: roomId,
    limit: "24",
    offset: "0",
  });
  const episodeParams = new URLSearchParams({
    room_id: roomId,
    limit: "24",
    offset: "0",
  });

  if (status) {
    eventParams.set("status", status);
    episodeParams.set("status", status);
  }
  if (eventType) {
    eventParams.set("event_type", eventType);
  }
  if (episodeType) {
    episodeParams.set("episode_type", episodeType);
  }
  if (ingestRunId) {
    eventParams.set("ingest_run_id", ingestRunId);
    episodeParams.set("ingest_run_id", ingestRunId);
  }
  if (!includeCorrected) {
    eventParams.set("include_corrected", "false");
    episodeParams.set("include_corrected", "false");
  }

  try {
    const [events, episodes] = await Promise.all([
      fetchJson(`/api/memory/events?${eventParams.toString()}`),
      fetchJson(`/api/memory/episodes?${episodeParams.toString()}`),
    ]);
    state.memory.events = events;
    state.memory.episodes = episodes;
    renderMemoryEvents(events);
    renderMemoryEpisodes(episodes);

    const nextSelection = chooseMemorySelection(events, episodes);
    if (nextSelection) {
      await loadMemorySelection(nextSelection.kind, nextSelection.id, { refreshAnswer: true });
    } else {
      state.memory.selection = null;
      state.memory.detail = null;
      state.memory.provenanceDetail = null;
      state.memory.contextPayload = null;
      state.memory.answer = null;
      renderMemoryDetail(null, null);
      renderMemoryProvenance(null, null);
      renderMemoryContext(null);
      renderMemoryAnswer(null);
    }
  } catch (error) {
    document.querySelector("#memory-detail").className = "detail-card empty-state";
    document.querySelector("#memory-detail").textContent = error.message;
    renderMemoryProvenance(null, null);
  }
}

async function refreshMissionControl() {
  const [blueprint, status, rooms, guards, datasets, audit, ingestStatus, ingestQueue] = await Promise.all([
    fetchJson("/api/blueprint"),
    fetchJson("/api/status"),
    fetchJson("/api/rooms"),
    fetchJson("/api/governance/guards"),
    fetchJson("/api/datasets"),
    fetchJson("/api/audit"),
    fetchJson("/api/ingest/status"),
    fetchJson("/api/ingest/queue"),
  ]);

  state.blueprint = blueprint;
  state.status = status;
  state.rooms = rooms;
  state.guards = guards;
  state.datasets = datasets;
  state.audit = audit;
  state.ingestStatus = ingestStatus;
  state.ingestQueue = ingestQueue;

  renderMission(blueprint);
  renderStatusCards(status);
  renderDatasets(datasets);
  renderRooms(rooms);
  renderGuards(guards);
  renderAudit(audit);
  renderModules(blueprint.modules);
  renderAgents(blueprint.agents);
  renderPhases(blueprint.build_phases);
  renderIngestQueueJobs(ingestQueue);
  syncIngestQueueSelection();
  renderIngestRuns(ingestStatus);
  renderIngestPreview(state.ingestPreview);
  renderIngestRunManifest(state.ingestManifest);
  populateRoomFilter(rooms);
  populateDatasetFilter(datasets);
  populateMemoryRoomFilter(rooms);
  await refreshAssetBrowser();
  await refreshMemoryExplorer();
}

async function loadIngestRunManifest(runId) {
  try {
    const manifest = await fetchJson(`/api/ingest/runs/${runId}/manifest`);
    state.ingestManifest = manifest;
    renderIngestRunManifest(manifest);
  } catch (error) {
    state.ingestManifest = null;
    const root = document.querySelector("#ingest-run-detail");
    root.className = "detail-card";
    root.textContent = error.message;
  }
}

function collectIngestPayload(form) {
  return Object.fromEntries(new FormData(form).entries());
}

async function previewIngestForm() {
  const form = document.querySelector("#ingest-form");
  const previewButton = document.querySelector("#ingest-preview-button");
  const feedback = document.querySelector("#ingest-feedback");
  const payload = collectIngestPayload(form);

  previewButton.disabled = true;
  feedback.textContent = "Building ingest manifest...";

  try {
    const result = await fetchJson("/api/ingest/preflight?sample_limit=8", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.ingestPreview = result;
    renderIngestPreview(result);
    feedback.textContent = result.can_start_ingest
      ? `Preview ready: ${result.files_discovered} files across ${result.asset_kind_breakdown.length} asset kinds.`
      : `Preview ready with guard warning: ${result.access_guard.reason}`;
  } catch (error) {
    state.ingestPreview = null;
    renderIngestPreview(null);
    feedback.textContent = error.message;
  } finally {
    previewButton.disabled = false;
  }
}

async function queueIngestForm() {
  const form = document.querySelector("#ingest-form");
  const queueButton = document.querySelector("#ingest-queue-button");
  const feedback = document.querySelector("#ingest-feedback");
  const payload = collectIngestPayload(form);

  queueButton.disabled = true;
  feedback.textContent = "Queueing dataset...";

  try {
    const result = await fetchJson("/api/ingest/queue", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.ingestQueueSelectionId = result.job.id;
    feedback.textContent = result.created
      ? `Queue job ${result.job.id} is ${result.job.status} for ${result.job.label}.`
      : `Reused queue job ${result.job.id} for ${result.job.label}.`;
    await refreshMissionControl();
  } catch (error) {
    feedback.textContent = error.message;
  } finally {
    queueButton.disabled = false;
  }
}

async function submitIngestForm(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const submitButton = form.querySelector("button[type='submit']");
  const feedback = document.querySelector("#ingest-feedback");
  const payload = collectIngestPayload(form);

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
    await loadIngestRunManifest(result.run.id);
  } catch (error) {
    feedback.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

async function executeIngestQueueJob(jobId) {
  const feedback = document.querySelector("#ingest-feedback");
  feedback.textContent = `Executing queue job ${jobId}...`;
  try {
    const result = await fetchJson(`/api/ingest/queue/${jobId}/execute`, {
      method: "POST",
    });
    state.ingestQueueSelectionId = result.job.id;
    feedback.textContent =
      result.execution?.run?.summary ||
      result.error ||
      `Queue job ${result.job.id} is now ${result.job.status}.`;
    await refreshMissionControl();
    if (result.execution?.run?.id) {
      await loadIngestRunManifest(result.execution.run.id);
    }
  } catch (error) {
    feedback.textContent = error.message;
  }
}

async function cancelIngestQueueJob(jobId) {
  const feedback = document.querySelector("#ingest-feedback");
  feedback.textContent = `Cancelling queue job ${jobId}...`;
  try {
    const job = await fetchJson(`/api/ingest/queue/${jobId}/cancel`, {
      method: "POST",
    });
    state.ingestQueueSelectionId = job.id;
    feedback.textContent = `Queue job ${job.id} is now ${job.status}.`;
    await refreshMissionControl();
  } catch (error) {
    feedback.textContent = error.message;
  }
}

function bindEvents() {
  document.querySelector("#ingest-form").addEventListener("submit", submitIngestForm);
  document.querySelector("#ingest-preview-button").addEventListener("click", previewIngestForm);
  document.querySelector("#ingest-queue-button").addEventListener("click", queueIngestForm);
  document.querySelector("#asset-refresh").addEventListener("click", refreshAssetBrowser);
  document.querySelector("#asset-room-filter").addEventListener("change", refreshAssetBrowser);
  document.querySelector("#asset-dataset-filter").addEventListener("change", refreshAssetBrowser);
  document.querySelector("#ingest-queue-jobs").addEventListener("click", (event) => {
    const button = event.target.closest("[data-queue-job-id]");
    if (!button || button.disabled) {
      return;
    }
    const { queueAction, queueJobId } = button.dataset;
    if (queueAction === "inspect") {
      state.ingestQueueSelectionId = queueJobId;
      syncIngestQueueSelection();
      return;
    }
    if (queueAction === "execute") {
      executeIngestQueueJob(queueJobId);
      return;
    }
    if (queueAction === "cancel") {
      cancelIngestQueueJob(queueJobId);
      return;
    }
    if (queueAction === "manifest") {
      const job = state.ingestQueue.find((item) => String(item.id) === String(queueJobId));
      if (job?.last_run_id) {
        loadIngestRunManifest(job.last_run_id);
      }
    }
  });
  document.querySelector("#ingest-runs").addEventListener("click", (event) => {
    const button = event.target.closest("[data-ingest-run-id]");
    if (!button || button.disabled) {
      return;
    }
    loadIngestRunManifest(button.dataset.ingestRunId);
  });
  document.querySelector("#asset-table").addEventListener("click", (event) => {
    const button = event.target.closest("[data-asset-id]");
    if (!button) {
      return;
    }
    loadAssetDetail(button.dataset.assetId);
  });

  document.querySelector("#memory-filter-form").addEventListener("submit", refreshMemoryExplorer);
  document.querySelector("#memory-room-filter").addEventListener("change", refreshMemoryExplorer);
  document.querySelector("#memory-context-refresh").addEventListener("click", refreshMemoryContextOnly);
  document.querySelector("#memory-question-form").addEventListener("submit", refreshMemoryAnswer);
  document.querySelector("#memory-events").addEventListener("click", (event) => {
    const button = event.target.closest("[data-memory-kind='event']");
    if (!button) {
      return;
    }
    loadMemorySelection("event", button.dataset.memoryId);
  });
  document.querySelector("#memory-episodes").addEventListener("click", (event) => {
    const button = event.target.closest("[data-memory-kind='episode']");
    if (!button) {
      return;
    }
    loadMemorySelection("episode", button.dataset.memoryId);
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
