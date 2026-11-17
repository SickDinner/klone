"use strict";

const state = {agents: [], sources: [], docs: [], report: null, pending: false};
const $ = id => document.getElementById(id);

function add(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = String(text);
  if (className) el.className = className;
  return el;
}
function notice(id, message) {$(id).textContent = String(message);}
function source(id) {return state.sources.find(s => s.id === id);}
function agent(id) {return state.agents.find(a => a.id === id);}
function checkDocument(doc) {
  if (!source(doc.source_id)) throw new Error("Lähde-ID ei ole tunnettu.");
  const spec = source(doc.source_id);
  if (doc.courier_id !== spec.courier_id) throw new Error("Viestinviejä ei vastaa lähdettä.");
  const parsed = new URL(doc.url);
  if (parsed.protocol !== "https:" || !spec.allowed_article_hosts.includes(parsed.hostname.toLowerCase())
    || parsed.username || parsed.password || parsed.hash || (parsed.port && parsed.port !== "443"))
    throw new Error("Artikkelin URL ei ole lähteen hyväksymässä HTTPS-osoitteessa.");
  if (!String(doc.title || "").trim() || String(doc.title).length > 240
    || !String(doc.summary || "").trim() || String(doc.summary).length > 360)
    throw new Error("Otsikko ja yhteenveto ovat pakollisia.");
}
async function getJson(url, init) {
  const response = await fetch(url, {cache:"no-store", credentials:"same-origin", ...init});
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload && payload.detail;
    throw new Error(typeof detail === "string" ? detail : "HTTP " + response.status);
  }
  return response.json();
}
function renderAgents() {
  const root = $("agents");
  root.replaceChildren();
  state.agents.forEach(a => {
    const box = add("article", undefined, "agent");
    box.append(add("p", "LIMBO · " + a.slot + " / 8", "eyebrow"));
    box.append(add("h3", a.name));
    box.append(add("p", a.task, "task"));
    box.append(add("p", "Tutkimus: " + a.topic, "meta"));
    box.append(add("p", "Raportti → kuningas-ID " + a.founder_id
      + " · julkaisuoikeus: ei", "meta"));
    const mods = add("div", undefined, "modulators");
    Object.entries(a.baseline_modulators).forEach(([name,value]) => {
      mods.append(add("span", name + " " + Number(value).toFixed(2)));
    });
    box.append(mods);
    root.append(box);
  });
}
function renderSources() {
  const sourceSelect = $("source-id"), draftSelect = $("draft-source");
  sourceSelect.replaceChildren(); draftSelect.replaceChildren();
  state.sources.forEach(s => {
    const a = agent(s.courier_id);
    for (const sel of [sourceSelect, draftSelect]) {
      const option = add("option", (a ? a.name : s.courier_id) + " · " + s.id + " · " + s.topic);
      option.value = s.id; sel.append(option);
    }
  });
}
function renderDocs() {
  notice("observation-status", state.docs.length + " / 48 havaintoa. Tiedot ovat vain välilehden muistissa.");
  const root = $("observation-list");root.replaceChildren();
  state.docs.forEach((doc,i) => {
    const box = add("article", undefined, "item");
    box.append(add("strong", doc.title));
    box.append(add("small", doc.source_id + " · " + doc.url));
    const btn = add("button", "Poista", "secondary");
    btn.type="button";
    btn.addEventListener("click", () => {state.docs.splice(i,1);state.report=null;$("export-report").disabled=true;renderDocs();});
    box.append(btn);root.append(box);
  });
}
$("observation-form").addEventListener("submit", event => {
  event.preventDefault();
  try {
    if (state.docs.length >= 48) throw new Error("Korkeintaan 48 havaintoa / istunto.");
    const id = $("source-id").value, spec = source(id);
    if (!spec) throw new Error("Tuntematon lähde.");
    const doc = {
      source_id:id, courier_id:spec.courier_id,
      url:$("article-url").value.trim(),title:$("article-title").value.trim(),
      summary:$("article-summary").value.trim(),published_at:null
    };
    checkDocument(doc);
    if (state.docs.some(x => x.source_id === id && x.url === doc.url))
      throw new Error("Sama havainto on jo lisätty.");
    state.docs.push(doc);state.report=null;$("export-report").disabled=true;
    renderDocs();notice("report-status","Havainto lisätty. Laadi raportti.");
    $("article-title").value="";$("article-url").value="";$("article-summary").value="";
  } catch(error){notice("observation-status", error.message);}
});
$("clear-input").addEventListener("click", () => {
  state.docs=[];state.report=null;$("export-report").disabled=true;renderDocs();
  $("report").replaceChildren();notice("report-status","Havainnot tyhjennetty.");
});
$("import-file").addEventListener("change", async event => {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  try {
    if (file.size > 3*1024*1024) throw new Error("Liian suuri JSON-tiedosto.");
    const parsed=JSON.parse(await file.text());
    const docs=Array.isArray(parsed) ? parsed :
      Array.isArray(parsed.receipts) ? parsed.receipts :
      Array.isArray(parsed.documents) ? parsed.documents : null;
    if (!docs || !docs.length || docs.length>48) throw new Error("JSONissa on oltava 1–48 havaintoa.");
    const selected=docs.map(doc => ({
      source_id:doc.source_id,courier_id:doc.courier_id,url:doc.url,
      title:doc.title,summary:doc.summary,published_at:doc.published_at ?? null
    }));
    selected.forEach(checkDocument);
    if (new Set(selected.map(d => d.source_id+"|"+d.url)).size!==selected.length)
      throw new Error("Havaintojen URL:t eivät saa toistua.");
    state.docs=selected;state.report=null;$("export-report").disabled=true;
    $("report").replaceChildren();renderDocs();notice("report-status","Tuodut havainnot odottavat raporttia.");
  } catch(error){notice("observation-status","Tuonti epäonnistui: "+error.message);}
  finally{event.target.value="";}
});
function renderReport(report) {
  const root=$("report");root.replaceChildren();
  root.append(add("p","Lähdekatkelmat: "+report.receipts.length+" · tiiviste: "
    + report.input_sha256.slice(0,20)+"…"));
  root.append(add("p","Väitteiden tila: EI TOISENNETTU. Neuvoston virallinen evidenssiä tukevien lähteiden kiintiö ei täyty pelkällä RSS-syötteellä.","status"));
  (report.agent_reports || []).forEach(row => {
    const box=add("article",undefined,"brief");
    box.append(add("b",row.name+" → perustaja "+row.founder_id));
    box.append(add("p","Havaintoja "+row.observations+" · julkaisijaryhmiä "
      +row.distinct_publisher_groups+" · "+row.epistemic_status));
    const a=agent(row.courier_id);
    if(a)box.append(add("small","Kognitiivinen tilanne: "
      +String(a.attention_preview?.mode||"tuntematon")+" (laskennallinen analogia)"));
    root.append(box);
  });
  root.append(add("p","Neuvoston raportin tarkistussumma ja koko rakenteinen tulos tallennettavissa JSONina."));
}
$("preview").addEventListener("click", async () => {
  if (state.pending)return;
  if (!state.docs.length){notice("report-status","Lisää ensin havainto.");return;}
  state.pending=true;$("preview").disabled=true;
  try {
    const report=await getJson("/api/limbo-external/preview",{
      method:"POST", headers:{"Content-Type":"application/json"},
      body:JSON.stringify({goal:$("goal").value,documents:state.docs})
    });
    state.report=report;renderReport(report);$("export-report").disabled=false;
    notice("report-status","Raportti luotu. Ei julkaisuja eikä yksityisen muistin muutoksia.");
  }catch(error){notice("report-status","Raportin laatiminen epäonnistui: "+error.message);}
  finally{state.pending=false;$("preview").disabled=false;}
});
$("export-report").addEventListener("click", () => {
  if (!state.report)return;
  const blob=new Blob([JSON.stringify(state.report,null,2)],{type:"application/json"});
  const url=URL.createObjectURL(blob);
  const a=document.createElement("a");
  a.href=url;a.download="limbo-external-preview.json";a.click();
  setTimeout(()=>URL.revokeObjectURL(url),3000);
});
$("draft-form").addEventListener("submit",async event=>{
  event.preventDefault();
  const spec=source($("draft-source").value);
  if(!spec)return;
  try {
    const draft=await getJson("/api/limbo-external/question-draft",{
      method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({source_id:spec.id,courier_id:spec.courier_id,
        question:$("draft-question").value.trim()})
    });
    $("draft-output").textContent=draft.message;
    notice("draft-status","Vain luonnos · AI-rooli ilmoitettu · vaatii ihmisen tarkistuksen · mitään ei lähetetty.");
  }catch(error){notice("draft-status","Luonnos epäonnistui: "+error.message);}
});
async function init(){
  try{
    const [a,s]=await Promise.all([
      getJson("/api/limbo-external/agents"),
      getJson("/api/limbo-external/sources")
    ]);
    state.agents=a.agents;state.sources=s.sources;
    renderAgents();renderSources();renderDocs();
    notice("status","8 Limbo-agenttia ja "+state.sources.length
      +" ennalta hyväksyttyä lähdettä ladattu. Ulkoiset verkkohaut ja julkaisut eivät käynnisty automaattisesti.");
  }catch(error){notice("status","KLONE-rajapinta ei vastaa: "+error.message
    +". Varmista, että palvelin on päivitetty sisältämään limbo_external_api.");}
}
void init();
