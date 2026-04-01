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
  ingestQueueHistory: null,
  ingestPreview: null,
  ingestManifest: null,
  dialogueCorpus: null,
  constitution: null,
  simulation: {
    board: null,
    selectedRoomId: "",
    selectedSquare: null,
    squareDetail: null,
    worldMemory: null,
  },
  assets: [],
  selectedAsset: null,
  artMetrics: null,
  artComparisonSelectionIds: [],
  artComparison: null,
  artComparisonError: null,
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

const MAX_ART_COMPARISON_ASSETS = 8;
const ART_COMPARISON_METRIC_FIELDS = [
  "brightness_mean",
  "contrast_stddev",
  "edge_density",
  "ink_coverage_ratio",
  "colorfulness",
  "entropy",
  "symmetry_vertical",
  "symmetry_horizontal",
];

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

function renderConstitution(constitution) {
  const root = document.querySelector("#constitution-detail");
  if (!constitution) {
    root.className = "detail-card empty-state";
    root.textContent = "No constitution shell loaded yet.";
    return;
  }

  const parameterMarkup = constitution.parameters?.length
    ? `<ul class="manifest-list">${constitution.parameters
        .map(
          (item) =>
            `<li><strong>${escapeHtml(item.key)}</strong>: ${escapeHtml(item.value)} <span class="table-subtitle">${escapeHtml(
              item.category,
            )} | range ${escapeHtml(item.min_value)}-${escapeHtml(item.max_value)}</span><div>${escapeHtml(
              item.description,
            )}</div></li>`,
        )
        .join("")}</ul>`
    : '<div class="empty-state">No constitution parameters are visible yet.</div>';

  const changeMarkup = constitution.recent_changes?.length
    ? `<ul class="manifest-list">${constitution.recent_changes
        .map(
          (item) =>
            `<li><strong>${escapeHtml(item.version)}</strong>: ${escapeHtml(item.summary)} <span class="table-subtitle">${escapeHtml(
              formatTime(item.changed_at),
            )} by ${escapeHtml(item.actor)}</span><div>${escapeHtml(item.effect_scope)}</div></li>`,
        )
        .join("")}</ul>`
    : '<div class="empty-state">No constitution change log is visible yet.</div>';

  root.className = "detail-card";
  root.innerHTML = `
    <h3>Constitution Snapshot</h3>
    <p>${escapeHtml(constitution.summary)}</p>
    <div class="meta">${chips([
      `profile_id: ${constitution.profile_id}`,
      `layer_version: ${constitution.layer_version}`,
      `approval_state: ${constitution.approval_state}`,
      `read_only: ${constitution.read_only}`,
      `routing_influence_enabled: ${constitution.routing_influence_enabled}`,
      `parameters: ${constitution.parameter_count}`,
      `changes: ${constitution.change_count}`,
    ])}</div>
    <div class="preview-grid">
      <section class="preview-block">
        <h4>Parameters</h4>
        ${parameterMarkup}
      </section>
      <section class="preview-block">
        <h4>Recent Changes</h4>
        ${changeMarkup}
      </section>
    </div>
    <section class="preview-block warning-list">
      <h4>Notes and Warnings</h4>
      <ul class="manifest-list">
        ${constitution.notes.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        ${constitution.warnings.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
      </ul>
    </section>
  `;
}

function renderHybridBoard(board) {
  const summaryRoot = document.querySelector("#simulation-board-summary");
  const boardRoot = document.querySelector("#simulation-board-shell");
  if (!board) {
    summaryRoot.className = "detail-card empty-state";
    summaryRoot.textContent = "No hybrid board projection loaded yet.";
    boardRoot.className = "detail-card empty-state";
    boardRoot.textContent = "No board projection loaded yet.";
    return;
  }

  summaryRoot.className = "detail-card";
  summaryRoot.innerHTML = `
    <h3>Projection Summary</h3>
    <p>The hybrid board is a governed runtime surface projected from audit and memory evidence. It does not replace the source of truth.</p>
    <div class="meta">${chips([
      `version: ${board.projection_version}`,
      `read_only: ${board.read_only}`,
      board.requested_room_id ? `room: ${board.requested_room_id}` : `rooms: ${board.resolved_room_ids.length}`,
      `events: ${board.source_totals.memory_events}`,
      `episodes: ${board.source_totals.memory_episodes}`,
      `audit: ${board.source_totals.audit_events}`,
    ])}</div>
    <ul class="detail-list">
      ${board.notes.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
    ${
      board.warnings?.length
        ? `<div class="meta">${chips(board.warnings.map((warning) => `warning: ${warning}`))}</div>`
        : ""
    }
  `;

  const squaresByKey = new Map(board.squares.map((square) => [`${square.row_id}:${square.column_id}`, square]));
  const headerMarkup = board.column_axes
    .map(
      (column) => `
        <div class="hybrid-axis hybrid-axis-column" title="${escapeHtml(column.description)}">
          <strong>${escapeHtml(column.label)}</strong>
        </div>
      `,
    )
    .join("");

  const rowMarkup = board.row_axes
    .map((row) => {
      const cells = board.column_axes
        .map((column) => {
          const square = squaresByKey.get(`${row.id}:${column.id}`);
          if (!square) {
            return '<div class="hybrid-board-cell hybrid-board-cell-empty">n/a</div>';
          }
          const selected =
            state.simulation.selectedSquare?.rowId === square.row_id &&
            state.simulation.selectedSquare?.columnId === square.column_id;
          return `
            <div
              class="hybrid-board-cell hybrid-${escapeHtml(square.dominant_polarity)} ${selected ? "hybrid-selected" : ""}"
              style="--hybrid-intensity:${Math.max(0.08, square.intensity)};"
              title="${escapeHtml(square.title)} | markers: ${escapeHtml(square.top_markers.join(", ") || "none")}"
              data-hybrid-row-id="${escapeHtml(square.row_id)}"
              data-hybrid-column-id="${escapeHtml(square.column_id)}"
            >
              <div class="hybrid-cell-title">${escapeHtml(square.dominant_polarity)}</div>
              <div class="hybrid-cell-metric">${square.activity_score.toFixed(2)}</div>
              <div class="hybrid-cell-subtitle">e${square.event_count} / ep${square.episode_count} / a${square.audit_count}</div>
              <div class="hybrid-cell-subtitle">scar ${square.scar_score.toFixed(2)}</div>
            </div>
          `;
        })
        .join("");

      return `
        <div class="hybrid-axis hybrid-axis-row" title="${escapeHtml(row.description)}">
          <strong>${escapeHtml(row.label)}</strong>
        </div>
        ${cells}
      `;
    })
    .join("");

  boardRoot.className = "detail-card";
  boardRoot.innerHTML = `
    <div class="hybrid-board-scroll">
      <div class="hybrid-board-grid">
        <div class="hybrid-axis hybrid-axis-corner">Board</div>
        ${headerMarkup}
        ${rowMarkup}
      </div>
    </div>
  `;
}

function renderHybridBoardDetail(detail) {
  const root = document.querySelector("#simulation-board-detail");
  if (!detail) {
    root.className = "detail-card empty-state";
    root.textContent = "Select a board square to inspect its source slices.";
    return;
  }

  root.className = "detail-card";
  root.innerHTML = `
    <h3>${escapeHtml(detail.square.title)}</h3>
    <p>Source slices that currently feed this governed simulation square.</p>
    <div class="meta">${chips([
      `signals: ${detail.square.signal_count}`,
      `activity: ${detail.square.activity_score.toFixed(2)}`,
      `alignment: ${detail.square.alignment_score.toFixed(2)}`,
      `sources: ${detail.source_count}`,
      detail.requested_room_id ? `room: ${detail.requested_room_id}` : `rooms: ${detail.resolved_room_ids.length}`,
    ])}</div>
    ${
      detail.sources?.length
        ? `<div class="stack compact-stack">${detail.sources
            .map(
              (source) => `
                <article class="stack-item compact-item">
                  <small>${escapeHtml(source.source_kind)}</small>
                  <h3>${escapeHtml(source.title)}</h3>
                  <p>${escapeHtml(source.summary)}</p>
                  <div class="meta">${chips([
                    `room: ${source.room_id}`,
                    `status: ${source.status || "n/a"}`,
                    `at: ${formatTime(source.occurred_at)}`,
                    ...source.markers.map((marker) => `marker: ${marker}`),
                  ])}</div>
                  ${
                    source.route_hint
                      ? `<div class="table-subtitle">${escapeHtml(source.route_hint)}</div>`
                      : ""
                  }
                </article>
              `,
            )
            .join("")}</div>`
        : '<div class="empty-state">No source slices mapped to this square.</div>'
    }
  `;
}

function renderWorldMemory(worldMemory) {
  const summaryRoot = document.querySelector("#world-memory-summary");
  const shellRoot = document.querySelector("#world-memory-shell");
  if (!worldMemory) {
    summaryRoot.className = "detail-card empty-state";
    summaryRoot.textContent = "No world-memory shell loaded yet.";
    shellRoot.className = "detail-card empty-state";
    shellRoot.textContent = "No world-memory shell loaded yet.";
    return;
  }

  summaryRoot.className = "detail-card";
  summaryRoot.innerHTML = `
    <h3>World Memory Summary</h3>
    <p>The first world-memory shell groups indexed local assets into deterministic place anchors and clusters.</p>
    <div class="meta">${chips([
      `version: ${worldMemory.projection_version}`,
      `read_only: ${worldMemory.read_only}`,
      worldMemory.requested_room_id ? `room: ${worldMemory.requested_room_id}` : `rooms: ${worldMemory.resolved_room_ids.length}`,
      `nodes: ${worldMemory.node_count}`,
      `clusters: ${worldMemory.cluster_count}`,
      ...worldMemory.anchor_types.map((anchorType) => `type: ${anchorType}`),
    ])}</div>
    <ul class="detail-list">
      ${worldMemory.notes.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
    ${
      worldMemory.warnings?.length
        ? `<div class="meta">${chips(worldMemory.warnings.map((warning) => `warning: ${warning}`))}</div>`
        : ""
    }
  `;

  const clusterMarkup = worldMemory.clusters?.length
    ? `<div class="stack compact-stack">${worldMemory.clusters
        .slice(0, 8)
        .map(
          (cluster) => `
            <article class="stack-item compact-item">
              <small>${escapeHtml(cluster.room_id)}</small>
              <h3>${escapeHtml(cluster.label)}</h3>
              <div class="meta">${chips([
                `nodes: ${cluster.node_count}`,
                `dataset: ${cluster.dataset_label}`,
                `kind: ${cluster.dominant_asset_kind}`,
                `recent: ${formatTime(cluster.recent_indexed_at)}`,
              ])}</div>
            </article>
          `,
        )
        .join("")}</div>`
    : '<div class="empty-state">No world-memory clusters available yet.</div>';

  const nodeMarkup = worldMemory.nodes?.length
    ? `<div class="stack compact-stack">${worldMemory.nodes
        .slice(0, 16)
        .map(
          (node) => `
            <article class="stack-item compact-item">
              <small>${escapeHtml(node.anchor_type)}</small>
              <h3>${escapeHtml(node.label)}</h3>
              <div class="meta">${chips([
                `room: ${node.room_id}`,
                `dataset: ${node.dataset_label}`,
                `kind: ${node.asset_kind}`,
                `intensity: ${node.intensity.toFixed(2)}`,
                `indexed: ${formatTime(node.indexed_at)}`,
              ])}</div>
            </article>
          `,
        )
        .join("")}</div>`
    : '<div class="empty-state">No world-memory nodes available yet.</div>';

  shellRoot.className = "detail-card";
  shellRoot.innerHTML = `
    <div class="preview-grid">
      <section class="preview-block">
        <h4>Clusters</h4>
        ${clusterMarkup}
      </section>
      <section class="preview-block">
        <h4>Recent Nodes</h4>
        ${nodeMarkup}
      </section>
    </div>
  `;
}

function renderDialogueCorpus(analysis) {
  const root = document.querySelector("#dialogue-corpus-detail");
  if (!analysis) {
    root.className = "detail-card empty-state";
    root.textContent =
      "Analyze a local Messenger export root or ChatGPT export JSON file without writing raw dialogue into memory.";
    return;
  }

  const selectedSource = analysis.detected_sources?.find((item) => item.selected);

  const sourceMarkup = analysis.detected_sources?.length
    ? `<ul class="manifest-list">${analysis.detected_sources
        .map(
          (source) =>
            `<li><strong>${escapeHtml(source.label)}</strong>: ${escapeHtml(source.status)} (${escapeHtml(
              source.record_count,
            )} records) <span class="table-subtitle">${escapeHtml(source.path)}${source.selected ? " | selected" : ""}</span></li>`,
        )
        .join("")}</ul>`
    : '<div class="empty-state">No source roots discovered.</div>';

  const sectionMarkup = analysis.section_breakdown?.length
    ? `<ul class="manifest-list">${analysis.section_breakdown
        .map(
          (item) =>
            `<li><strong>${escapeHtml(item.section)}</strong>: ${escapeHtml(item.thread_count)} threads, ${escapeHtml(
              item.message_count,
            )} messages</li>`,
        )
        .join("")}</ul>`
    : '<div class="empty-state">No section breakdown is available.</div>';

  const counterpartMarkup = analysis.top_counterparts?.length
    ? `<ul class="manifest-list">${analysis.top_counterparts
        .map(
          (item) =>
            `<li><strong>${escapeHtml(item.name)}</strong>: ${escapeHtml(
              item.interaction_message_count,
            )} direct-thread interactions <span class="table-subtitle">${escapeHtml(
              item.thread_count,
            )} threads | last ${escapeHtml(formatTime(item.last_message_at))}</span></li>`,
        )
        .join("")}</ul>`
    : '<div class="empty-state">No direct counterpart ranking is available for this source.</div>';

  const groupMarkup = analysis.top_group_threads?.length
    ? `<ul class="manifest-list">${analysis.top_group_threads
        .map(
          (item) =>
            `<li><strong>${escapeHtml(item.title)}</strong>: ${escapeHtml(
              item.message_count,
            )} messages <span class="table-subtitle">${escapeHtml(
              item.participant_count,
            )} participants | last ${escapeHtml(formatTime(item.last_message_at))}</span></li>`,
        )
        .join("")}</ul>`
    : '<div class="empty-state">No group-thread ranking is available for this source.</div>';

  const termMarkup = analysis.top_terms?.length
    ? `<div class="meta">${analysis.top_terms
        .map((item) => `<span class="chip">${escapeHtml(item.token)} (${escapeHtml(item.count)})</span>`)
        .join("")}</div>`
    : '<div class="empty-state">No stable topical hints were extracted.</div>';

  const styleMarkup = analysis.style_signals?.length
    ? `<ul class="manifest-list">${analysis.style_signals
        .map(
          (item) =>
            `<li><strong>${escapeHtml(item.label)}</strong>: ${escapeHtml(item.value)} ${escapeHtml(
              item.unit,
            )}<div>${escapeHtml(item.summary)}</div></li>`,
        )
        .join("")}</ul>`
    : '<div class="empty-state">No style signals are available yet.</div>';

  const activityMarkup = analysis.activity_by_year?.length
    ? `<ul class="manifest-list">${analysis.activity_by_year
        .map(
          (item) =>
            `<li><strong>${escapeHtml(item.bucket)}</strong>: ${escapeHtml(item.message_count)} messages <span class="table-subtitle">${escapeHtml(
              item.thread_count,
            )} threads | sent ${escapeHtml(item.sent_message_count)} | received ${escapeHtml(
              item.received_message_count,
            )}</span></li>`,
        )
        .join("")}</ul>`
    : '<div class="empty-state">No activity timeline is available.</div>';

  const notesMarkup = [...(analysis.relationship_priors || []), ...(analysis.history_priors || []), ...(analysis.clone_foundation || []), ...(analysis.notes || []), ...(analysis.warnings || [])]
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");

  root.className = "detail-card";
  root.innerHTML = `
    <h3>Dialogue Corpus Snapshot</h3>
    <p>${escapeHtml(analysis.source_kind)} routed from ${escapeHtml(analysis.requested_path)} into a read-only corpus summary.</p>
    <div class="meta">${chips([
      `selected_source: ${selectedSource?.label || analysis.selected_source_path}`,
      `owner_name: ${analysis.owner_name}`,
      `room: ${analysis.recommended_room_id}`,
      `classification: ${analysis.recommended_classification_level}`,
      `threads: ${analysis.thread_count}`,
      `direct_threads: ${analysis.direct_thread_count}`,
      `group_threads: ${analysis.group_thread_count}`,
      `counterparts: ${analysis.counterpart_count}`,
      `participants: ${analysis.unique_participant_count}`,
      `messages: ${analysis.message_count}`,
      `sent: ${analysis.sent_message_count}`,
      `received: ${analysis.received_message_count}`,
      `attachments: ${analysis.attachment_message_count}`,
      `first: ${formatTime(analysis.first_message_at)}`,
      `last: ${formatTime(analysis.last_message_at)}`,
    ])}</div>
    <div class="preview-grid">
      <section class="preview-block">
        <h4>Detected Sources</h4>
        ${sourceMarkup}
      </section>
      <section class="preview-block">
        <h4>Section Breakdown</h4>
        ${sectionMarkup}
      </section>
      <section class="preview-block">
        <h4>Top Counterparts</h4>
        ${counterpartMarkup}
      </section>
      <section class="preview-block">
        <h4>Top Group Threads</h4>
        ${groupMarkup}
      </section>
      <section class="preview-block">
        <h4>Activity by Year</h4>
        ${activityMarkup}
      </section>
      <section class="preview-block">
        <h4>Style Signals</h4>
        ${styleMarkup}
      </section>
    </div>
    <section class="preview-block">
      <h4>Top Terms</h4>
      ${termMarkup}
    </section>
    <section class="preview-block warning-list">
      <h4>Notes and Warnings</h4>
      <ul class="manifest-list">${notesMarkup}</ul>
    </section>
  `;
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
            <button class="link-button" data-queue-action="execute" data-queue-job-id="${job.id}" type="button" ${job.can_execute ? "" : "disabled"}>${job.status === "interrupted" ? "Resume" : "Execute"}</button>
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

  const history =
    state.ingestQueueHistory && String(state.ingestQueueHistory.job?.id || "") === String(job.id)
      ? state.ingestQueueHistory
      : null;
  const historyMarkup = !history
    ? '<div class="empty-state">Use Inspect to load bounded queue lifecycle history.</div>'
    : history.history_events?.length
      ? `<ul class="manifest-list">${history.history_events
          .map(
            (event) =>
              `<li><strong>${escapeHtml(event.event_type)}</strong>: ${escapeHtml(event.summary)} <span class="table-subtitle">${escapeHtml(formatTime(event.created_at))}</span></li>`,
          )
          .join("")}</ul>`
      : '<div class="empty-state">No queue lifecycle events recorded for this job yet.</div>';
  const linkedRunMarkup = history?.linked_run
    ? `<ul class="detail-list">
        <li><strong>run_id</strong>: ${escapeHtml(history.linked_run.id)}</li>
        <li><strong>run_status</strong>: ${escapeHtml(history.linked_run.status)}</li>
        <li><strong>dataset_label</strong>: ${escapeHtml(history.linked_run.dataset_label)}</li>
        <li><strong>has_manifest</strong>: ${escapeHtml(history.linked_manifest_available)}</li>
        <li><strong>manifest_route</strong>: ${escapeHtml(history.linked_manifest_route || "none")}</li>
      </ul>`
    : '<div class="empty-state">No linked ingest run is attached to this queue job yet.</div>';

  root.className = "detail-card";
  root.innerHTML = `
    <h3>Queue Job ${job.id}</h3>
    <p>${escapeHtml(job.label)} in ${escapeHtml(job.room_id)} persists the ingest request for manual execution, retry, and interrupted-run recovery.</p>
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
    <div class="preview-grid">
      <section class="preview-block">
        <h4>Queue History</h4>
        ${historyMarkup}
      </section>
      <section class="preview-block">
        <h4>Linked Run Reference</h4>
        ${linkedRunMarkup}
      </section>
    </div>
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
    state.ingestQueueHistory = null;
    renderIngestQueueDetail(null);
    return;
  }

  const selected =
    state.ingestQueue.find((job) => String(job.id) === String(state.ingestQueueSelectionId || "")) ||
    state.ingestQueue[0];
  state.ingestQueueSelectionId = selected.id;
  if (String(state.ingestQueueHistory?.job?.id || "") !== String(selected.id)) {
    state.ingestQueueHistory = null;
  }
  renderIngestQueueDetail(selected);
}

function renderAssets(assets) {
  const root = document.querySelector("#asset-table");
  const roomId = document.querySelector("#asset-room-filter")?.value || "";
  const selectedIds = new Set(state.artComparisonSelectionIds.map((item) => String(item)));
  if (!assets.length) {
    root.innerHTML = '<tr><td colspan="8" class="empty-cell">No assets in the current room scope.</td></tr>';
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
          <td>
            <label class="table-checkbox">
              <input
                type="checkbox"
                data-compare-asset-id="${asset.id}"
                ${selectedIds.has(String(asset.id)) ? "checked" : ""}
                ${roomId && asset.asset_kind === "image" ? "" : "disabled"}
              />
              <span>${roomId ? (asset.asset_kind === "image" ? "select" : "image only") : "pick room"}</span>
            </label>
          </td>
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

function renderArtMetrics(metrics, asset = null) {
  const root = document.querySelector("#art-metrics");
  if (!asset) {
    root.className = "detail-card empty-state";
    root.textContent = "Select an image asset to inspect formal metrics.";
    return;
  }
  if (asset.asset_kind !== "image") {
    root.className = "detail-card empty-state";
    root.textContent = `Art metrics currently support image assets only. Selected asset kind: ${asset.asset_kind}.`;
    return;
  }
  if (!metrics) {
    root.className = "detail-card empty-state";
    root.textContent = "No art metrics loaded yet.";
    return;
  }

  root.className = "detail-card";
  root.innerHTML = `
    <h3>${escapeHtml(metrics.file_name)}</h3>
    <p>${escapeHtml(metrics.relative_path)} in ${escapeHtml(metrics.room_id)} is measured through deterministic formal image metrics only.</p>
    <div class="meta">${chips([
      `analysis_version: ${metrics.analysis_version}`,
      `orientation: ${metrics.orientation}`,
      `size: ${metrics.width_px}x${metrics.height_px}`,
      `sample: ${metrics.sample_width_px}x${metrics.sample_height_px}`,
      `edge_density: ${metrics.edge_density}`,
      `ink_coverage: ${metrics.ink_coverage_ratio}`,
      `colorfulness: ${metrics.colorfulness}`,
    ])}</div>
    <ul class="detail-list">
      <li><strong>aspect_ratio</strong>: ${escapeHtml(metrics.aspect_ratio)}</li>
      <li><strong>brightness_mean</strong>: ${escapeHtml(metrics.brightness_mean)}</li>
      <li><strong>contrast_stddev</strong>: ${escapeHtml(metrics.contrast_stddev)}</li>
      <li><strong>dark_pixel_ratio</strong>: ${escapeHtml(metrics.dark_pixel_ratio)}</li>
      <li><strong>light_pixel_ratio</strong>: ${escapeHtml(metrics.light_pixel_ratio)}</li>
      <li><strong>entropy</strong>: ${escapeHtml(metrics.entropy)}</li>
      <li><strong>symmetry_vertical</strong>: ${escapeHtml(metrics.symmetry_vertical)}</li>
      <li><strong>symmetry_horizontal</strong>: ${escapeHtml(metrics.symmetry_horizontal)}</li>
      <li><strong>center_of_mass_x</strong>: ${escapeHtml(metrics.center_of_mass_x)}</li>
      <li><strong>center_of_mass_y</strong>: ${escapeHtml(metrics.center_of_mass_y)}</li>
      <li><strong>quantized_color_count</strong>: ${escapeHtml(metrics.quantized_color_count)}</li>
      <li><strong>notes</strong>: ${metrics.notes.map((item) => escapeHtml(item)).join(", ")}</li>
      <li><strong>warnings</strong>: ${metrics.warnings.map((item) => escapeHtml(item)).join(", ") || "none"}</li>
    </ul>
  `;
}

function renderArtComparison() {
  const root = document.querySelector("#art-comparison");
  const roomId = document.querySelector("#asset-room-filter")?.value || "";
  const selectedAssets = state.artComparisonSelectionIds
    .map((assetId) => state.assets.find((asset) => String(asset.id) === String(assetId)))
    .filter(Boolean);
  const selectedMarkup = selectedAssets.length
    ? `<ul class="manifest-list">${selectedAssets
        .map(
          (asset) =>
            `<li><strong>${escapeHtml(asset.file_name)}</strong>: ${escapeHtml(asset.dataset_label)} (${escapeHtml(
              formatTime(asset.fs_modified_at),
            )})</li>`,
        )
        .join("")}</ul>`
    : '<div class="empty-state">No image assets selected for comparison yet.</div>';
  const actionsMarkup = `
    <div class="form-actions">
      <button
        class="button button-secondary"
        data-art-compare-action="run"
        type="button"
        ${roomId && selectedAssets.length >= 2 ? "" : "disabled"}
      >
        Run Compare
      </button>
      <button
        class="button button-secondary"
        data-art-compare-action="clear"
        type="button"
        ${selectedAssets.length ? "" : "disabled"}
      >
        Clear Selection
      </button>
    </div>
  `;

  if (!roomId) {
    root.className = "detail-card";
    root.innerHTML = `
      <h3>Bounded Art Comparison</h3>
      <p>Select one room in the asset browser first. Comparison stays room-scoped and only works over the assets visible in that room.</p>
      ${actionsMarkup}
    `;
    return;
  }

  const errorMarkup = state.artComparisonError
    ? `<div class="empty-state">${escapeHtml(state.artComparisonError)}</div>`
    : "";

  if (selectedAssets.length < 2 || !state.artComparison) {
    root.className = "detail-card";
    root.innerHTML = `
      <h3>Bounded Art Comparison</h3>
      <p>Select 2 to ${MAX_ART_COMPARISON_ASSETS} image assets from the current room to inspect the existing V1.2 comparison payload in Mission Control.</p>
      <div class="meta">${chips([
        `room: ${roomId}`,
        `selected_assets: ${selectedAssets.length}`,
        `max_assets: ${MAX_ART_COMPARISON_ASSETS}`,
      ])}</div>
      ${actionsMarkup}
      ${errorMarkup}
      <section class="preview-block warning-list">
        <h4>Selected Assets</h4>
        ${selectedMarkup}
      </section>
    `;
    return;
  }

  const comparison = state.artComparison;
  const deltaMarkup = comparison.metric_deltas?.length
    ? `<ul class="manifest-list">${comparison.metric_deltas
        .map(
          (item) =>
            `<li><strong>${escapeHtml(item.metric_name)}</strong>: ${escapeHtml(item.start_value)} -> ${escapeHtml(
              item.end_value,
            )} (delta ${escapeHtml(item.delta)})</li>`,
        )
        .join("")}</ul>`
    : '<div class="empty-state">No metric deltas returned.</div>';
  const comparedAssetsMarkup = comparison.compared_assets?.length
    ? comparison.compared_assets
        .map((item) => {
          const metricMarkup = ART_COMPARISON_METRIC_FIELDS.map(
            (metricName) =>
              `<li><strong>${escapeHtml(metricName)}</strong>: ${escapeHtml(item.metrics[metricName])}</li>`,
          ).join("");
          return `
            <li>
              <strong>#${item.position} ${escapeHtml(item.file_name)}</strong>
              <div class="meta">${chips([
                `asset_id: ${item.asset_id}`,
                `dataset: ${item.dataset_label}`,
                `modified: ${formatTime(item.fs_modified_at)}`,
              ])}</div>
              <ul class="detail-list compact-list">${metricMarkup}</ul>
            </li>
          `;
        })
        .join("")
    : "<li>No compared asset records returned.</li>";

  root.className = "detail-card";
  root.innerHTML = `
    <h3>Bounded Art Comparison</h3>
    <p>The current room selection reuses the existing read-only V1.2 comparison seam without adding new metrics, learned features, or writeback behavior.</p>
    <div class="meta">${chips([
      `room: ${comparison.room_id}`,
      `comparison_version: ${comparison.comparison_version}`,
      `analysis_version: ${comparison.analysis_version}`,
      `asset_count: ${comparison.asset_count}`,
      `ordering_basis: ${comparison.ordering_basis}`,
    ])}</div>
    ${actionsMarkup}
    ${errorMarkup}
    <div class="preview-grid">
      <section class="preview-block">
        <h4>Selected Assets</h4>
        ${selectedMarkup}
      </section>
      <section class="preview-block">
        <h4>Metric Deltas</h4>
        ${deltaMarkup}
      </section>
    </div>
    <section class="preview-block warning-list">
      <h4>Compared Assets</h4>
      <ul class="manifest-list">${comparedAssetsMarkup}</ul>
    </section>
    <section class="preview-block warning-list">
      <h4>Notes and Warnings</h4>
      <ul class="manifest-list">
        ${comparison.notes.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
        ${
          comparison.warnings.length
            ? comparison.warnings.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
            : "<li>No comparison warnings.</li>"
        }
      </ul>
    </section>
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

function populateSimulationRoomFilter(rooms) {
  const select = document.querySelector("#simulation-room-filter");
  const current = state.simulation.selectedRoomId || select.value;
  select.innerHTML = [
    '<option value="">All readable rooms</option>',
    ...rooms.map((room) => `<option value="${escapeHtml(room.id)}">${escapeHtml(room.label)}</option>`),
  ].join("");
  select.value = rooms.some((room) => room.id === current) ? current : "";
  state.simulation.selectedRoomId = select.value;
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
  state.assets = assets;
  state.artComparisonSelectionIds = roomId
    ? state.artComparisonSelectionIds.filter((assetId) =>
        assets.some(
          (asset) => String(asset.id) === String(assetId) && asset.asset_kind === "image",
        ),
      )
    : [];
  state.artComparison = null;
  state.artComparisonError = null;
  renderAssets(assets);
  renderArtComparison();
}

async function loadAssetDetail(assetId) {
  try {
    const asset = await fetchJson(`/api/assets/${assetId}`);
    state.selectedAsset = asset;
    renderAssetDetail(asset);
    if (asset.asset_kind !== "image") {
      state.artMetrics = null;
      renderArtMetrics(null, asset);
      return;
    }
    try {
      const metrics = await fetchJson(`/api/art/assets/${assetId}/metrics`);
      state.artMetrics = metrics;
      renderArtMetrics(metrics, asset);
    } catch (error) {
      state.artMetrics = null;
      const root = document.querySelector("#art-metrics");
      root.className = "detail-card";
      root.textContent = error.message;
    }
  } catch (error) {
    state.selectedAsset = null;
    state.artMetrics = null;
    document.querySelector("#asset-detail").textContent = error.message;
    renderArtMetrics(null, null);
  }
}

function toggleArtComparisonSelection(assetId, checked) {
  const normalizedId = String(assetId);
  const nextSelection = state.artComparisonSelectionIds
    .map((item) => String(item))
    .filter((item) => item !== normalizedId);

  if (checked) {
    if (nextSelection.length >= MAX_ART_COMPARISON_ASSETS) {
      state.artComparisonError = `Art comparison supports at most ${MAX_ART_COMPARISON_ASSETS} assets per request.`;
      renderAssets(state.assets);
      renderArtComparison();
      return;
    }
    nextSelection.push(normalizedId);
  }

  state.artComparisonSelectionIds = nextSelection;
  state.artComparison = null;
  state.artComparisonError = null;
  renderAssets(state.assets);
  renderArtComparison();
}

function clearArtComparisonSelection() {
  state.artComparisonSelectionIds = [];
  state.artComparison = null;
  state.artComparisonError = null;
  renderAssets(state.assets);
  renderArtComparison();
}

async function runArtComparison() {
  const roomId = document.querySelector("#asset-room-filter").value;
  if (!roomId) {
    state.artComparison = null;
    state.artComparisonError = "Select a single room in the asset browser before comparing art assets.";
    renderArtComparison();
    return;
  }

  if (state.artComparisonSelectionIds.length < 2) {
    state.artComparison = null;
    state.artComparisonError = "Select at least two image assets for comparison.";
    renderArtComparison();
    return;
  }

  const root = document.querySelector("#art-comparison");
  root.className = "detail-card";
  root.innerHTML = `
    <h3>Bounded Art Comparison</h3>
    <p>Loading comparison for ${state.artComparisonSelectionIds.length} selected assets in ${escapeHtml(roomId)}...</p>
  `;

  const params = new URLSearchParams({ room_id: roomId });
  state.artComparisonSelectionIds.forEach((assetId) => {
    params.append("asset_id", String(assetId));
  });

  try {
    const comparison = await fetchJson(`/api/art/assets/compare?${params.toString()}`);
    state.artComparison = comparison;
    state.artComparisonError = null;
    renderArtComparison();
  } catch (error) {
    state.artComparison = null;
    state.artComparisonError = error.message;
    renderArtComparison();
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

async function loadHybridBoardSquareDetail(rowId, columnId) {
  state.simulation.selectedSquare = { rowId, columnId };
  renderHybridBoard(state.simulation.board);

  const params = new URLSearchParams();
  if (state.simulation.selectedRoomId) {
    params.set("room_id", state.simulation.selectedRoomId);
  }

  try {
    const detail = await fetchJson(
      `/api/simulation/hybrid-board/squares/${encodeURIComponent(rowId)}/${encodeURIComponent(columnId)}?${params.toString()}`,
    );
    state.simulation.squareDetail = detail;
    renderHybridBoardDetail(detail);
  } catch (error) {
    state.simulation.squareDetail = null;
    const root = document.querySelector("#simulation-board-detail");
    root.className = "detail-card";
    root.textContent = error.message;
  }
}

async function refreshSimulationProjection(options = {}) {
  const { preserveSelection = true } = options;
  const params = new URLSearchParams();
  if (state.simulation.selectedRoomId) {
    params.set("room_id", state.simulation.selectedRoomId);
  }
  const query = params.toString();
  const suffix = query ? `?${query}` : "";

  try {
    const [board, worldMemory] = await Promise.all([
      fetchJson(`/api/simulation/hybrid-board${suffix}`),
      fetchJson(`/api/simulation/world-memory${suffix}`),
    ]);
    state.simulation.board = board;
    state.simulation.worldMemory = worldMemory;
    renderHybridBoard(board);
    renderWorldMemory(worldMemory);

    if (
      preserveSelection &&
      state.simulation.selectedSquare &&
      board.squares.some(
        (square) =>
          square.row_id === state.simulation.selectedSquare.rowId &&
          square.column_id === state.simulation.selectedSquare.columnId,
      )
    ) {
      await loadHybridBoardSquareDetail(
        state.simulation.selectedSquare.rowId,
        state.simulation.selectedSquare.columnId,
      );
      return;
    }

    const nextSquare = board.squares.find((square) => square.activity_score > 0) || board.squares[0];
    if (nextSquare) {
      await loadHybridBoardSquareDetail(nextSquare.row_id, nextSquare.column_id);
    } else {
      state.simulation.selectedSquare = null;
      state.simulation.squareDetail = null;
      renderHybridBoardDetail(null);
    }
  } catch (error) {
    state.simulation.board = null;
    state.simulation.worldMemory = null;
    state.simulation.squareDetail = null;
    renderHybridBoard(null);
    renderHybridBoardDetail(null);
    renderWorldMemory(null);
    document.querySelector("#simulation-board-summary").textContent = error.message;
    document.querySelector("#simulation-board-summary").className = "detail-card";
  }
}

async function refreshMissionControl() {
  const [blueprint, status, rooms, guards, datasets, audit, ingestStatus, ingestQueue, constitution] =
    await Promise.all([
      fetchJson("/api/blueprint"),
      fetchJson("/api/status"),
      fetchJson("/api/rooms"),
      fetchJson("/api/governance/guards"),
      fetchJson("/api/datasets"),
      fetchJson("/api/audit"),
      fetchJson("/api/ingest/status"),
      fetchJson("/api/ingest/queue"),
      fetchJson("/api/constitution"),
    ]);

  state.blueprint = blueprint;
  state.status = status;
  state.rooms = rooms;
  state.guards = guards;
  state.datasets = datasets;
  state.audit = audit;
  state.ingestStatus = ingestStatus;
  state.ingestQueue = ingestQueue;
  state.constitution = constitution;

  renderMission(blueprint);
  renderStatusCards(status);
  renderDatasets(datasets);
  renderRooms(rooms);
  renderGuards(guards);
  renderAudit(audit);
  renderDialogueCorpus(state.dialogueCorpus);
  renderConstitution(constitution);
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
  populateSimulationRoomFilter(rooms);
  await refreshAssetBrowser();
  await refreshMemoryExplorer();
  await refreshSimulationProjection({ preserveSelection: true });
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

async function inspectIngestQueueJob(jobId) {
  const feedback = document.querySelector("#ingest-feedback");
  const job = state.ingestQueue.find((item) => String(item.id) === String(jobId));
  state.ingestQueueSelectionId = jobId;
  syncIngestQueueSelection();
  if (!job?.room_id) {
    return;
  }

  feedback.textContent = `Loading history for queue job ${jobId}...`;
  try {
    const history = await fetchJson(
      `/api/ingest/queue/${jobId}/history?room_id=${encodeURIComponent(job.room_id)}`,
    );
    state.ingestQueueHistory = history;
    renderIngestQueueDetail(history.job);
    feedback.textContent = `Loaded ${history.history_event_count} queue history events for job ${jobId}.`;
  } catch (error) {
    state.ingestQueueHistory = null;
    const root = document.querySelector("#ingest-queue-detail");
    root.className = "detail-card";
    root.textContent = error.message;
    feedback.textContent = error.message;
  }
}

function collectIngestPayload(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function collectDialogueCorpusPayload(form) {
  const payload = {
    source_path: form.source_path.value.trim(),
  };
  const ownerName = form.owner_name.value.trim();
  if (ownerName) {
    payload.owner_name = ownerName;
  }
  return payload;
}

async function analyzeDialogueCorpus(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const submitButton = form.querySelector("button[type='submit']");
  const feedback = document.querySelector("#dialogue-corpus-feedback");
  const payload = collectDialogueCorpusPayload(form);

  submitButton.disabled = true;
  feedback.textContent = "Analyzing dialogue corpus...";

  try {
    const result = await fetchJson("/api/dialogue-corpus/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.dialogueCorpus = result;
    renderDialogueCorpus(result);
    feedback.textContent = `Dialogue corpus ready: ${result.thread_count} threads and ${result.message_count} messages.`;
  } catch (error) {
    state.dialogueCorpus = null;
    renderDialogueCorpus(null);
    feedback.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
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
    await inspectIngestQueueJob(result.job.id);
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
    await inspectIngestQueueJob(result.job.id);
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
    await inspectIngestQueueJob(job.id);
  } catch (error) {
    feedback.textContent = error.message;
  }
}

function bindEvents() {
  document.querySelector("#ingest-form").addEventListener("submit", submitIngestForm);
  document.querySelector("#ingest-preview-button").addEventListener("click", previewIngestForm);
  document.querySelector("#ingest-queue-button").addEventListener("click", queueIngestForm);
  document.querySelector("#dialogue-corpus-form").addEventListener("submit", analyzeDialogueCorpus);
  document.querySelector("#asset-refresh").addEventListener("click", refreshAssetBrowser);
  document.querySelector("#asset-room-filter").addEventListener("change", refreshAssetBrowser);
  document.querySelector("#asset-dataset-filter").addEventListener("change", refreshAssetBrowser);
  document.querySelector("#simulation-refresh").addEventListener("click", () =>
    refreshSimulationProjection({ preserveSelection: true }),
  );
  document.querySelector("#simulation-room-filter").addEventListener("change", (event) => {
    state.simulation.selectedRoomId = event.currentTarget.value;
    refreshSimulationProjection({ preserveSelection: false });
  });
  document.querySelector("#simulation-board-shell").addEventListener("click", (event) => {
    const cell = event.target.closest("[data-hybrid-row-id][data-hybrid-column-id]");
    if (!cell) {
      return;
    }
    loadHybridBoardSquareDetail(cell.dataset.hybridRowId, cell.dataset.hybridColumnId);
  });
  document.querySelector("#ingest-queue-jobs").addEventListener("click", (event) => {
    const button = event.target.closest("[data-queue-job-id]");
    if (!button || button.disabled) {
      return;
    }
    const { queueAction, queueJobId } = button.dataset;
    if (queueAction === "inspect") {
      inspectIngestQueueJob(queueJobId);
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
  document.querySelector("#asset-table").addEventListener("change", (event) => {
    const checkbox = event.target.closest("[data-compare-asset-id]");
    if (!checkbox) {
      return;
    }
    toggleArtComparisonSelection(checkbox.dataset.compareAssetId, checkbox.checked);
  });
  document.querySelector("#art-comparison").addEventListener("click", (event) => {
    const button = event.target.closest("[data-art-compare-action]");
    if (!button || button.disabled) {
      return;
    }
    if (button.dataset.artCompareAction === "run") {
      runArtComparison();
      return;
    }
    if (button.dataset.artCompareAction === "clear") {
      clearArtComparisonSelection();
    }
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
