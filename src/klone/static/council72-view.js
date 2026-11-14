"use strict";
(async function () {
  const byId = (id) => document.getElementById(id);
  const node = (tag, value) => { const n = document.createElement(tag); n.textContent = String(value ?? "Ei tietoa"); return n; };
  const status = (text) => { byId("status").textContent = text; };
  const voteNames = {endorse:"Puoltaa", oppose:"Vastustaa", defer:"Odota lisätietoa"};
  const decisionNames = {endorsed_for_review:"Perustajat puoltavat tarkistusta", insufficient_evidence:"Rinkien viitteitä puuttuu", contested:"Perustajilla on erimielisyys", pending:"Harkinta kesken"};
  const modNames = {dopamine:"Dopamiini", noradrenaline:"Noradrenaliini", acetylcholine:"Asetyylikoliini", serotonin:"Serotoniini", gaba:"GABA", glutamate:"Glutamaatti"};
  const api = document.body.dataset.api;
  let model, selected, selectedRing = 1, current = null, generation = 0;
  function table(headers, rows) {
    const wrap = node("div", ""); wrap.className="table-wrap";
    const t = document.createElement("table"), head=document.createElement("tr");
    headers.forEach(h=>head.appendChild(node("th",h))); t.appendChild(head);
    rows.forEach(row=>{const tr=document.createElement("tr");row.forEach(v=>tr.appendChild(node("td",v)));t.appendChild(tr);});
    wrap.appendChild(t);return wrap;
  }
  function demo() {
    return {proposal_id:"synthetic-council72", source_kind:"synthetic_fixture", classification:"public",
      goal:"Synteettinen koe: yhdistä kahdeksan ringin havainnot toiminnallisen itsemallin tutkimussuunnitelmaksi.",
      signals:{evidence_quality:.95,uncertainty:.08,risk:.05,novelty:.6,reward:.8,threat:.04,social_feedback:.4},
      ring_evidence:Object.fromEntries(Array.from({length:8},(_,i)=>[String(i+1),["synthetic:ring:"+(i+1)]]))};
  }
  function choose(memberId) {
    selected=model.members.find(m=>m.id===memberId); selectedRing=selected.ring; renderRing();
    document.querySelectorAll(".seat").forEach(s=>s.classList.toggle("selected",Number(s.dataset.member)===memberId));
  }
  function renderRing() {
    const ring=model.rings.find(r=>r.id===selectedRing), founder=model.members.find(m=>m.id===ring.steward_id);
    byId("ring-number").textContent="RINKI "+ring.id+" / 9";
    byId("ring-title").textContent=ring.dante_label;
    byId("ring-domain").textContent=ring.domain;
    byId("ring-steward").textContent=founder?"Vastuukuninkaana "+founder.name:"Kahdeksan perustajaa · yhteinen synteesi";
    byId("members").replaceChildren();
    ring.member_ids.forEach(id=>{const m=model.members.find(x=>x.id===id), b=node("button",m.name);b.type="button";
      b.classList.toggle("active",id===selected.id);b.setAttribute("aria-pressed",String(id===selected.id));
      b.appendChild(node("small",m.task));b.addEventListener("click",()=>choose(id));byId("members").appendChild(b);});
    document.querySelectorAll("#ring-tabs button").forEach(b=>{b.classList.toggle("active",Number(b.dataset.ring)===ring.id);b.setAttribute("aria-pressed",String(Number(b.dataset.ring)===ring.id));});
    const panel=byId("member-detail");panel.replaceChildren();
    panel.appendChild(node("p",(selected.founder?"PERUSTAJA":"ERIKOISTUNUT JÄSEN")+" · GOETIA #"+selected.id)).className="tag";
    panel.appendChild(node("h3",selected.name));panel.appendChild(node("p",selected.task)).className="mission";
    panel.appendChild(node("p","Kirjallinen motiivi: "+selected.source_motif+". Tekniset painotukset ovat tämän mallin omia."));
    if(selected.courier_for){const king=model.members.find(m=>m.id===selected.courier_for);panel.appendChild(node("p","Limbon viestinviejä kuninkaalle "+king.name+". Vastaanottaa havaintoväitteitä ja valmistelee luonnoksia; ei julkaisuvaltuutta."));}
    if(selected.founder){const r=model.rings.find(r=>r.id===selected.stewards_ring), courier=model.members.find(m=>m.courier_for===selected.id);
      panel.appendChild(node("p","Oma rinki: "+r.id+" · "+r.domain+". Limbon viestinviejä: "+courier.name+"."));}
    const opinion=current?.modulated.opinions.find(o=>o.member_id===selected.id);
    const baseline=current?.baseline.opinions.find(o=>o.member_id===selected.id);
    const bars=node("div","");bars.className="bars";
    Object.entries(selected.baseline_modulators).forEach(([key,value])=>{
      const actual=opinion?.modulators?.[key]??value, div=node("div","");
      div.appendChild(node("div",modNames[key]+" · "+Number(actual).toFixed(2))).className="bar-label";
      const p=document.createElement("progress");p.max=1;p.value=Number(actual);p.setAttribute("aria-label",modNames[key]);div.appendChild(p);bars.appendChild(div);});
    panel.appendChild(bars);panel.appendChild(node("p",opinion?"Avaamasi kokeen laskennalliset arvot.":"Profiilin lähtöpainot. Ei biologisia pitoisuuksia.")).className="muted";
    if(opinion){panel.appendChild(table(["Ilman tunnepainotusta","Tunnepainotuksella"],[[voteNames[baseline.vote],voteNames[opinion.vote]],[baseline.score,opinion.score]]));
      panel.appendChild(node("p","Uteliaisuus "+opinion.affect.curiosity+" · huoli "+opinion.affect.concern+" · rauhallisuus "+opinion.affect.calm));}
  }
  function map() {
    const svg=byId("council-map"), ns="http://www.w3.org/2000/svg";
    const s=(tag,attrs)=>{const e=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,String(v)));return e;};
    for(let slot=0;slot<8;slot++){const a=(slot*45-90)*Math.PI/180;svg.appendChild(s("line",{x1:500+70*Math.cos(a),y1:500+70*Math.sin(a),x2:500+455*Math.cos(a),y2:500+455*Math.sin(a),class:"spoke"}));}
    model.rings.forEach(r=>{const radius=455-(r.id-1)*45;svg.appendChild(s("circle",{cx:500,cy:500,r:radius,class:"orbit"}));
      r.member_ids.forEach((id,i)=>{const a=(i*45-90)*Math.PI/180,m=model.members.find(m=>m.id===id),g=s("g",{class:"seat"+(m.founder?" founder":""),role:"button",tabindex:0,"aria-label":r.id+". rinki · "+m.name+" · "+m.task,"data-member":id});
        const x=500+radius*Math.cos(a),y=500+radius*Math.sin(a);g.appendChild(s("circle",{cx:x,cy:y,r:18}));const text=s("text",{x,y});text.textContent=String(id);g.appendChild(text);
        g.addEventListener("click",()=>choose(id));g.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();choose(id);}});svg.appendChild(g);});});
    const center=s("text",{x:500,y:504,class:"center"});center.textContent="72";svg.appendChild(center);
    const label=s("text",{x:500,y:526,class:"center-label"});label.textContent="YHTEINEN SUUNTA";svg.appendChild(label);
  }
  function renderReport(data) {
    if(!data||data.kind!=="klone-council72-experiment"||data.schema_version!==1)throw Error("Tuntematon neuvostokoe");
    const authorities=["binding_authority","external_actions","permission_changes","deployment_approval","consciousness_claim"];
    const unit=v=>typeof v==="number"&&Number.isFinite(v)&&v>=0&&v<=1;
    if(data.modulated?.modulation!==true||data.baseline?.modulation!==false||authorities.some(k=>data[k]!==false)||typeof data.replay_matches!=="boolean"||
      !Number.isInteger(data.comparison?.changed_opinions)||data.comparison.changed_opinions<0||data.comparison.changed_opinions>72||
      typeof data.comparison.mean_score_delta!=="number"||!Number.isFinite(data.comparison.mean_score_delta))throw Error("Virheellinen kokeen yhteenveto");
    for(const report of [data.modulated,data.baseline]){
      if(!report||report.kind!=="klone-council72-round"||!Array.isArray(report.opinions)||report.opinions.length!==72||
        new Set(report.opinions.map(o=>o?.member_id)).size!==72||report.opinions.some(o=>!model.members.some(m=>m.id===o?.member_id)||!voteNames[o.vote]||typeof o.score!=="number"||!Number.isFinite(o.score)||o.score<0||o.score>1||
          !o.modulators||Object.keys(modNames).some(k=>!unit(o.modulators[k]))||!o.affect||["curiosity","concern","calm","social_openness"].some(k=>!unit(o.affect[k])))||
        !Array.isArray(report.founder_ballots)||report.founder_ballots.length!==8||new Set(report.founder_ballots.map(f=>f?.member_id)).size!==8||report.founder_ballots.some(f=>!model.founder_ids.includes(f?.member_id)||!voteNames[f.vote])||
        !Array.isArray(report.ring_reports)||report.ring_reports.length!==8||new Set(report.ring_reports.map(r=>r?.ring)).size!==8||report.ring_reports.some(r=>!Number.isInteger(r?.ring)||r.ring<1||r.ring>8||!Array.isArray(r.evidence_refs)||r.evidence_refs.length>8)||
        !report.decision||!decisionNames[report.decision.status]||authorities.some(k=>report[k]!==false||report.decision[k]!==false)||
        typeof report.proposal?.goal!=="string"||report.proposal.goal.length>2000||!Array.isArray(report.trace)||report.trace.length>128||!/^[a-f0-9]{64}$/.test(report.trace_sha256))throw Error("Virheellinen tai puutteellinen koeraportti");
    }
    current=data;const panel=byId("experiment-result"),r=data.modulated;panel.replaceChildren();
    panel.appendChild(node("h3",decisionNames[r.decision.status]||"Tuntematon kanta"));
    panel.appendChild(node("p",r.proposal?.source_kind==="synthetic_fixture"?"Synteettinen koe · ei KLONEn todellinen tilannekuva":"Käyttäjän antamat havaintoväitteet · alkuperää ei varmennettu")).className="tag";
    panel.appendChild(node("p",r.proposal?.goal));
    const cards=node("div","");cards.className="result-cards";
    [[data.comparison?.changed_opinions,"muuttunutta jäsenkantaa"],[data.comparison?.mean_score_delta,"keskimääräinen piste-ero"],[data.replay_matches?"Täsmää":"Ei vahvistettu","replay raportin mukaan"]].forEach(([v,l])=>{const c=node("div","");c.appendChild(node("strong",v));c.appendChild(node("span",l));cards.appendChild(c);});panel.appendChild(cards);
    panel.appendChild(node("p","Sisäinen kanta on tutkimustulos. Tietoisuutta, alkuperää tai toimintavaltuutta ei ole varmennettu. Ulkoiset julkaisut pysyvät pois käytöstä."));
    panel.appendChild(table(["Perustaja","Oma rinki","Viimeinen kanta","Kannan lähde"],r.founder_ballots.map(f=>[model.members.find(m=>m.id===f.member_id)?.name,f.stewards_ring,voteNames[f.vote],f.vote_source==="simulated"?"Laskennallinen":"Erillinen syöte"])));
    panel.appendChild(node("h3","Havainto kulkee Limbon kautta"));
    panel.appendChild(table(["Viestinviejä","Rinki","Vastuukuninkaalle","Viitteitä"],r.ring_reports.map(x=>[model.members.find(m=>m.id===x.courier_id)?.name,x.ring,model.members.find(m=>m.id===x.steward_id)?.name,x.evidence_refs?.length??"Ei tietoa"])));
    panel.appendChild(node("p","Päätöslokin SHA-256: "+r.trace_sha256)).className="muted";choose(selected.id);
  }
  async function request(path,payload){const response=await fetch(api+path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});if(!response.ok)throw Error("Paikallinen API hylkäsi pyynnön ("+response.status+"). Tarkista viitteet, kanta ja luokittelu.");return response.json();}
  try {
    const response=await fetch(document.body.dataset.catalog);if(!response.ok)throw Error("Rooliluetteloa ei löytynyt");model=await response.json();
    if(model.kind!=="klone-council72-catalog"||!Array.isArray(model.members)||model.members.length!==72||!Array.isArray(model.rings)||model.rings.length!==9)throw Error("Virheellinen rooliluettelo");
    model.rings.forEach(r=>{const b=node("button",r.id+" · "+r.dante_label.split(" /")[0]);b.type="button";b.dataset.ring=r.id;b.addEventListener("click",()=>choose(r.member_ids[0]));byId("ring-tabs").appendChild(b);});
    map();choose(model.rings[8].member_ids[1]);status("72 roolia ladattu · ei koetta avattuna · ulkoiset toimet pois käytöstä");
    byId("proposal-input").value=JSON.stringify(demo(),null,2);
    model.founder_ids.forEach(id=>{const o=node("option",model.members.find(m=>m.id===id).name);o.value=String(id);byId("draft-king").appendChild(o);});
    byId("local-controls").hidden=!api;
  } catch(error){status("Rakennetta ei voitu ladata: "+error.message);return;}
  byId("report-file").addEventListener("change",async()=>{const read=++generation,file=byId("report-file").files?.[0];if(!file)return;
    try{if(file.size>524288)throw Error("Raportin enimmäiskoko on 512 KiB");const data=JSON.parse(await file.text());if(read!==generation)return;renderReport(data);status("Koe luettu paikallisesti. Raportin väitteet eivät anna julkaisuvaltuutta.");}catch(e){status("Raporttia ei hyväksytty: "+e.message);}});
  byId("download-input").addEventListener("click",()=>{const blob=new Blob([JSON.stringify(demo(),null,2)],{type:"application/json"}),url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="council72-synteettinen-tehtava.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),0);});
  byId("simulate").addEventListener("click",async()=>{if(!api)return;const own=++generation;try{const result=await request("/simulate",JSON.parse(byId("proposal-input").value));if(own!==generation)return;renderReport(result);status("Paikallinen koe valmis. Ei ulkoisia toimia.");}catch(e){status(e.message);}});
  byId("draft").addEventListener("click",async()=>{if(!api||!current){status("Avaa tai simuloi ensin koe.");return;}try{const king=Number(byId("draft-king").value),courier=model.members.find(m=>m.courier_for===king);
    const result=await request("/draft",{proposal:current.modulated.proposal,king_id:king,courier_id:courier.id,channel:byId("draft-channel").value,message:byId("draft-message").value});byId("draft-result").textContent=JSON.stringify(result,null,2);status("Luonnos muodostettu. Vastaanottaja ja tili ovat vielä määrittelemättä. Mitään ei lähetetty.");}catch(e){status(e.message);}});
})();
