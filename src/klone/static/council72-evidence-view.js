"use strict";
(async function(){
  const byId=id=>document.getElementById(id),node=(tag,text)=>{const el=document.createElement(tag);el.textContent=String(text??"Avoin");return el;};
  const own=(o,k)=>Object.hasOwn(o,k),hex=s=>typeof s==="string"&&/^[a-f0-9]{64}$/.test(s),id=s=>typeof s==="string"&&/^[A-Za-z0-9_.:-]{1,64}$/.test(s);
  const authority=["binding_authority","external_actions","permission_changes","deployment_approval","consciousness_claim"];
  const states={met_for_review:"Täyttyy tarkistettavaksi",not_met:"Ei täyty",unknown:"Avoin"};
  const classes={public:"Julkinen",restricted:"Rajattu",sealed:"Suljettu"};
  const stages={syntax:"Syntaksi",cognition:"Kognitiotestit",full:"Koko testisarja",local_deploy:"Local Deploy"};
  const logStates={passed:"Läpi",failed:"Epäonnistui",unknown:"Avoin",not_present:"Puuttuu",unavailable:"Ei käytettävissä"};
  const reasons={different_or_unknown_commit:"Commit on toinen tai avoin",different_or_unknown_environment:"Vaaditun ympäristön ajo puuttuu",v2_execution_context_required:"V2-ajokonteksti puuttuu",contract_binding_missing_changed_or_different:"Koesopimus puuttuu, vaihtui tai poikkeaa",incomplete_or_inconsistent_artifacts:"Aineistossa tai ajokontekstissa on puutteita",contradictory_evidence:"Manifesti ja loki ovat ristiriidassa",log_does_not_establish_status:"Lokista puuttuu tunnistettu tulos",consistent_reported_failure:"Manifesti, exit ja loki ilmoittavat virheen",pytest_pass_count_unavailable:"Pytestin läpäisseiden määrä puuttuu",reported_pass_count_below_locked_minimum:"Läpäisseiden määrä alittaa lukitun rajan",locally_consistent_stage_claim:"Manifesti, exit ja loki täsmäävät"};
  const domains=["hypervisor","permissions","audit","memory","cognition","research","genomics","media","simulation","android","ci","deployment"];
  const domainRing={hypervisor:7,permissions:7,audit:8,memory:3,cognition:2,research:6,genomics:8,media:1,simulation:6,android:4,ci:8,deployment:7};
  let model,current=null,readId=0;
  function table(head,rows){const wrap=node("div","");wrap.className="table-wrap";const t=document.createElement("table"),tr=document.createElement("tr");head.forEach(v=>tr.appendChild(node("th",v)));const thead=document.createElement("thead");thead.appendChild(tr);t.appendChild(thead);const body=document.createElement("tbody");rows.forEach(row=>{const r=document.createElement("tr");row.forEach(v=>r.appendChild(node("td",v)));body.appendChild(r);});t.appendChild(body);wrap.appendChild(t);return wrap;}
  function checkContract(c){
    const fail=()=>{throw Error("Virheellinen koesopimus");},s=c?.spec;
    if(!c||c.kind!=="klone-council72-contract"||c.schema_version!==1||authority.some(k=>c[k]!==false)||c.registration_time_authenticated!==false||c.provenance_authenticated!==false||!hex(c.contract_sha256)||
      c.acceptance_policy!=="all_selected_matching_runs_must_pass_each_criterion"||c.required_manifest_schema!==2||c.required_clean_checkout!==true||c.require_complete_capture!==true||c.require_matching_packet_and_logs!==true||c.require_collector_contract_binding!==true||c.max_failed!==0||
      !s||!id(s.contract_id)||typeof s.goal!=="string"||!s.goal.trim()||s.goal.length>2000||typeof s.target_commit!=="string"||!/^[a-f0-9]{40}$/.test(s.target_commit)||!own(classes,s.classification)||!Array.isArray(s.criteria)||s.criteria.length<1||s.criteria.length>16)fail();
    const ids=new Set(),claims=new Set();s.criteria.forEach(r=>{if(!r||!id(r.id)||!id(r.claim_key)||ids.has(r.id)||claims.has(r.claim_key)||!domains.includes(r.domain)||!own(stages,r.stage)||!["work","android"].includes(r.environment)||!Number.isInteger(r.min_passed)||r.min_passed<0||r.min_passed>1000000||r.stage==="syntax"&&r.min_passed!==0)fail();ids.add(r.id);claims.add(r.claim_key);});
  }
  function checkEvidence(d){
    checkContract(d.contract);const fail=()=>{throw Error("Virheellinen evidenssikatselmus");};
    if(d.kind!=="klone-council72-evidence"||d.schema_version!==1||authority.some(k=>d[k]!==false)||d.origin_authenticated!==false||d.test_execution_authenticated!==false||d.registration_time_authenticated!==false||d.history_rewritten!==false||d.log_commands_executed!==false||d.memory_write_enabled!==false||d.manual_review_required!==true||!hex(d.evidence_sha256)||!hex(d.contract_file_sha256)||
      !own(states,d.status)||d.classification!==(d.contract.spec.classification==="sealed"?"sealed":"restricted")||d.source_independence!=="all_imported_artifacts_share_one_unauthed_group"||!Array.isArray(d.runs)||d.runs.length<1||d.runs.length>8||!Array.isArray(d.criteria)||d.criteria.length!==d.contract.spec.criteria.length||!Array.isArray(d.session_step_proposals)||d.session_step_proposals.length!==1)fail();
    const names=new Set();d.runs.forEach(r=>{if(!r||typeof r.run_name!=="string"||!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,199}$/.test(r.run_name)||names.has(r.run_name)||!r.trust||r.trust.origin_authenticated!==false||r.trust.test_execution_authenticated!==false||r.deployment_approval!==false||!r.attestation||!r.github||!r.manifest||!r.packet)fail();names.add(r.run_name);});
    d.criteria.forEach((r,i)=>{if(!r||!r.criterion||["id","claim_key","domain","stage","environment","min_passed"].some(k=>r.criterion[k]!==d.contract.spec.criteria[i][k])||!own(states,r.status)||!Number.isInteger(r.matching_runs)||r.matching_runs<0||r.matching_runs>8||!Array.isArray(r.cases)||r.cases.length!==d.runs.length)fail();r.cases.forEach(c=>{if(!c||!names.has(c.run_name)||!own(states,c.status)||![true,false,null].includes(c.in_scope)||typeof c.reason!=="string"||c.reason.length>200)fail();});});
    const step=d.session_step_proposals[0];if(!Array.isArray(step.observations)||step.observations.length!==d.criteria.length||!Array.isArray(step.dispatches)||step.dispatches.length)fail();
    const obsIds=new Set();step.observations.forEach((o,i)=>{const c=d.criteria[i],courier=model.members.find(m=>m.id===o?.courier_id&&m.ring===1);
      if(!o||Object.keys(o).length!==9||!courier||courier.courier_for!==model.rings[domainRing[c.criterion.domain]-1].steward_id||!id(o.id)||obsIds.has(o.id)||o.claim_key!==c.criterion.claim_key||o.stance!==({met_for_review:"supports",not_met:"contradicts",unknown:"unknown"}[c.status])||o.source_group!=="local-artifact-claims"||o.classification!==d.classification||typeof o.summary!=="string"||o.summary.length>512||o.source_ref!=="contract:"+d.contract.contract_sha256+":criterion:"+c.criterion.id||!o.signals||Object.keys(o.signals).length!==7||Object.keys(o.signals).some(k=>!["evidence_quality","uncertainty","risk","novelty","reward","threat","social_feedback"].includes(k)||typeof o.signals[k]!=="number"||!Number.isFinite(o.signals[k])||o.signals[k]<0||o.signals[k]>1))fail();obsIds.add(o.id);});
  }
  function render(data){
    const evidence=data.kind==="klone-council72-evidence";if(evidence)checkEvidence(data);else checkContract(data);
    current=data;byId("save-report").disabled=false;byId("save-step").disabled=!evidence;
    const c=evidence?data.contract:data,s=c.spec,panel=byId("result");panel.replaceChildren();
    panel.appendChild(node("p",classes[evidence?data.classification:s.classification]+" · "+(evidence?states[data.status]:"Sopimus muodostettu"))).className="tag";
    panel.appendChild(node("h2",s.goal));panel.appendChild(node("p","Kohdecommit: "+s.target_commit));
    panel.appendChild(node("p","Sopimuksen SHA-256: "+c.contract_sha256)).className="muted";
    panel.appendChild(node("p","Selain tarkistaa rakenteen. Tiivisteen sitominen manifestiin on kerääjän ilmoitus; rekisteröinnin aikaa ja testin suoritusta ei ole riippumattomasti autentikoitu."));
    panel.appendChild(table(["Kriteeri","Osa-alue","Ympäristö","Vaihe","Vähintään läpi"],s.criteria.map(r=>[r.id,r.domain,r.environment,stages[r.stage],r.min_passed])));
    if(!evidence)return;
    panel.appendChild(node("h2","Kriteerit alkuperäisen aineiston perusteella"));
    data.criteria.forEach(r=>{const card=node("article","");card.className="task-card";card.appendChild(node("h3",r.criterion.id+" · "+states[r.status]));card.appendChild(node("p",r.matching_runs+" ajoa kohdecommitissa ja vaaditussa ympäristössä. Osa-alue on sopimuksen tehtäväluokka; koko osa-alueen kattavuutta siitä ei päätellä."));
      card.appendChild(table(["Ajo","Tulkinta","Tila / exit","Lokin tila","Syy"],r.cases.map(c=>[c.run_name,states[c.status],(logStates[c.declared_status]||"Avoin")+" / "+(c.declared_exit_code??"avoin"),logStates[c.log_reported_status]||"Avoin",reasons[c.reason]||("Selvitettävä: "+c.reason)])));panel.appendChild(card);});
    panel.appendChild(node("h2","Alkuperä, eheys ja CI erillisinä"));
    data.runs.forEach(r=>{const details=node("details","");details.appendChild(node("summary",r.run_name));details.appendChild(table(["Havainto","Raportin ilmoittama tulos"],[
      ["Manifestin SHA-256",r.manifest.sha256],["Paketti vastaa aineistoa",r.trust.packet_matches_source===true?"Täsmää":r.trust.packet_matches_source===false?"Ei täsmää":"Avoin"],
      ["Laatuluokka",({verified:"Paikallisesti eheä",incomplete:"Puutteellinen",contradictory:"Ristiriitainen",unexamined:"Tutkimatta"}[r.quality?.category]||"Avoin")],["Todistajan allekirjoitus",({not_provided:"Ei annettu",verified_signature:"Täsmää luotettuun avaimeen",packet_unavailable:"Paketti puuttuu",verification_unavailable:"Tarkistus ei käytettävissä",rejected:"Hylätty"}[r.attestation.state]||"Avoin")],
      ["GitHub CI -väite",({unavailable:"CI-tulos puuttuu",reported_success:"Ilmoitettu onnistuminen",reported_failure:"Ilmoitettu epäonnistuminen",unknown:"Avoin"}[r.github.state]||"Avoin")],["Testin suoritus autentikoitu","Ei"],["Käyttöönoton hyväksyntä","Ei"]]));panel.appendChild(details);});
    panel.appendChild(node("p","Havaintokierros sisältää "+data.criteria.length+" havaintoa yhdestä paikallisen aineiston lähderyhmästä. Eri nimet tai kopioidut ajot eivät tuo itsenäisiä lähteitä."));
    panel.appendChild(node("p","Evidenssikatselmuksen SHA-256: "+data.evidence_sha256)).className="muted";
  }
  function download(data,name){const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:"application/json"})),a=document.createElement("a");a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),0);}
  try{const response=await fetch(document.body.dataset.catalog);model=await response.json();if(model.kind!=="klone-council72-catalog"||model.members.length!==72)throw Error("Rooliluettelo puuttuu");byId("source-file").disabled=false;byId("status").textContent="Valmis lukemaan paikallisen JSONin.";}catch(e){byId("status").textContent=e.message;return;}
  byId("source-file").addEventListener("change",async()=>{const seq=++readId,file=byId("source-file").files?.[0];if(!file)return;try{if(file.size>2097152)throw Error("Enimmäiskoko on 2 MiB");const data=JSON.parse(await file.text());if(seq!==readId)return;render(data);byId("status").textContent="Luettu tässä selaimessa. Tarkista alkuperäiset aineistot Pythonissa.";}catch(e){byId("status").textContent="Raporttia ei hyväksytty: "+e.message;}});
  byId("save-report").addEventListener("click",()=>{if(current)download(current,"neuvosto72-evidenssi.json");});
  byId("save-step").addEventListener("click",()=>{if(current?.kind==="klone-council72-evidence")download(current.session_step_proposals[0],"neuvosto72-havaintokierros.json");});
})();
