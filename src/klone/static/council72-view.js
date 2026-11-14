"use strict";
(async function () {
  const byId = (id) => document.getElementById(id);
  const node = (tag, value) => { const n = document.createElement(tag); n.textContent = String(value ?? "Ei tietoa"); return n; };
  const status = (text) => { byId("status").textContent = text; };
  const voteNames = {endorse:"Puoltaa", oppose:"Vastustaa", defer:"Odota lisätietoa"};
  const decisionNames = {endorsed_for_review:"Perustajat puoltavat tarkistusta", insufficient_evidence:"Rinkien viitteitä puuttuu", contested:"Perustajilla on erimielisyys", pending:"Harkinta kesken"};
  const modNames = {dopamine:"Dopamiini", noradrenaline:"Noradrenaliini", acetylcholine:"Asetyylikoliini", serotonin:"Serotoniini", gaba:"GABA", glutamate:"Glutamaatti"};
  const api = document.body.dataset.api;
  let model, checkCatalog, selected, selectedRing = 1, current = null, currentSession = null, currentReview = null, currentBriefing = null, generation = 0;
  const domainNames={hypervisor:"Hypervisor",permissions:"Käyttöoikeudet",audit:"Auditointi",memory:"Muisti",cognition:"Kognitio",research:"Tutkimus",genomics:"Genomiikka",media:"Media",simulation:"Simulaatio",android:"Android / Termux",ci:"CI-testit",deployment:"Asennus"};
  const stateNames={unverified:"Varmentamaton",failed:"Epäonnistunut",pending:"Kesken",passed:"Läpäissyt",not_applicable:"Soveltuvuus arvioitava"};
  const sessionNames = {...decisionNames, contradictory_evidence:"Ristiriita vaatii selvityksen", insufficient_sources:"Lähderyhmiä puuttuu"};
  const queueNames = {pending_owner_review:"Odota omistajan tarkistusta",stale_requires_review:"Vanhentunut · tarkista uudelleen",blocked_private:"Yksityinen aineisto · estetty",blocked_policy:"Käyttöoikeus estää",blocked_contradictory_evidence:"Ristiriita estää",blocked_insufficient_sources:"Lähderyhmiä puuttuu",blocked_contested:"Perustaja vastustaa",blocked_pending:"Harkinta kesken",blocked_insufficient_evidence:"Viitteitä puuttuu"};
  const unitValue=v=>typeof v==="number"&&Number.isFinite(v)&&v>=0&&v<=1;
  const own=(obj,key)=>Object.hasOwn(obj,key);
  const hex=v=>typeof v==="string"&&/^[a-f0-9]{64}$/.test(v);
  const identifier=v=>typeof v==="string"&&/^[A-Za-z0-9_.:-]{1,64}$/.test(v);
  const classification=["public","restricted","sealed"];
  const classNames={public:"julkinen",restricted:"rajattu",sealed:"suljettu"};
  const stanceNames={supports:"puoltaa",contradicts:"vastakkainen väite",unknown:"avoin"};
  const channelNames={forum:"Foorumi",social:"Some",documentation:"Ohjeet",research:"Tutkimus"};
  const authorityKeys=["binding_authority","external_actions","permission_changes","deployment_approval","consciousness_claim"];
  function download(data,name){const blob=new Blob([JSON.stringify(data,null,2)],{type:"application/json"}),url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),0);}
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
        new Set(report.opinions.map(o=>o?.member_id)).size!==72||report.opinions.some(o=>!model.members.some(m=>m.id===o?.member_id)||!own(voteNames,o.vote)||typeof o.score!=="number"||!Number.isFinite(o.score)||o.score<0||o.score>1||
          !o.modulators||Object.keys(modNames).some(k=>!unit(o.modulators[k]))||!o.affect||["curiosity","concern","calm","social_openness"].some(k=>!unit(o.affect[k])))||
        !Array.isArray(report.founder_ballots)||report.founder_ballots.length!==8||new Set(report.founder_ballots.map(f=>f?.member_id)).size!==8||report.founder_ballots.some(f=>!model.founder_ids.includes(f?.member_id)||!own(voteNames,f.vote))||
        !Array.isArray(report.ring_reports)||report.ring_reports.length!==8||new Set(report.ring_reports.map(r=>r?.ring)).size!==8||report.ring_reports.some(r=>!Number.isInteger(r?.ring)||r.ring<1||r.ring>8||!Array.isArray(r.evidence_refs)||r.evidence_refs.length>8)||
        !report.decision||!own(decisionNames,report.decision.status)||authorities.some(k=>report[k]!==false||report.decision[k]!==false)||
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
  function validateSession(data){
    const bad=()=>{throw Error("Virheellinen tai puutteellinen neuvostoistunto");};
    if(!data||data.kind!=="klone-council72-session"||data.schema_version!==1||authorityKeys.some(k=>data[k]!==false)||
      data.provenance_authenticated!==false||!identifier(data.request?.session_id)||typeof data.request.goal!=="string"||data.request.goal.length>2000||
      !classification.includes(data.request.classification)||!Array.isArray(data.request.steps)||!Array.isArray(data.rounds)||data.rounds.length<1||data.rounds.length>8||
      data.request.steps.length!==data.rounds.length||!Array.isArray(data.outbox)||data.outbox.length>64||!data.member_state||Object.keys(data.member_state).length!==72||
      model.members.some(m=>!data.member_state[String(m.id)]||Object.keys(modNames).some(k=>!unitValue(data.member_state[String(m.id)][k]))))bad();
    let level=classification.indexOf(data.request.classification), previous="0".repeat(64);const ids=new Set();
    data.rounds.forEach((r,i)=>{
      const observations=data.request.steps[i]?.observations;
      if(!Array.isArray(observations)||observations.length<1||observations.length>32)bad();
      observations.forEach(o=>{
        if(!o||!identifier(o.id)||ids.has(o.id)||!model.members.some(m=>m.id===o.courier_id&&m.ring===1)||
          !identifier(o.source_group)||!identifier(o.claim_key)||!["supports","contradicts","unknown"].includes(o.stance)||
          typeof o.summary!=="string"||o.summary.length>512||typeof o.source_ref!=="string"||o.source_ref.length>256||!classification.includes(o.classification)||
          !o.signals||["evidence_quality","uncertainty","risk","novelty","reward","threat","social_feedback"].some(k=>!unitValue(o.signals[k]))||
          (o.supersedes!==null&&!ids.has(o.supersedes)))bad();
        ids.add(o.id);level=Math.max(level,classification.indexOf(o.classification));
      });
      if(!r||r.index!==i+1||r.previous_hash!==previous||!hex(r.event_hash)||!hex(r.state_sha256)||!hex(r.previous_state_sha256)||
        !own(sessionNames,r.review_status)||r.classification!==classification[level]||!unitValue(r.mean_state_delta)||
        !Array.isArray(r.conflicts)||r.conflicts.length>256||!Array.isArray(r.rings)||r.rings.length!==8||
        new Set(r.rings.map(x=>x?.ring)).size!==8||r.rings.some(x=>!Number.isInteger(x?.ring)||x.ring<1||x.ring>8||
          !Number.isInteger(x.claimed_source_groups)||x.claimed_source_groups<0||x.claimed_source_groups>256||
          !Number.isInteger(x.supporting_source_groups)||x.supporting_source_groups<0||x.supporting_source_groups>x.claimed_source_groups||
          x.authenticated_sources!==0||x.quorum_met!==(x.supporting_source_groups>=2)||!Array.isArray(x.unknown_observation_ids)||x.unknown_observation_ids.length>256)||
        !Array.isArray(r.founder_ballots)||r.founder_ballots.length!==8||r.founder_ballots.some(f=>!model.founder_ids.includes(f?.member_id)||!own(voteNames,f.vote))||
        r.permission_preview?.preview_only!==true||r.permission_preview.caller_authenticated!==false)bad();
      previous=r.event_hash;
    });
    if(data.classification!==classification[level]||data.trace_sha256!==previous)bad();
    data.outbox.forEach(q=>{
      const courier=model.members.find(m=>m.courier_for===q?.king_id);
      if(!q||!courier||q.courier_id!==courier.id||!Number.isInteger(q.round)||q.round<1||q.round>data.rounds.length||
        !own(queueNames,q.status)||typeof q.message!=="string"||q.message.length>2000||q.origin_event_hash!==data.rounds[q.round-1].event_hash||
        authorityKeys.some(k=>q[k]!==false)||q.delivery_enabled!==false||q.issuer_authenticated!==false||q.owner_review_required!==true||q.account!==null||q.destination!==null||
        (q.round!==data.rounds.length&&q.status!=="stale_requires_review")||
        (q.status==="pending_owner_review"&&(data.classification!=="public"||data.rounds.at(-1).review_status!=="endorsed_for_review"||data.rounds.at(-1).permission_preview.decision!=="allowed")))bad();
    });
  }
  function renderSessionRound(index){
    const data=currentSession,r=data.rounds[index],panel=byId("session-round-detail");panel.replaceChildren();
    document.querySelectorAll("#session-rounds button").forEach((b,i)=>{b.classList.toggle("active",i===index);b.setAttribute("aria-pressed",String(i===index));});
    panel.appendChild(node("h3","Kierros "+r.index+" · "+sessionNames[r.review_status]));
    panel.appendChild(node("p","Tilamuutos "+r.mean_state_delta+" · luokittelu "+classNames[r.classification]+" · Hypervisorin esikatselu: "+(r.permission_preview.decision==="allowed"?"ehdotus sallittu":"estetty")));
    panel.appendChild(table(["Rinki","Lähderyhmiä","Puoltavia ryhmiä / 2","Avoimia havaintoja"],r.rings.map(x=>[x.ring,x.claimed_source_groups,x.supporting_source_groups,x.unknown_observation_ids.length])));
    if(r.conflicts.length){panel.appendChild(node("h3","Nämä väitteet riitelevät"));panel.appendChild(table(["Väite","Ringit","Havainnot"],r.conflicts.map(c=>[c.claim_key,Array.isArray(c.rings)?c.rings.join(", "):"Ei tietoa",Array.isArray(c.observation_ids)?c.observation_ids.join(", "):"Ei tietoa"])));}
    panel.appendChild(node("h3","Kierroksen uudet havainnot"));
    data.request.steps[index].observations.forEach(o=>{const detail=node("details","");detail.appendChild(node("summary",o.id+" · "+stanceNames[o.stance]+" · "+o.source_group));
      const courier=model.members.find(m=>m.id===o.courier_id),king=model.members.find(m=>m.id===courier.courier_for);
      detail.appendChild(node("p",courier.name+" → "+king.name+" · "+classNames[o.classification]));detail.appendChild(node("p",o.summary));detail.appendChild(node("p","Lähdeviite: "+o.source_ref));
      if(o.supersedes)detail.appendChild(node("p","Korvaa väitteen "+o.supersedes+". Alkuperäinen säilyy aiemmassa kierroksessa."));panel.appendChild(detail);});
    panel.appendChild(table(["Perustaja","Kanta"],r.founder_ballots.map(f=>[model.members.find(m=>m.id===f.member_id).name,voteNames[f.vote]])));
  }
  function renderSession(data){
    validateSession(data);renderReport(data.latest_experiment);currentSession=data;
    byId("session-panel").hidden=false;byId("save-session").disabled=false;
    byId("session-summary").textContent=(data.request.source_kind==="synthetic_fixture"?"Synteettinen istunto":"Käyttäjän havaintoväitteet")+" · "+data.rounds.length+" kierrosta · "+data.active_observation_count+" aktiivista havaintoa · "+classNames[data.classification];
    byId("session-rounds").replaceChildren();data.rounds.forEach((r,i)=>{const b=node("button",r.index+" · "+sessionNames[r.review_status]);b.addEventListener("click",()=>renderSessionRound(i));byId("session-rounds").appendChild(b);});
    const outbox=byId("session-outbox");outbox.replaceChildren();
    if(!data.outbox.length)outbox.appendChild(node("p","Ei viestiluonnoksia."));
    data.outbox.forEach(q=>{const d=node("details","");d.appendChild(node("summary",model.members.find(m=>m.id===q.king_id).name+" → "+model.members.find(m=>m.id===q.courier_id).name+" · "+queueNames[q.status]));
      d.appendChild(node("p","Kierros "+q.round+" · "+(channelNames[q.channel]||"Kanava avoin")+" · vastaanottaja ja tili avoinna"));d.appendChild(node("p",q.message));d.appendChild(node("p","KLONE · tekoälyneuvoston tarkistamaton luonnos. Omistajan tarkistus tarvitaan."));outbox.appendChild(d);});
    byId("session-integrity").textContent="Istuntoketjun SHA-256: "+data.trace_sha256+". Selain tarkistaa rakenteen ja ketjuviitteet. Kryptografinen replay tehdään Pythonissa; alkuperää ei ole autentikoitu.";
    if(api)byId("session-input").value=JSON.stringify(data.request,null,2);
    renderSessionRound(data.rounds.length-1);clearReview();byId("run-review").disabled=!api;byId("run-briefing").disabled=!api;
  }
  function clearReview(){
    currentReview=null;byId("save-review").disabled=true;
    currentBriefing=null;byId("save-briefing").disabled=true;
    byId("run-briefing").disabled=!api||!currentSession;
    byId("briefing-result").replaceChildren(node("p","Avaa katselmuksen JSON tai muodosta uusi avoimesta istunnosta paikallisessa KLONEssa."));
    byId("review-result").replaceChildren(node("p","Muodosta kehitysjono avoimesta istunnosta tai avaa aiemmin tallennettu kehitysjonon JSON."));
  }
  function validateReview(data){
    const fail=()=>{throw Error("Virheellinen tai puutteellinen kehitysjono");},a=data?.source_analysis,p=data?.plan,o=data?.options;
    if(!data||data.kind!=="klone-council72-review"||data.schema_version!==1||authorityKeys.some(k=>data[k]!==false)||data.provenance_authenticated!==false||data.manual_review_required!==true||
      !hex(data.review_sha256)||data.session_trace_sha256!==data.session?.trace_sha256||data.catalog_sha256!==data.session?.catalog_sha256||data.classification!==data.session?.classification||
      !o||!Number.isInteger(o.budget_minutes)||o.budget_minutes<1||o.budget_minutes>480||!Number.isInteger(o.max_tasks)||o.max_tasks<1||o.max_tasks>32||!Number.isInteger(o.max_source_groups)||o.max_source_groups<1||o.max_source_groups>32||
      !o.domain_states||Object.keys(o.domain_states).length!==12||Object.keys(domainNames).some(k=>!own(stateNames,o.domain_states[k]))||
      !a||a.scope!=="final_active_evidence_with_original_incoming_state"||a.history_rewritten!==false||!own(sessionNames,a.baseline_review_status)||
      !Array.isArray(a.cases)||a.cases.length>o.max_source_groups||!Array.isArray(a.tested_source_groups)||!Array.isArray(a.omitted_source_groups)||
      a.tested_source_groups.length!==a.cases.length||a.tested_source_groups.length+a.omitted_source_groups.length!==a.active_source_groups||a.active_source_groups>256||
      [...a.tested_source_groups,...a.omitted_source_groups].some(v=>!identifier(v))||new Set([...a.tested_source_groups,...a.omitted_source_groups]).size!==a.active_source_groups||
      a.coverage_complete!==(a.omitted_source_groups.length===0)||!p||p.execution_enabled!==false||p.time_estimates_only!==true||p.domain_state_source!=="caller_declared_not_verified"||
      !Array.isArray(p.tasks)||p.tasks.length>320)fail();
    a.cases.forEach((c,i)=>{if(!c||c.removed_source_group!==a.tested_source_groups[i]||!own(sessionNames,c.review_status)||c.review_status_changed!==(c.review_status!==a.baseline_review_status)||authorityKeys.some(k=>c[k]!==false)||
      !Array.isArray(c.affected_rings)||c.affected_rings.some(r=>!Number.isInteger(r)||r<1||r>8)||!Array.isArray(c.missing_quorum_rings)||c.missing_quorum_rings.some(r=>!Number.isInteger(r)||r<1||r>8)||
      !Array.isArray(c.changed_founder_ids)||c.changed_founder_ids.some(id=>!model.founder_ids.includes(id))||!unitValue(c.mean_absolute_score_delta)||!Number.isInteger(c.changed_member_votes)||c.changed_member_votes<0||c.changed_member_votes>72||
      !Array.isArray(c.removed_observation_ids)||c.removed_observation_ids.length>256||c.removed_observation_ids.some(id=>!identifier(id)))fail();});
    if(a.status_sensitive_cases!==a.cases.filter(c=>c.review_status_changed).length)fail();
    const ids=new Set();let total=0,count=0;
    p.tasks.forEach(t=>{
      const r=t?.route,courier=model.members.find(m=>m.id===r?.courier_id),king=model.members.find(m=>m.id===r?.founder_id);
      if(!t||typeof t.id!=="string"||t.id.length>96||ids.has(t.id)||typeof t.title!=="string"||t.title.length>256||typeof t.done_check!=="string"||t.done_check.length>1024||
        !Number.isInteger(t.priority_score)||t.priority_score<0||t.priority_score>30||!Number.isInteger(t.estimated_minutes)||t.estimated_minutes<1||t.estimated_minutes>480||t.execution_enabled!==false||
        !["selected","deferred_budget","deferred_task_limit"].includes(t.allocation)||!courier||!king?.founder||courier.courier_for!==king.id||king.stewards_ring!==r.ring||
        r.founder_name!==king.name||r.courier_name!==courier.name||!Array.isArray(t.evidence_observation_ids)||t.evidence_observation_ids.length>256||t.evidence_observation_ids.some(id=>!identifier(id)))fail();
      ids.add(t.id);if(t.allocation==="selected"){total+=t.estimated_minutes;count++;}
    });
    if(total!==p.allocated_minutes||total>o.budget_minutes||count!==p.selected_count||count>o.max_tasks||p.deferred_count!==p.tasks.length-count||p.remaining_minutes!==o.budget_minutes-total)fail();
  }
  function renderReview(data){
    validateReview(data);renderSession(data.session);currentReview=data;byId("save-review").disabled=false;
    byId("review-budget").value=String(data.options.budget_minutes);byId("review-max-tasks").value=String(data.options.max_tasks);byId("review-max-sources").value=String(data.options.max_source_groups);
    document.querySelectorAll("#domain-states select").forEach(s=>{s.value=data.options.domain_states[s.dataset.domain];});
    const panel=byId("review-result"),a=data.source_analysis,p=data.plan;panel.replaceChildren();
    panel.appendChild(node("p",(data.session.request.source_kind==="synthetic_fixture"?"Synteettinen koe":"Ilmoitetut havaintoväitteet")+" · "+classNames[data.classification]+" · lähtökanta: "+sessionNames[a.baseline_review_status])).className="tag";
    panel.appendChild(node("h3",p.selected_count+" tehtävää · "+p.allocated_minutes+" / "+data.options.budget_minutes+" minuuttia"));
    panel.appendChild(node("p","Ajat ovat suunnitteluarvioita. Tehtäviä ei suoriteta. Osa-alueiden tilat ovat ilmoituksia; tarkistusten tulokset kerätään erikseen."));
    panel.appendChild(node("h3","Kestääkö kanta lähderyhmän poistamisen?"));
    panel.appendChild(node("p",a.cases.length+" / "+a.active_source_groups+" lähderyhmää tutkittu · "+a.status_sensitive_cases+" kokeessa tarkistustila muuttui. Koe säilyttää viimeisen kierroksen alkuperäisen alkutilan ja perustajien annetut äänet. Historia ei muutu."));
    if(!a.coverage_complete)panel.appendChild(node("p","OSITTAINEN KATTAVUUS · tutkimatta: "+a.omitted_source_groups.join(", "))).className="tag";
    panel.appendChild(table(["Poistettu ryhmä","Tarkistustila ilman ryhmää","Lähdekiintiö puuttuu ringeistä","Muuttuneet jäsenäänet / perustajat","Keskimääräinen piste-ero"],a.cases.map(c=>[c.removed_source_group,sessionNames[c.review_status],c.missing_quorum_rings.join(", ")||"Ei puutu",c.changed_member_votes+" / "+c.changed_founder_ids.length,c.mean_absolute_score_delta])));
    panel.appendChild(node("h3","Budjettiin valitut tehtävät"));
    function taskCard(t){const card=node("article","");card.className="task-card";card.appendChild(node("p",t.estimated_minutes+" min · paino "+t.priority_score+" · rinki "+t.route.ring+" · "+({selected:"valittu",deferred_budget:"ei mahdu aikabudjettiin",deferred_task_limit:"tehtäväraja täynnä"}[t.allocation]))).className="tag";card.appendChild(node("h3",t.title));card.appendChild(node("p",t.route.founder_name+" → "+t.route.courier_name+" · käsiteltävä tehtäväehdotus"));card.appendChild(node("p",t.done_check));
      if(t.check_target)card.appendChild(node("p","Tarkistuksen lähtökohta: "+t.check_target));
      if(t.check_target_kind==="unmapped")card.appendChild(node("p","Erillistä regressiotestiä ei ole vielä kartoitettu. Määritä ensin testattava rajapinta."));
      if(t.evidence_observation_ids.length)card.appendChild(node("p","Havainnot: "+t.evidence_observation_ids.join(", "))).className="muted";
      return card;}
    const picked=p.tasks.filter(t=>t.allocation==="selected");if(!picked.length)panel.appendChild(node("p","Yksikään kokonainen tehtävä ei mahdu tähän budjettiin."));picked.forEach(t=>panel.appendChild(taskCard(t)));
    const deferred=node("details","");deferred.appendChild(node("summary",p.deferred_count+" odottavaa tehtävää"));p.tasks.filter(t=>t.allocation!=="selected").forEach(t=>deferred.appendChild(taskCard(t)));panel.appendChild(deferred);
    panel.appendChild(node("p","Kehitysjonon SHA-256: "+data.review_sha256+". Selain tarkistaa rakenteen. Täysi toisto: python -m klone.council72_review --verify raportti.json. Tiiviste ei todenna lähteitä." )).className="muted";
  }
  const claimNames={contested:"Ristiriita",unexamined:"Avoin",reported_support:"Ilmoitettu puolto",reported_opposition:"Ilmoitettu vastustus",mixed_unknown:"Mukana avoimia väitteitä"};
  function validateBriefing(data){
    const fail=()=>{throw Error("Virheellinen perustajien katselmus");};
    if(!data||data.kind!=="klone-council72-briefing"||data.schema_version!==1||authorityKeys.some(k=>data[k]!==false)||data.execution_enabled!==false||data.provenance_authenticated!==false||data.manual_review_required!==true||!hex(data.briefing_sha256))fail();
    validateSession(data.review?.session);validateReview(data.review);
    const session=data.review.session,c=data.consolidation,all=session.request.steps.flatMap(s=>s.observations),ids=new Set(all.map(o=>o.id));
    if(data.review_sha256!==data.review.review_sha256||data.session_trace_sha256!==session.trace_sha256||data.classification!==session.classification||data.goal!==session.request.goal||
      !Array.isArray(data.founders)||data.founders.length!==8||!Array.isArray(data.domain_work_packets)||data.domain_work_packets.length!==12||
      !c||c.kind!=="referenced_claim_index_only"||c.memory_write_enabled!==false||c.originals_preserved_in_review!==true||c.history_observation_count!==session.observation_count||c.active_observation_count!==session.active_observation_count||!Array.isArray(c.claims)||c.claims.length>256||!Array.isArray(c.corrections)||c.corrections.length>256||
      !data.collective||!own(sessionNames,data.collective.review_status)||data.collective.common_goal_achieved!==null||!Array.isArray(data.collective.minority_founder_ids)||data.collective.minority_founder_ids.some(id=>!model.founder_ids.includes(id)))fail();
    function claims(rows){if(!Array.isArray(rows)||rows.length>256)fail();rows.forEach(row=>{if(!row||!Number.isInteger(row.ring)||row.ring<1||row.ring>8||!identifier(row.claim_key)||!own(claimNames,row.epistemic_status)||row.truth_verified!==false||row.classification!==data.classification)fail();["history_observation_ids","active_observation_ids","supports","contradicts","unknown"].forEach(k=>{if(!Array.isArray(row[k])||row[k].length>256||row[k].some(id=>!ids.has(id)))fail();});});}
    claims(c.claims);
    c.corrections.forEach(row=>{if(!row||!ids.has(row.superseded_id)||!ids.has(row.replacement_id)||!all.some(o=>o.id===row.replacement_id&&o.supersedes===row.superseded_id))fail();});
    function packet(p){const trusted=checkCatalog.domains.find(d=>d.domain===p?.domain);if(!trusted||p.execution_enabled!==false||p.test_execution_status!=="not_run_by_briefing"||p.expected_commit!==null||!own(stateNames,p.caller_declared_state)||
      p.commands_text!==trusted.commands_text||p.coverage!==trusted.coverage||JSON.stringify(p.related_files)!==JSON.stringify(trusted.related_files)||JSON.stringify(p.test_targets)!==JSON.stringify(trusted.test_targets))fail();}
    if(new Set(data.domain_work_packets.map(p=>p.domain)).size!==12)fail();data.domain_work_packets.forEach(packet);
    data.founders.forEach((f,i)=>{const ring=model.rings[i],king=model.members.find(m=>m.id===ring.steward_id),courier=model.members.find(m=>m.courier_for===king.id);
      if(!f||f.ring!==i+1||f.founder_id!==king.id||f.courier_id!==courier.id||f.founder_name!==king.name||f.courier_name!==courier.name||!own(voteNames,f.founder_vote)||!Array.isArray(f.members)||f.members.length!==8||!Array.isArray(f.vote_history)||f.vote_history.length!==session.rounds.length||!Array.isArray(f.domain_work_packets)||f.domain_work_packets.length>12||!Array.isArray(f.conflict_claim_keys)||!Array.isArray(f.unknown_observation_ids)||!Array.isArray(f.task_ids)||!Number.isInteger(f.allocated_minutes)||f.allocated_minutes<0||f.allocated_minutes>480)fail();
      f.members.forEach((m,j)=>{const original=model.members.find(r=>r.id===ring.member_ids[j]);if(!m||m.id!==original.id||m.name!==original.name||m.task!==original.task||!own(voteNames,m.vote)||!unitValue(m.score))fail();});
      f.vote_history.forEach((v,j)=>{if(!v||v.round!==j+1||!own(voteNames,v.vote)||!["simulated","explicit_input"].includes(v.origin)||!own(sessionNames,v.review_status)||v.event_hash!==session.rounds[j].event_hash)fail();});
      if(!f.affect||f.affect.scope!=="retained_state_from_profile_baseline"||Object.keys(modNames).some(k=>!unitValue(f.affect.baseline?.[k])||!unitValue(f.affect.current?.[k])||typeof f.affect.delta?.[k]!=="number"||!Number.isFinite(f.affect.delta[k])||Math.abs(f.affect.delta[k])>1))fail();
      f.domain_work_packets.forEach(packet);claims(f.claims);
    });
    if(data.next_step!==null){const s=data.next_step,t=data.review.plan.tasks.find(t=>t.id===s?.task?.id);if(!s||s.execution_enabled!==false||s.change_proposal!==null||!t||t.allocation!=="selected"||JSON.stringify(s.task)!==JSON.stringify(t)||!Array.isArray(s.checklist)||s.checklist.length>16||!Array.isArray(s.open_questions)||s.open_questions.length>16)fail();if(s.work_packet!==null)packet(s.work_packet);}
  }
  function commandCard(p){
    const trusted=checkCatalog.domains.find(d=>d.domain===p.domain),card=node("article","");card.className="task-card";
    card.appendChild(node("h3",domainNames[p.domain]+" · "+stateNames[p.caller_declared_state]));
    card.appendChild(node("p","Tarkistettavat tiedostot: "+trusted.related_files.join(", ")));
    if(trusted.coverage==="art_image_subset_only")card.appendChild(node("p","Rajattu kattavuus: Art Labin kuvamittarit ja kuvavertailun huonerajat."));
    if(trusted.commands_text){card.appendChild(node("p","Oletus: ~/klone-next ja sen .venv. Aseta KLONE_ROOT worktree-hakemistoon tarvittaessa. Komentoja ei ole ajettu tällä katselmuksella."));
      const details=node("details","");details.appendChild(node("summary","Täsmälliset testikomennot"));const copy=node("button","Kopioi vain komennot");copy.type="button";copy.addEventListener("click",async()=>{try{await navigator.clipboard.writeText(trusted.commands_text);status("Kopioitu vain komentolohko. Tarkista testiympäristö ennen ajoa.");}catch{status("Kopiointi ei onnistunut. Valitse alla oleva komentolohko käsin.");}});details.appendChild(copy);details.appendChild(node("pre",trusted.commands_text));card.appendChild(details);
    }else card.appendChild(node("p","Tarkista GitHubin workflow ja saman commitin CI-ajon tulokset. Paikallista pytest-ajoa ei lasketa GitHub CI -evidenssiksi."));
    return card;
  }
  function renderBriefing(data){
    validateBriefing(data);renderReview(data.review);currentBriefing=data;byId("save-briefing").disabled=false;
    const panel=byId("briefing-result"),s=data.next_step;panel.replaceChildren();
    panel.appendChild(node("p",classNames[data.classification]+" · "+sessionNames[data.collective.review_status]+" · "+data.consolidation.active_observation_count+" aktiivista / "+data.consolidation.history_observation_count+" historiallista havaintoa")).className="tag";
    panel.appendChild(node("h3",data.goal));
    panel.appendChild(node("p","Tässä ovat ilmoitetut väitteet ja laskennallinen yhteenveto. Alkuperää ei ole autentikoitu. Päämäärän toteutuminen on avoin; sen arviointi tarvitsee erillisen mittarin."));
    panel.appendChild(node("h3","Yksi pienin seuraava askel"));
    if(s){panel.appendChild(node("p",s.task.title+" · "+s.task.estimated_minutes+" min · "+s.task.route.founder_name+" → "+s.task.route.courier_name));panel.appendChild(node("p",s.task.done_check));
      const list=node("ol","");s.checklist.forEach(text=>list.appendChild(node("li",text)));panel.appendChild(list);panel.appendChild(node("p","Avoinna: "+s.open_questions.join(" ")));
      if(s.work_packet)panel.appendChild(commandCard(s.work_packet));else panel.appendChild(node("p","Tämä askel vaatii alkuperäisen lähdeaineiston tarkistuksen. Koodikorjaus ja testikomento ovat vielä avoinna."));
    }else panel.appendChild(node("p","Yksikään kokonainen tehtävä ei mahtunut valittuun budjettiin."));
    panel.appendChild(node("h3","Kahdeksan perustajan vastuut"));
    const grid=node("div","");grid.className="founder-briefings";
    data.founders.forEach(f=>{const d=node("details","");d.appendChild(node("summary",f.founder_name+" · "+f.ring_name+" · "+voteNames[f.founder_vote]));
      d.appendChild(node("p",f.responsibility+" · tehtävä: "+f.founder_task));d.appendChild(node("p",f.courier_name+" välittää · budjetista "+f.allocated_minutes+" min · "+f.task_ids.length+" tehtävää"));
      if(f.conflict_claim_keys.length)d.appendChild(node("p","RISTIRIITA · "+f.conflict_claim_keys.join(", "))).className="tag";
      if(f.unknown_observation_ids.length)d.appendChild(node("p","Avoimet havainnot: "+f.unknown_observation_ids.join(", ")));
      d.appendChild(table(["Väite","Aineiston kanta","Aktiiviset havainnot","Koko historia"],f.claims.map(c=>[c.claim_key,claimNames[c.epistemic_status],c.active_observation_ids.join(", "),c.history_observation_ids.join(", ")])));
      d.appendChild(node("h3","Simuloidun tilan muutos"));d.appendChild(table(["Säädin","Lähtö","Nykyinen","Muutos"],Object.entries(modNames).map(([k,label])=>[label,f.affect.baseline[k],f.affect.current[k],f.affect.delta[k]])));
      d.appendChild(node("p","Muutos vertaa viimeistä säilytettyä tilaa rooliprofiiliin. Arvot ovat laskennallisia analogioita." )).className="muted";
      d.appendChild(table(["Kierros","Perustajan kanta","Äänen alkuperä"],f.vote_history.map(v=>[v.round,voteNames[v.vote],v.origin==="explicit_input"?"Erikseen annettu":"Laskennallinen"])));
      const roles=node("details","");roles.appendChild(node("summary","Ringin kahdeksan tehtävää"));roles.appendChild(table(["Rooli","Tehtävä","Kanta","Signaalirinki"],f.members.map(m=>[m.name,m.task,voteNames[m.vote],m.signal_ring])));d.appendChild(roles);
      f.domain_work_packets.forEach(p=>d.appendChild(commandCard(p)));grid.appendChild(d);
    });panel.appendChild(grid);
    const memory=node("details","");memory.appendChild(node("summary","Muistin konsolidointiehdotus · "+data.consolidation.claims.length+" viitteistettyä väitettä"));memory.appendChild(node("p","Alkuperäiset tekstit säilyvät istunnossa. Muistiin ei kirjoiteta. Puolto on ilmoitettu kanta, ei varmennettu totuus."));memory.appendChild(table(["Korvattu havainto","Uusi havainto"],data.consolidation.corrections.map(c=>[c.superseded_id,c.replacement_id])));panel.appendChild(memory);
    panel.appendChild(node("p","Katselmuksen SHA-256: "+data.briefing_sha256+". Selain tarkistaa rakenteen ja komentoluettelon. Täysi toisto: python -m klone.council72_briefing --verify katselmus.json." )).className="muted";
  }
  async function request(path,payload){const response=await fetch(api+path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});if(!response.ok)throw Error("Paikallinen API hylkäsi pyynnön ("+response.status+"). Tarkista viitteet, kanta ja luokittelu.");return response.json();}
  try {
    const response=await fetch(document.body.dataset.catalog);if(!response.ok)throw Error("Rooliluetteloa ei löytynyt");model=await response.json();
    if(model.kind!=="klone-council72-catalog"||!Array.isArray(model.members)||model.members.length!==72||!Array.isArray(model.rings)||model.rings.length!==9)throw Error("Virheellinen rooliluettelo");
    const checkResponse=await fetch(document.body.dataset.catalog.replace("council72-catalog.json","council72-work-checks.json"));if(!checkResponse.ok)throw Error("Tarkistuskomentojen luettelo puuttuu");checkCatalog=await checkResponse.json();if(checkCatalog.kind!=="klone-council72-work-checks"||checkCatalog.schema_version!==1||!Array.isArray(checkCatalog.domains)||checkCatalog.domains.length!==12||Object.keys(domainNames).some(k=>!checkCatalog.domains.some(d=>d.domain===k)))throw Error("Virheellinen komentoluettelo");
    model.rings.forEach(r=>{const b=node("button",r.id+" · "+r.dante_label.split(" /")[0]);b.type="button";b.dataset.ring=r.id;b.addEventListener("click",()=>choose(r.member_ids[0]));byId("ring-tabs").appendChild(b);});
    map();choose(model.rings[8].member_ids[1]);status("72 roolia ladattu · ei koetta avattuna · ulkoiset toimet pois käytöstä");
    byId("proposal-input").value=JSON.stringify(demo(),null,2);
    model.founder_ids.forEach(id=>{const o=node("option",model.members.find(m=>m.id===id).name);o.value=String(id);byId("draft-king").appendChild(o);});
    byId("local-controls").hidden=!api;byId("session-controls").hidden=!api;byId("review-controls").hidden=!api;byId("briefing-controls").hidden=!api;
    Object.entries(domainNames).forEach(([key,name])=>{const label=node("label",name),select=document.createElement("select");select.dataset.domain=key;Object.entries(stateNames).forEach(([value,text])=>{const option=node("option",text);option.value=value;select.appendChild(option);});label.appendChild(select);byId("domain-states").appendChild(label);});
    const template=await fetch(byId("session-template").href);if(template.ok)byId("session-input").value=JSON.stringify(await template.json(),null,2);
  } catch(error){status("Rakennetta ei voitu ladata: "+error.message);return;}
  byId("report-file").addEventListener("change",async()=>{const read=++generation,file=byId("report-file").files?.[0];if(!file)return;
    try{if(file.size>2097152)throw Error("Raportin enimmäiskoko on 2 MiB");const data=JSON.parse(await file.text());if(read!==generation)return;
      if(data?.kind==="klone-council72-briefing"){renderBriefing(data);status("Kuninkaiden katselmus luettu paikallisesti. Täysi replay tehdään Pythonissa.");}
      else if(data?.kind==="klone-council72-review"){renderReview(data);status("Kehitysjono ja lähteiden poistokokeet luettu paikallisesti. Täysi replay tehdään Pythonissa.");}
      else if(data?.kind==="klone-council72-session"){renderSession(data);status("Istunto luettu paikallisesti · "+data.rounds.length+" kierrosta · mitään ei lähetetty.");}
      else{renderReport(data);currentSession=null;clearReview();byId("run-review").disabled=true;byId("session-panel").hidden=true;byId("save-session").disabled=true;status("Koe luettu paikallisesti. Raportin väitteet eivät anna julkaisuvaltuutta.");}
    }catch(e){status("Raporttia ei hyväksytty: "+e.message);}});
  byId("download-input").addEventListener("click",()=>{const blob=new Blob([JSON.stringify(demo(),null,2)],{type:"application/json"}),url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="council72-synteettinen-tehtava.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),0);});
  byId("simulate").addEventListener("click",async()=>{if(!api)return;const own=++generation;try{const result=await request("/simulate",JSON.parse(byId("proposal-input").value));if(own!==generation)return;renderReport(result);currentSession=null;clearReview();byId("run-review").disabled=true;byId("session-panel").hidden=true;byId("save-session").disabled=true;status("Paikallinen koe valmis. Ei ulkoisia toimia.");}catch(e){status(e.message);}});
  byId("run-review").addEventListener("click",async()=>{if(!api||!currentSession)return;const own=++generation;try{
    const domain_states=Object.fromEntries([...document.querySelectorAll("#domain-states select")].map(s=>[s.dataset.domain,s.value]));
    const result=await request("/review",{session:currentSession.request,domain_states,budget_minutes:Number(byId("review-budget").value),max_tasks:Number(byId("review-max-tasks").value),max_source_groups:Number(byId("review-max-sources").value)});
    if(own!==generation)return;renderReview(result);status("Lähteiden poistokokeet ja aikabudjetoitu kehitysjono valmiina. Tallenna tulos jatkoa varten.");
  }catch(e){status(e.message);}});
  byId("save-review").addEventListener("click",()=>{if(currentReview)download(currentReview,"council72-kehitysjono-"+currentReview.session.request.session_id+".json");});
  byId("run-briefing").addEventListener("click",async()=>{if(!api||!currentSession)return;const own=++generation;try{
    const domain_states=Object.fromEntries([...document.querySelectorAll("#domain-states select")].map(s=>[s.dataset.domain,s.value]));
    const result=await request("/briefing",{session:currentSession.request,domain_states,budget_minutes:Number(byId("review-budget").value),max_tasks:Number(byId("review-max-tasks").value),max_source_groups:Number(byId("review-max-sources").value)});
    if(own!==generation)return;renderBriefing(result);status("Kahdeksan perustajan katselmus ja seuraava askel muodostettu. Tallenna jatkoa varten.");
  }catch(e){status(e.message);}});
  byId("save-briefing").addEventListener("click",()=>{if(currentBriefing)download(currentBriefing,"council72-katselmus-"+currentBriefing.review.session.request.session_id+".json");});
  byId("save-session").addEventListener("click",()=>{if(currentSession)download(currentSession,"council72-istunto-"+currentSession.request.session_id+".json");});
  byId("run-session").addEventListener("click",async()=>{if(!api)return;const own=++generation;try{
    if(byId("session-input").value.length>2097152)throw Error("Istunnon tehtävä on liian suuri");
    const result=await request("/session",JSON.parse(byId("session-input").value));if(own!==generation)return;renderSession(result);status("Istunto laskettu. Tallenna raportti, jotta voit jatkaa myöhemmin.");
  }catch(e){status(e.message);}});
  byId("memory-observation").addEventListener("click",async()=>{if(!api)return;const own=++generation;try{
    if(byId("session-input").value.length>2097152)throw Error("Istunnon tehtävä on liian suuri");const input=JSON.parse(byId("session-input").value);
    if(!Array.isArray(input.steps)||input.steps.length>=8)throw Error("Istuntoon mahtuu enintään kahdeksan kierrosta");
    const result=await request("/memory-observation",{limit:50});if(own!==generation)return;
    if(input.steps.some(s=>s.observations?.some(o=>o.id===result.observation.id)))throw Error("Sama muistiotos on jo mukana. Sitä ei lisätty toistamiseen.");
    input.steps.push({observations:[result.observation],dispatches:[]});byId("session-input").value=JSON.stringify(input,null,2);
    status("Julkisen muistin otos lisätty lomakkeelle uutena avoimena havaintona. Luku kirjattiin auditointiin. Aja kierrokset erikseen.");
  }catch(e){status(e.message);}});
  byId("draft").addEventListener("click",async()=>{if(!api||!current){status("Avaa tai simuloi ensin koe.");return;}try{const king=Number(byId("draft-king").value),courier=model.members.find(m=>m.courier_for===king);
    if(currentSession){status("Muodosta istunnon viestit sen tehtävä-JSONin dispatches-kentässä. Istunnon lähde- ja ristiriitatarkistukset tarvitaan ensin.");return;}
    const result=await request("/draft",{proposal:current.modulated.proposal,king_id:king,courier_id:courier.id,channel:byId("draft-channel").value,message:byId("draft-message").value});byId("draft-result").textContent=JSON.stringify(result,null,2);status("Luonnos muodostettu. Vastaanottaja ja tili ovat vielä määrittelemättä. Mitään ei lähetetty.");}catch(e){status(e.message);}});
})();
