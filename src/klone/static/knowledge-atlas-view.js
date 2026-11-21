/* KLONE Knowledge Atlas. Public, local read-only display. Never HTML-inject Wikipedia text. */
"use strict";
const root = document;
const byId = id => root.getElementById(id);
const setText = (id, text) => { byId(id).textContent = String(text); };
const fmt = n => new Intl.NumberFormat("fi-FI").format(Number(n) || 0);

async function getJson(url) {
  const response = await fetch(url, {credentials: "same-origin", cache: "no-store"});
  const data = await response.json();
  if (!response.ok) throw new Error(String(data.detail || "Haku epäonnistui"));
  return data;
}

function safeWikipediaLink(url) {
  try {
    const link = new URL(url);
    if (link.protocol !== "https:" || !/^[a-z]{2}\.wikipedia\.org$/.test(link.hostname)) return null;
    return link.href;
  } catch { return null; }
}

function appendText(container, tag, value, classname) {
  const node = root.createElement(tag);
  if (classname) node.className = classname;
  node.textContent = String(value);
  container.appendChild(node);
  return node;
}

function appendSource(container, item) {
  const panel = root.createElement("article");
  panel.className = "article";
  const heading = root.createElement("h3");
  const href = safeWikipediaLink(item.source_url);
  if (href) {
    const link = root.createElement("a");
    link.href = href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = String(item.title);
    heading.appendChild(link);
  } else {
    heading.textContent = String(item.title);
  }
  panel.appendChild(heading);
  appendText(panel, "p", item.text_excerpt_untrusted || "(Ei tiivistelmää)");
  const metadata = root.createElement("div");
  metadata.className = "tags";
  metadata.textContent = item.language.toUpperCase() + " · revisio " +
    item.revision_id + " · " + item.source_version_timestamp + " · " +
    item.content_kind + " · " + item.license_name +
    (item.truncated ? " · lyhennetty" : "");
  panel.appendChild(metadata);
  const history = safeWikipediaLink(item.attribution_url);
  if (history) {
    const a = root.createElement("a");
    a.href = history;
    a.rel = "noopener noreferrer";
    a.target = "_blank";
    a.textContent = "Tekijät ja muutoshistoria";
    panel.appendChild(a);
  }
  container.appendChild(panel);
}

async function init() {
  try {
    const [status, profiles] = await Promise.all([
      getJson("/api/knowledge-atlas/status"),
      getJson("/api/knowledge-atlas/members")
    ]);
    setText("articleCount", fmt(status.distinct_article_count));
    setText("storage",
      status.installed
        ? (status.storage_bytes_current / (1024 * 1024)).toFixed(1) + " Mt"
        : "ei alustettu");
    setText("roleCount", fmt(profiles.members.length));
    for (const p of profiles.members) {
      const option = root.createElement("option");
      option.value = String(p.member_id);
      option.textContent = "#" + p.member_id + " " + p.name + " — " + p.canonical_task;
      byId("member").appendChild(option);
    }
    setText("status", status.installed
      ? "Paikallinen tietopankki käytettävissä. Tulos ei tarkoita lähteen tieteellistä vahvistamista."
      : "Tietopankkia ei ole alustettu. Luo se Termuxissa komennolla: python -m klone.knowledge_atlas status");
  } catch (error) {
    setText("status", "Tilan lataaminen epäonnistui: " + error.message);
  }
}

byId("searchForm").addEventListener("submit", async event => {
  event.preventDefault();
  const button = byId("searchButton");
  const area = byId("results");
  area.replaceChildren();
  button.disabled = true;
  setText("status", "Haetaan vain paikallisesta tietopankista…");
  try {
    const params = new URLSearchParams({q: byId("question").value.trim(), limit:"12"});
    if (byId("member").value) params.set("member_id", byId("member").value);
    if (byId("language").value) params.set("language", byId("language").value);
    const result = await getJson("/api/knowledge-atlas/search?" + params.toString());
    setText("status", String(result.source_count) + " lähdettä paikallisesta tietopankista. Ei verkkolatausta eikä GPT-kutsua.");
    result.matched_sources.forEach(source => appendSource(area, source));
  } catch (error) {
    setText("status", "Haku epäonnistui: " + error.message);
  } finally {
    button.disabled = false;
  }
});

init();
