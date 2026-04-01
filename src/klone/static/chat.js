const chatState = {
  status: null,
  history: [],
  pending: false,
};

const CHAT_STORAGE_KEYS = {
  sourcePath: "klone.chat.sourcePath",
  ownerName: "klone.chat.ownerName",
  mode: "klone.chat.mode",
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

function formatTime(value) {
  return new Date(value).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function setFeedback(message) {
  document.querySelector("#chat-feedback").textContent = message;
}

function loadStoredValue(key) {
  try {
    return window.localStorage.getItem(key) || "";
  } catch (error) {
    console.error(error);
    return "";
  }
}

function saveStoredValue(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch (error) {
    console.error(error);
  }
}

function setModeBadge(message) {
  document.querySelector("#chat-mode-badge").textContent = message;
}

function renderStatus(status) {
  const root = document.querySelector("#chat-status");
  root.className = "detail-card";
  root.innerHTML = `
    <div class="meta">
      <span class="chip">channel: ${escapeHtml(status.channel_name)}</span>
      <span class="chip">OpenAI: ${status.openai_api_configured ? "configured" : "missing"}</span>
      <span class="chip">preferred_model: ${escapeHtml(status.preferred_model)}</span>
    </div>
    <ul class="detail-list">
      <li><strong>default_source_path</strong>: ${escapeHtml(status.default_source_path || "not set")}</li>
      ${status.notes.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
  `;

  const suggestionsRoot = document.querySelector("#chat-suggestions");
  suggestionsRoot.innerHTML = status.suggested_queries
    .map(
      (item) => `
        <button class="irc-suggestion" type="button" data-suggestion="${escapeHtml(item)}">
          ${escapeHtml(item)}
        </button>
      `,
    )
    .join("");

  const sourceInput = document.querySelector("#chat-source-path");
  const ownerInput = document.querySelector("#chat-owner-name");
  const modeSelect = document.querySelector("#chat-mode");

  sourceInput.value = loadStoredValue(CHAT_STORAGE_KEYS.sourcePath) || status.default_source_path || "";
  ownerInput.value = loadStoredValue(CHAT_STORAGE_KEYS.ownerName);
  modeSelect.value = loadStoredValue(CHAT_STORAGE_KEYS.mode) || "auto";

  setModeBadge(status.openai_api_configured ? "auto -> GPT-5.4 kaytettavissa" : "auto -> bounded local");
}

function renderLog() {
  const root = document.querySelector("#chat-log");
  if (!chatState.history.length) {
    root.innerHTML = `
      <article class="irc-line irc-line-system">
        <div class="irc-line-head">
          <span class="irc-speaker">system</span>
          <span>${formatTime(new Date().toISOString())}</span>
        </div>
        <div class="irc-content">Huone on valmis. Kirjoita kysymys tai paina Suggested Queries.</div>
      </article>
    `;
    return;
  }

  root.innerHTML = chatState.history
    .map((item) => {
      const cssClass =
        item.role === "user"
          ? "irc-line irc-line-user"
          : item.role === "assistant"
            ? "irc-line irc-line-assistant"
            : "irc-line irc-line-system";
      const metaChips = (item.meta || [])
        .map((value) => `<span class="irc-meta-chip">${escapeHtml(value)}</span>`)
        .join("");
      return `
        <article class="${cssClass}">
          <div class="irc-line-head">
            <span class="irc-speaker">${escapeHtml(item.speaker)}</span>
            <span>${escapeHtml(item.timestamp)}</span>
          </div>
          <div class="irc-content">${escapeHtml(item.content)}</div>
          ${metaChips ? `<div class="irc-line-meta">${metaChips}</div>` : ""}
        </article>
      `;
    })
    .join("");
  root.scrollTop = root.scrollHeight;
}

function appendLine({ role, speaker, content, meta = [] }) {
  chatState.history.push({
    role,
    speaker,
    content,
    meta,
    timestamp: formatTime(new Date().toISOString()),
  });
  renderLog();
}

function buildHistoryPayload() {
  return chatState.history
    .filter((item) => item.role === "user" || item.role === "assistant")
    .slice(-12)
    .map((item) => ({
      role: item.role,
      speaker: item.speaker,
      content: item.content,
    }));
}

function normalizeMessage(rawValue) {
  const text = rawValue.trim();
  if (!text) {
    return "";
  }
  if (text.toLowerCase() === "/clear") {
    chatState.history = [];
    renderLog();
    return "";
  }
  if (text.toLowerCase().startsWith("/klone ")) {
    return text.slice(7).trim();
  }
  return text;
}

async function submitChatMessage(rawValue) {
  if (chatState.pending) {
    return;
  }

  const input = document.querySelector("#chat-input");
  const sourcePath = document.querySelector("#chat-source-path").value.trim();
  const ownerName = document.querySelector("#chat-owner-name").value.trim();
  const mode = document.querySelector("#chat-mode").value;
  const message = normalizeMessage(rawValue);

  if (!message) {
    setFeedback("Keskustelu tyhjennettiin.");
    input.value = "";
    return;
  }
  if (!sourcePath) {
    setFeedback("Lahdepolku puuttuu. Tarkista Source Path ennen kysymysta.");
    return;
  }

  chatState.pending = true;
  document.querySelector("#chat-send").disabled = true;
  appendLine({ role: "user", speaker: "you", content: message });
  setFeedback("Klone rakentaa vastausta...");

  const payload = {
    source_path: sourcePath,
    message,
    mode,
    history: buildHistoryPayload(),
  };
  if (ownerName) {
    payload.owner_name = ownerName;
  }

  try {
    const response = await fetchJson("/api/clone-chat/respond", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const meta = [
      `mode: ${response.backend_mode}`,
      response.model ? `model: ${response.model}` : "model: local",
      `supported: ${response.answer.supported}`,
    ];
    appendLine({
      role: "assistant",
      speaker: response.reply.speaker,
      content: response.reply.content,
      meta,
    });

    response.system_notes.forEach((note) => {
      appendLine({ role: "system", speaker: "system", content: note });
    });

    if (response.backend_mode === "openai_gpt_5_4") {
      setModeBadge("auto -> GPT-5.4 live");
    } else if (response.backend_mode === "bounded_fallback") {
      setModeBadge("fallback -> bounded local");
    } else {
      setModeBadge("bounded local");
    }
    setFeedback(
      response.answer.supported
        ? `Vastaus valmis (${response.backend_mode}).`
        : "Kysymys meni nykyisen rajatun evidenssipaketin ulkopuolelle.",
    );
  } catch (error) {
    appendLine({ role: "system", speaker: "system", content: error.message });
    setFeedback(error.message);
  } finally {
    chatState.pending = false;
    document.querySelector("#chat-send").disabled = false;
    input.value = "";
    input.focus();
  }
}

async function sendChatMessage(event) {
  event.preventDefault();
  const input = document.querySelector("#chat-input");
  await submitChatMessage(input.value);
}

function bindEvents() {
  document.querySelector("#chat-form").addEventListener("submit", sendChatMessage);
  document.querySelector("#chat-clear").addEventListener("click", () => {
    chatState.history = [];
    renderLog();
    setFeedback("Keskusteluloki tyhjennettiin.");
  });
  const suggestionHandler = async (event) => {
    const button = event.target.closest("[data-suggestion]");
    if (!button) {
      return;
    }
    const suggestion = button.dataset.suggestion;
    document.querySelector("#chat-input").value = suggestion;
    await submitChatMessage(suggestion);
  };
  document.querySelector("#chat-suggestions").addEventListener("click", suggestionHandler);
  document.querySelector("#chat-quickstart").addEventListener("click", suggestionHandler);
  document.querySelector("#chat-mode").addEventListener("change", (event) => {
    const value = event.currentTarget.value;
    saveStoredValue(CHAT_STORAGE_KEYS.mode, value);
    if (value === "gpt-5.4") {
      setModeBadge("pyydetty -> GPT-5.4");
    } else if (value === "bounded") {
      setModeBadge("pakotettu -> bounded local");
    } else {
      setModeBadge(chatState.status?.openai_api_configured ? "auto -> GPT-5.4 kaytettavissa" : "auto -> bounded local");
    }
  });
  document.querySelector("#chat-source-path").addEventListener("change", (event) => {
    saveStoredValue(CHAT_STORAGE_KEYS.sourcePath, event.currentTarget.value.trim());
  });
  document.querySelector("#chat-owner-name").addEventListener("change", (event) => {
    saveStoredValue(CHAT_STORAGE_KEYS.ownerName, event.currentTarget.value.trim());
  });
}

async function main() {
  bindEvents();
  renderLog();
  try {
    const status = await fetchJson("/api/clone-chat/status");
    chatState.status = status;
    renderStatus(status);
    appendLine({
      role: "system",
      speaker: "system",
      content: status.openai_api_configured
        ? "Huone on valmis. GPT-5.4 on kaytettavissa auto-tilassa."
        : "Huone on valmis. OPENAI_API_KEY puuttuu, joten vastaukset tulevat nyt rajatusta paikallisesta tilasta.",
    });
    setFeedback("Huone on valmis kayttoon.");
    document.querySelector("#chat-input").focus();
  } catch (error) {
    setFeedback(error.message);
    appendLine({ role: "system", speaker: "system", content: error.message });
  }
}

main();
