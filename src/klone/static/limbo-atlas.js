"use strict";
(function(){
  const state={catalog:null,records:[],report:null,busy:false,queue:null};
  const id=name=>document.getElementById(name);
  const el=(tag,text,cls)=>{
    const node=document.createElement(tag);
    if(text!==undefined)node.textContent=String(text);
    if(cls)node.className=cls;
    return node;
  };
  const say=(name,text)=>{id(name).textContent=String(text);};
  const canon={
    "arxiv-ai":"atlas-arxiv-ai",
    "arxiv-neuro":"neuro-arxiv",
    "nasa-latest":"nasa-news",
    "nasa-technology":"nasa-news"
  };
  const domainOf=sid=>state.catalog.sources.find(x=>x.id===sid);
  const byId=did=>state.catalog.domains.find(x=>x.id===did);
  async function api(url,opts){
    const response=await fetch(url,{cache:"no-store",credentials:"same-origin",...opts});
    if(!response.ok){
      const data=await response.json().catch(()=>null);
      throw new Error(typeof data?.detail==="string"?data.detail:"HTTP "+response.status);
    }
    return response.json();
  }
  function renderCatalog(){
    const root=id("atlas-agents"),sources=id("atlas-sources");
    const domainFilter=id("domain-filter"),sourceSelect=id("atlas-source-select");
    root.replaceChildren();sources.replaceChildren();sourceSelect.replaceChildren();
    for(const d of state.catalog.domains){
      if(!domainFilter.querySelector('option[value="'+d.id+'"]')){
        const option=el("option",d.name);option.value=d.id;domainFilter.append(option);
      }
      if(domainFilter.value && domainFilter.value!==d.id)continue;
      const card=el("article",undefined,"agent");
      card.append(el("p","LIMBO · "+d.slot+" / 8 · "+d.agent_name,"eyebrow"));
      card.append(el("h3",d.name));
      card.append(el("p",d.scope,"task"));
      card.append(el("p","Lähettäjä "+d.agent_name+" (#"+d.courier_id+") → perustaja #"+
        d.founder_id+"; ehdotettu rinki "+d.preferred_ring+" ("+d.ring_name+")","meta"));
      card.append(el("p","Kriittinen kysymys: "+d.research_question,"meta"));
      const mods=el("div",undefined,"modulators");
      for(const [k,v] of Object.entries(d.neuromodulators))mods.append(el("span",k+" "+Number(v).toFixed(2)));
      card.append(mods);
      root.append(card);
    }
    for(const s of state.catalog.sources){
      if(domainFilter.value && domainFilter.value!==s.domain)continue;
      const item=el("article",undefined,"atlas-source");
      item.append(el("p",s.kind.toUpperCase()+" · "+s.publisher,"eyebrow"));
      item.append(el("h3",s.description));
      item.append(el("p",(byId(s.domain)?.name||s.domain)+" · "+s.id));
      const a=el("a","Avaa alkuperäinen lähde");
      a.href=s.source_url;a.target="_blank";a.rel="noopener noreferrer";
      item.append(a);sources.append(item);
      const option=el("option",s.id+" · "+s.description);option.value=s.id;sourceSelect.append(option);
    }
  }
  function cleaned(raw){
    if(!raw||typeof raw!=="object")throw new Error("Havainto ei ole olio.");
    const sid=canon[raw.source_id]||raw.source_id,spec=domainOf(sid);
    if(!spec)throw new Error("Tuntematon lähde: "+sid);
    const domain=byId(spec.domain);
    if(!domain)throw new Error("Tuntematon tutkimusala.");
    const doc={
      source_id:sid,courier_id:domain.courier_id,
      url:String(raw.url||"").slice(0,256),
      title:String(raw.title||"").slice(0,240),
      summary:String(raw.summary||"").slice(0,360),
      published_at:raw.published_at?String(raw.published_at).slice(0,80):null
    };
    if(!doc.url.startsWith("https://")||!doc.title.trim()||!doc.summary.trim())
      throw new Error("Lähteellä pitää olla HTTPS-linkki, otsikko ja kuvaus.");
    return doc;
  }
  function refreshRecords(){
    const root=id("atlas-observations");root.replaceChildren();
    for(let i=0;i<state.records.length;i++){
      const o=state.records[i],s=domainOf(o.source_id);
      const card=el("article",undefined,"atlas-observation");
      card.append(el("b",o.title));
      card.append(el("p",(s?.domain||"tuntematon")+" · "+o.source_id));
      const link=el("a","Alkuperäinen tutkimus");link.href=o.url;link.target="_blank";link.rel="noopener noreferrer";card.append(link);
      const remove=el("button","Poista","secondary");
      remove.type="button";
      remove.addEventListener("click",()=>{
        state.records.splice(i,1);state.report=null;id("atlas-export").disabled=true;
        refreshRecords();id("atlas-packets").replaceChildren();
      });
      card.append(remove);root.append(card);
    }
    say("atlas-import-status",state.records.length+
        " / 48 havaintoa istunnossa. Lähteet ovat raportoituja väitteitä, eivät varmennettuja tosiasioita.");
  }
  function loadRecords(docs,fromOld){
    if(!Array.isArray(docs)||!docs.length||docs.length>48)
      throw new Error("Valitse aineisto, jossa on 1–48 havaintoa.");
    const all=docs.map(cleaned);
    if(new Set(all.map(x=>x.source_id+"|"+x.url)).size!==all.length)
      throw new Error("Sama artikkeli on aineistossa kahdesti.");
    state.records=all;state.report=null;id("atlas-export").disabled=true;
    refreshRecords();id("atlas-packets").replaceChildren();
    if(fromOld)say("atlas-import-status",all.length+
      " E1-tutkimusta tuotu. arXiv-lähteiden vastuuagentit reititetty Atlas E2:n erikoisaloille.");
  }
  id("domain-filter").addEventListener("change",renderCatalog);
  id("atlas-import").addEventListener("change",async event=>{
    const file=event.target.files?.[0];
    if(!file)return;
    try{
      if(file.size>4*1024*1024)throw new Error("Raportti on liian suuri (4 MiB).");
      const data=JSON.parse(await file.text());
      const docs=Array.isArray(data)?data:
        Array.isArray(data.observations)?data.observations:
        Array.isArray(data.receipts)?data.receipts:null;
      loadRecords(docs,!Array.isArray(data.observations));
    }catch(e){say("atlas-import-status","Tuonti epäonnistui: "+e.message);}
    event.target.value="";
  });
  id("atlas-reset").addEventListener("click",()=>{
    state.records=[];state.report=null;
    id("atlas-export").disabled=true;id("atlas-packets").replaceChildren();
    refreshRecords();say("atlas-plan-status","Istunto tyhjennetty.");
  });
  id("atlas-manual").addEventListener("submit",event=>{
    event.preventDefault();
    try{
      if(state.records.length>=48)throw new Error("48 havainnon raja saavutettu.");
      const s=domainOf(id("atlas-source-select").value);
      if(!s)throw new Error("Tuntematon lähde.");
      const d=cleaned({source_id:s.id,url:id("atlas-url").value.trim(),
        title:id("atlas-title").value.trim(),summary:id("atlas-summary").value.trim()});
      if(state.records.some(x=>x.source_id===d.source_id&&x.url===d.url))
        throw new Error("Sama artikkeli on jo lisätty.");
      state.records.push(d);refreshRecords();
      id("atlas-title").value="";id("atlas-summary").value="";id("atlas-url").value="";
      state.report=null;id("atlas-export").disabled=true;
    }catch(e){say("atlas-import-status","Lisäys epäonnistui: "+e.message);}
  });
  function renderPackets(report){
    const root=id("atlas-packets");root.replaceChildren();
    root.append(el("p","Lähteitä "+report.observations.length+
      " · julkaisijaryhmiä "+report.source_groups.length+
      " · luonnoksia "+report.packets.length+". Kaikki havaintoväitteet ovat edelleen epävarmoja.","atlas-stats"));
    for(const p of report.packets){
      const card=el("article",undefined,"atlas-packet");
      card.append(el("p","RINKI "+p.target_ring+" · PERUSTAJA #"+p.steward_id,"eyebrow"));
      card.append(el("h3",p.target_ring_name+" – "+p.specialist_domain));
      card.append(el("p","Lähtöhavainto: "+p.headline));
      card.append(el("p","Tutkimuskysymys: "+p.question));
      const details=el("div");
      details.append(el("h4","Ehdotettu tutkimusprosessi"));
      const list=el("ul");
      p.proposed_work.forEach(t=>list.append(el("li",t)));
      details.append(list);card.append(details);
      const specialist=el("details");
      specialist.append(el("summary","Ringin 8 erikoisagentin tutkimusideat"));
      for(const idea of p.specialist_ideas||[]){
        const row=el("section",undefined,"atlas-specialist");
        row.append(el("b","#"+idea.member_id+" "+idea.name+" · "+idea.specialism));
        row.append(el("p",idea.research_prompt));
        const affect=idea.simulated_affect||{};
        row.append(el("p","Simuloitu tila: uteliaisuus "+
          Number(affect.curiosity||0).toFixed(2)+", huoli "+
          Number(affect.concern||0).toFixed(2)+", rauhallisuus "+
          Number(affect.calm||0).toFixed(2)+
          " · vain tutkimusluonnos","atlas-stats"));
        specialist.append(row);
      }
      card.append(specialist);
      const badge=el("span","LUONNOS · EI JULKAISTU","atlas-pill");card.append(badge);
      card.append(el("span",p.publisher_groups.length+" julkaisijaryhmää · ei riippumatonta varmennusta","atlas-pill"));
      const links=el("details");
      links.append(el("summary","Lähdeviitteet ("+p.reference_urls.length+")"));
      for(const url of p.reference_urls){
        const a=el("a",url);a.href=url;a.target="_blank";a.rel="noopener noreferrer";
        links.append(a);
      }
      card.append(links);
      root.append(card);
    }
    if(!report.packets.length)root.append(el("p","Ei ehdotettuja tutkimuspaketteja."));
  }
  id("atlas-plan").addEventListener("click",async()=>{
    if(state.busy)return;
    if(!state.records.length){say("atlas-plan-status","Tuo ensin tutkimuksia.");return;}
    state.busy=true;id("atlas-plan").disabled=true;
    try{
      const which=id("atlas-ring").value;
      const report=await api("/api/limbo-atlas/plan",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({observations:state.records,
          target_ring:which?Number(which):null,
          research_question:id("atlas-question").value.trim()||null})
      });
      state.report=report;renderPackets(report);
      say("atlas-plan-status","Tutkimusluonnokset muodostettu. "+
        report.packets.length+" pakettia neuvostolle tarkistettavaksi. Ei ulkoisia toimia.");
      id("atlas-export").disabled=false;
    }catch(e){say("atlas-plan-status","Virhe: "+e.message);}
    finally{state.busy=false;id("atlas-plan").disabled=false;}
  });
  id("atlas-export").addEventListener("click",()=>{
    if(!state.report)return;
    const blob=new Blob([JSON.stringify(state.report,null,2)],{type:"application/json"});
    const url=URL.createObjectURL(blob),a=document.createElement("a");
    a.href=url;a.download="klone-atlas-council-review.json";
    a.click();setTimeout(()=>URL.revokeObjectURL(url),3000);
  });
  function showMemory(data){
    const root=id("atlas-memory-changes");
    root.replaceChildren();
    if(data.kind==="klone-atlas-memory-status"){
      if(!Array.isArray(data.domains)||!Array.isArray(data.recent_runs))
        throw new Error("Virheellinen tutkimusarkiston tilatiedosto.");
      say("atlas-memory-status","Atlas E3 -arkisto: "+data.runs+" tuontia, "+
        data.articles+" eri julkaisua, "+data.revisions+
        " havaintoversiota. Ei sisällä yksityisen Memory Coren tietoja.");
      for(const row of data.domains.slice(0,8)){
        const card=el("article",undefined,"atlas-memory-card");
        card.append(el("strong",String(row.domain)));
        card.append(el("p",String(row.unique_articles)+" eri julkaisuviitettä"));
        root.append(card);
      }
      return;
    }
    if(data.kind!=="klone-atlas-memory-delta"||!data.counts||!Array.isArray(data.changes))
      throw new Error("Tämä ei ole Atlas E3:n tilaraportti tai muutosraportti.");
    const counts=data.counts;
    say("atlas-memory-status","Atlas E3, erä #"+data.run_id+
      ": uusia "+counts.new+" · metadata muuttunut "+counts.metadata_changed+
      " · tunnettuja "+counts.unchanged+". Tutkimusväitteitä ei ole todennettu.");
    const visible=data.changes.filter(x=>x.status==="new"||x.status==="metadata_changed").slice(0,100);
    if(!visible.length){
      root.append(el("p","Ei uusia tai muuttuneita julkaisuja tässä tuontierässä."));
    }
    for(const entry of visible){
      const card=el("article",undefined,"atlas-memory-card");
      const type=entry.status==="new"?"UUSI JULKAISU":"METADATA MUUTTUNUT";
      card.append(el("p",type+" · "+entry.domain+" · versio "+entry.version,"eyebrow"));
      card.append(el("strong",entry.title));
      try{
        const link=new URL(entry.url);
        if(link.protocol==="https:"&&!link.username&&!link.password){
          const a=el("a","Lue lähteen sivu");
          a.href=link.href;a.target="_blank";a.rel="noopener noreferrer";
          card.append(a);
        }
      }catch(_ignored){}
      root.append(card);
    }
    if(data.changes.filter(x=>x.status==="new"||x.status==="metadata_changed").length>100){
      root.append(el("p","Ensimmäiset 100 muutosta näkyvät. Koko aineisto on tuotavassa JSONissa."));
    }
  }
  id("atlas-memory-import").addEventListener("change",async event=>{
    const file=event.target.files?.[0];
    if(!file)return;
    try{
      if(file.size>5*1024*1024)throw new Error("Muistiraportti on liian suuri.");
      const data=JSON.parse(await file.text());
      showMemory(data);
    }catch(error){
      say("atlas-memory-status","Muistitiedoston tuonti epäonnistui: "+error.message);
    }finally{event.target.value="";}
  });
  id("atlas-memory-clear").addEventListener("click",()=>{
    id("atlas-memory-changes").replaceChildren();
    say("atlas-memory-status","Muistivertailun näkymä tyhjennetty. SQLite-arkistoa ei muutettu.");
  });
  function displayQueue(q) {
    if (!q || q.kind!=="klone-atlas-e4-queue" || !Array.isArray(q.batches)
        || !Number.isInteger(q.article_count) || q.article_count<1
        || q.batches.length<1 || q.batches.length>3000)
      throw new Error("E4-jonotiedosto ei ole kelvollinen.");
    let sum=0;
    const seen=new Set();
    for (let i=0;i<q.batches.length;i++){
      const b=q.batches[i];
      if(b.number!==i+1||!Array.isArray(b.observations)||
         !Array.isArray(b.article_ids)||b.article_ids.length!==b.observations.length||
         b.size!==b.observations.length||b.size<1||b.size>48)
        throw new Error("E4-erä on virheellinen.");
      for(const n of b.article_ids){
        if(!Number.isInteger(n)||seen.has(n))throw new Error("E4 sisältää toistuvan julkaisu-ID:n.");
        seen.add(n);
      }
      for(const item of b.observations)cleaned(item);
      sum+=b.size;
    }
    if(sum!==q.article_count || q.batch_count!==q.batches.length)
      throw new Error("Jono ei kata kaikkia julkaisuviitteitä.");
    state.queue=q;
    const select=id("atlas-e4-batch"),root=id("atlas-e4-info");
    select.replaceChildren();root.replaceChildren();
    for(const b of q.batches){
      const option=el("option","Erä "+b.number+" / "+q.batch_count+" · "+b.size+" viitettä");
      option.value=String(b.number);
      select.append(option);
    }
    id("atlas-e4-load").disabled=false;
    say("atlas-e4-status","E4: "+q.article_count+" arkistoitua julkaisuviitettä, "+
      q.batch_count+" tutkimuserää. Tilanne: tutkimusjonon luonnos, ei vielä arvioitua näyttöä.");
    for(const b of q.batches){
      const card=el("article",undefined,"atlas-memory-card");
      card.append(el("strong","Erä "+b.number+" · "+b.size+" viitettä"));
      card.append(el("p",Object.entries(b.domains||{}).map(([d,n])=>d+" "+n).join(" · ")));
      root.append(card);
    }
  }
  id("atlas-e4-import").addEventListener("change",async event=>{
    const file=event.target.files?.[0];
    if(!file)return;
    try{
      if(file.size>8*1024*1024)throw new Error("E4-jono on liian suuri (8 MiB).");
      const q=JSON.parse(await file.text());
      displayQueue(q);
    }catch(error){say("atlas-e4-status","E4-tuonti epäonnistui: "+error.message);}
    finally{event.target.value="";}
  });
  id("atlas-e4-clear").addEventListener("click",()=>{
    state.queue=null;id("atlas-e4-batch").replaceChildren();
    id("atlas-e4-load").disabled=true;id("atlas-e4-info").replaceChildren();
    say("atlas-e4-status","E4-jono poistettu vain selainvälilehdestä.");
  });
  id("atlas-e4-load").addEventListener("click",()=>{
    if(!state.queue)return;
    const batch=state.queue.batches.find(b=>b.number===Number(id("atlas-e4-batch").value));
    if(!batch)return;
    try{
      loadRecords(batch.observations,false);
      say("atlas-plan-status","Erä "+batch.number+" / "+state.queue.batch_count+
          " ladattu. Valitse nyt vastaanottava rinki tai automaattireititys "+
          "ja muodosta tutkimusluonnokset.");
      id("atlas-research").scrollIntoView({behavior:"smooth",block:"start"});
    }catch(error){
      say("atlas-e4-status","Erän lataaminen epäonnistui: "+error.message);
    }
  });
  id("atlas-e5-search").addEventListener("click",async()=>{
    const q=id("atlas-e5-query").value.trim();
    if(q.length<2){say("atlas-e5-status","Kirjoita vähintään kaksi merkkiä.");return;}
    const out=id("atlas-e5-results");
    out.replaceChildren();
    id("atlas-e5-search").disabled=true;
    say("atlas-e5-status","Haetaan julkisesta KLONE research-room -muistista...");
    try{
      const result=await api("/api/limbo-atlas/memory/recall?q="+encodeURIComponent(q)+"&limit=20");
      say("atlas-e5-status","Memory Core: "+result.total_matches+
        " tutkimushavaintoa. Kaikki ovat edelleen vahvistamattomia julkisia lähdeväitteitä.");
      for(const item of result.results){
        const card=el("article",undefined,"atlas-memory-card");
        card.append(el("p","MUISTI #"+item.event_id+" · "+item.domain+
                        " · versio "+item.version,"eyebrow"));
        card.append(el("strong",item.title));
        card.append(el("p","Lähde: "+item.source_id+
                        " · Limbo-agentti #"+item.courier_id));
        const original=el("a","Alkuperäinen julkaisu");
        original.href=item.source_url;original.target="_blank";original.rel="noopener noreferrer";
        card.append(original);
        const memory=el("a","Avaa KLONEn lähteellinen muistokonteksti");
        memory.href=item.memory_context_url;memory.target="_blank";memory.rel="noopener noreferrer";
        card.append(memory);
        out.append(card);
      }
      if(!result.results.length)
        out.append(el("p","Ei osumia. Varmista ensin, että olet tuonut E3-tutkimukset Memory Coreen."));
    }catch(error){
      say("atlas-e5-status","Älymuistihaku epäonnistui: "+error.message+
          ". Varmista oikea KLONE-tietokanta ja uusin E5-palvelin.");
    }finally{id("atlas-e5-search").disabled=false;}
  });
  id("atlas-e5-query").addEventListener("keydown",event=>{
    if(event.key==="Enter"){event.preventDefault();id("atlas-e5-search").click();}
  });
  id("atlas-e5-clear").addEventListener("click",()=>{
    id("atlas-e5-results").replaceChildren();
    say("atlas-e5-status","Hakutulokset tyhjennetty. Memory Coren tietoja ei muutettu.");
  });
  let latestE6=null;
  id("atlas-e6-form").addEventListener("submit",async event=>{
    event.preventDefault();
    const q=id("atlas-e6-question").value.trim();
    const ring=id("atlas-e6-ring").value;
    const limit=id("atlas-e6-limit").value;
    if(q.length<3){say("atlas-e6-status","Anna vähintään kolme merkkiä.");return;}
    const results=id("atlas-e6-results");
    results.replaceChildren();
    latestE6=null;id("atlas-e6-export").disabled=true;
    id("atlas-e6-analyze").disabled=true;
    say("atlas-e6-status","Luetaan KLONEn julkista tutkimusmuistia, muodostetaan kysymykset...");
    try{
      const url="/api/limbo-atlas/intelligence?q="+encodeURIComponent(q)+
        "&limit="+encodeURIComponent(limit)+(ring?"&ring="+encodeURIComponent(ring):"");
      const report=await api(url);
      latestE6=report;
      const lead=el("article",undefined,"atlas-packet");
      lead.append(el("h3","Muistivertailu · "+report.matched_memory_count+
                         " / "+report.public_research_memory_count+" viitettä"));
      lead.append(el("p",Object.entries(report.domain_counts||{}).map(
        ([name,num])=>name+": "+num).join(" · ")));
      lead.append(el("p","Lähderyhmiä "+report.source_groups.length+
        " · tutkimuskysymyksiä "+report.research_drafts.length+
        " · mahdollisia verrattavia pareja "+report.comparisons.length));
      lead.append(el("p","Tietolähteen väitettä tai ristiriitaa ei ole varmennettu.","atlas-stats"));
      results.append(lead);
      for(const item of report.memories){
        const card=el("article",undefined,"atlas-memory-card");
        card.append(el("p","MUISTI #"+item.event_id+" · "+item.domain+
                    " · relevanssi "+item.relevance_score,"eyebrow"));
        card.append(el("strong",item.title));
        card.append(el("p","Versio "+item.version+" · lähteen tunniste "+item.source_id+
                    " · Limbo-agentti #"+item.courier_id));
        const a=el("a","Alkuperäinen julkaisu");
        a.href=item.source_url;a.target="_blank";a.rel="noopener noreferrer";
        card.append(a);results.append(card);
      }
      if(report.comparisons.length){
        const section=el("article",undefined,"atlas-packet");
        section.append(el("h3","Lähteiden vertailu ja mahdolliset ristiriidat"));
        for(const comparison of report.comparisons){
          const d=el("details");
          d.append(el("summary",comparison.kind==="potential_claim_tension"?
            "Mahdollinen sanallinen jännite – tarkista" : "Yhteinen aihe – vertaa menetelmiä"));
          d.append(el("p","Muistit #"+comparison.first_event_id+" ja #"+
            comparison.second_event_id+" · yhteisiä termejä: "+
            comparison.shared_terms.join(", ")));
          d.append(el("p",comparison.explanation));
          d.append(el("p","Eri julkaisijaryhmät: "+
            (comparison.different_publishers?"kyllä":"ei")+
            ". Väitteiden ristiriitaa ei ole varmennettu.","atlas-stats"));
          section.append(d);
        }
        results.append(section);
      }
      if(report.research_drafts.length){
        const section=el("article",undefined,"atlas-packet");
        section.append(el("h3","Neuvoston jatkotutkimusluonnokset"));
        for(const draft of report.research_drafts){
          const d=el("details");
          d.append(el("summary",draft.domain+" · Limbo-agentti #"+draft.agent_id+
                 " → rinki "+draft.specialist_ring));
          d.append(el("p","Tutkimuskysymys: "+draft.research_prompt));
          const ul=el("ul");
          draft.proposed_questions.forEach(v=>ul.append(el("li",v)));
          d.append(ul);
          d.append(el("p","Erikoisagenttien tunnukset: "+
            draft.specialist_member_ids.join(", ")+
            " · vasta alustava työluonnos","atlas-stats"));
          section.append(d);
        }
        results.append(section);
      }
      if(report.council72_preview?.packets?.length){
        const council=el("article",undefined,"atlas-packet");
        council.append(el("h3","Council72 · muistista johdetut erikoisagenttien ideat"));
        council.append(el("p",report.council72_preview.packets.length+
          " tutkimuspakettia. Kyseessä on simuloitu neuvostoistunto, ei toteutettu tutkimus."));
        for(const packet of report.council72_preview.packets){
          const details=el("details");
          details.append(el("summary","Rinki "+packet.target_ring+
            " · "+packet.target_ring_name+
            " · "+(packet.specialist_ideas||[]).length+" erikoisagenttia"));
          for(const idea of packet.specialist_ideas||[]){
            const item=el("section",undefined,"atlas-specialist");
            item.append(el("b","#"+idea.member_id+" "+idea.name));
            item.append(el("p",idea.research_prompt));
            item.append(el("p","Simuloitu ehdotus, ei näyttöä tai hyväksyttyä päätöstä.","atlas-stats"));
            details.append(item);
          }
          council.append(details);
        }
        results.append(council);
      }
      say("atlas-e6-status","E6-analyysi valmistui: "+report.matched_memory_count+
          " julkista muistiviitettä ja "+report.research_drafts.length+
          " tutkimusluonnosta. Ei muistikirjoituksia eikä uusia verkkohakuja.");
      id("atlas-e6-export").disabled=false;
    }catch(error){
      say("atlas-e6-status","Tutkimusanalyysi epäonnistui: "+error.message);
    }finally{id("atlas-e6-analyze").disabled=false;}
  });
  id("atlas-e6-export").addEventListener("click",()=>{
    if(!latestE6)return;
    const blob=new Blob([JSON.stringify(latestE6,null,2)],{type:"application/json"});
    const url=URL.createObjectURL(blob);
    const a=document.createElement("a");
    a.href=url;a.download="KLONE-E6-tutkimusanalyysi.json";a.click();
    setTimeout(()=>URL.revokeObjectURL(url),3000);
  });
  let latestE8=null;
  id("atlas-e7-import").addEventListener("change",async event=>{
    const file=event.target.files?.[0];
    if(!file)return;
    const root=id("atlas-e7-results");
    root.replaceChildren();
    try{
      if(file.size>5*1024*1024)throw Error("Yli 5 MiB:n päiväkirjaraportti.");
      const report=JSON.parse(await file.text());
      if(!report||report.kind!=="klone-e7-hypothesis-list"||
         !Array.isArray(report.hypotheses)||report.hypotheses.length>100)
        throw Error("Tuntematon E7-päiväkirjamuoto.");
      for(const entry of report.hypotheses){
        if(entry.kind!=="klone-e7-hypothesis-history"||
           !entry.hypothesis||!Array.isArray(entry.events))
          throw Error("Virheellinen hypoteesihistoria.");
        const card=el("article",undefined,"atlas-memory-card");
        card.append(el("p","#"+entry.hypothesis.hypothesis_id+" · "+
                       entry.hypothesis.domain+" · versio "+entry.revision,"eyebrow"));
        card.append(el("strong",entry.hypothesis.title));
        card.append(el("p","Kysymys: "+entry.hypothesis.question));
        card.append(el("p","Kumoava testi: "+entry.hypothesis.falsifier));
        card.append(el("p","Arvioinnin tila: "+entry.state+" · lähteitä: "+
                       entry.linked_sources+" · julkaisijaryhmiä: "+
                       entry.publisher_groups.length));
        if(entry.stale_source_event_ids?.length)
          card.append(el("p","Vanhentuneet lähdemuistien tunnukset: "+
                         entry.stale_source_event_ids.join(", "),"atlas-stats"));
        card.append(el("p","Evidenssivelka: vastanäytön haku "+
             (entry.evidence_debt?.find_counterevidence?"kesken":"ehdokas kirjattu")+
             " · riippumatonta toistoa ei ole varmistettu.","atlas-stats"));
        const history=el("details");
        history.append(el("summary","Avaa koko versio- ja lähdehistoria"));
        for(const step of entry.events.slice(0,100)){
          const item=el("p","Versio "+step.revision+" · "+step.event_type+
                   " · "+String(step.payload?.recorded_at||"aika tuntematon")+
                   " · tarkiste "+String(step.event_hash).slice(0,16),"atlas-stats");
          history.append(item);
          if(step.event_type==="source_link"){
            const src=step.payload.source;
            try{
              const url=new URL(String(src.source_url));
              if(url.protocol==="https:"&&!url.username&&!url.password){
                const a=el("a","Lähde #"+src.event_id+" · "+step.payload.stance);
                a.href=url.href;a.target="_blank";a.rel="noopener noreferrer";
                history.append(a);
              }
            }catch(_ignored){history.append(el("p","Virheellinen lähdeosoite ohitettu."));}
          }
        }
        card.append(history);root.append(card);
      }
      say("atlas-e7-status",report.hypotheses.length+
          " hypoteesia tuotu paikalliseen näkymään. Päiväkirjan tiedot säilyvät muuttumattomina.");
    }catch(err){say("atlas-e7-status","Päiväkirjan tuonti epäonnistui: "+err.message);}
    finally{event.target.value="";}
  });
  id("atlas-e7-clear").addEventListener("click",()=>{
    id("atlas-e7-results").replaceChildren();
    say("atlas-e7-status","Näyttö tyhjennetty. Tallennettua päiväkirjaa ei muutettu.");
  });
  id("atlas-e8-form").addEventListener("submit",async event=>{
    event.preventDefault();
    const question=id("atlas-e8-question").value.trim();
    if(question.length<3){say("atlas-e8-status","Syötä vähintään kolme merkkiä.");return;}
    id("atlas-e8-run").disabled=true;id("atlas-e8-export").disabled=true;
    id("atlas-e8-results").replaceChildren();latestE8=null;
    say("atlas-e8-status","Lasketaan julkisen muistin tieteidenvälisiä yhteyksiä...");
    try{
      const report=await api("/api/limbo-atlas/discovery?q="+encodeURIComponent(question)+
                             "&limit=48");
      latestE8=report;
      const root=id("atlas-e8-results");
      const header=el("article",undefined,"atlas-packet");
      header.append(el("h3","Löytötutka: "+report.selected+" valittua / "+
                        report.available_public_memories+" muistiviitettä"));
      header.append(el("p","Poikkitieteellisiä tutkittavia pareja "+
          report.cross_discipline_candidates.length+" · aiheita "+
          Object.keys(report.discipline_coverage).length));
      header.append(el("p","Tutkintaprioriteetit eivät ole luotettavuus- tai totuusprosentteja.",
          "atlas-stats"));
      root.append(header);
      const diagnostics=report.diagnostics||{};
      const scan=el("article",undefined,"atlas-packet");
      scan.append(el("h3","E8.1 · Haku muiden tieteenalojen lähteistä"));
      scan.append(el("p","Alkuperäisen haun tutkimusalat: "+
          (diagnostics.query_selected_domains||[]).join(", ")+
          " · muita julkisia lähteitä tutkittu: "+
          (report.outside_domain_documents_examined||0)+
          " · yhteyksiä muihin aloihin: "+
          (report.bridge_document_count||0)));
      if(diagnostics.why_no_pairs){
        scan.append(el("p","Ei vahvistettavaa yhteysehdokasta: "+
          diagnostics.why_no_pairs));
      }
      for(const suggestion of diagnostics.suggested_next_queries||[]){
        scan.append(el("p","Ehdotettu seuraava haku: "+suggestion,"atlas-stats"));
      }
      root.append(scan);
      for(const found of report.bridge_documents||[]){
        const item=el("article",undefined,"atlas-memory-card");
        item.append(el("p","MUISTA TUTKIMUSALOISTA · "+found.domain,"eyebrow"));
        item.append(el("strong",found.title));
        item.append(el("p","Lähdemuisti #"+found.event_id+
                        " · vahvistamaton lähdehavainto"));
        const anchor=el("a","Tarkista alkuperäinen julkaisu");
        anchor.href=found.source_url;anchor.target="_blank";
        anchor.rel="noopener noreferrer";item.append(anchor);
        root.append(item);
      }
      if(report.weak_single_term_leads?.length){
        const weak=el("article",undefined,"atlas-packet");
        weak.append(el("h3","Heikot, yhden termin perusteella löytyneet vihjeet"));
        weak.append(el("p","Nämä eivät täytä tutkimusyhteyden vähimmäisehtoja."));
        for(const lead of report.weak_single_term_leads){
          weak.append(el("p","Muistit #"+lead.first_event_id+" / #"+
              lead.second_event_id+" · termi: "+lead.shared_terms.join(", ")));
        }
        root.append(weak);
      }
      for(const pair of report.cross_discipline_candidates){
        const card=el("article",undefined,"atlas-memory-card");
        card.append(el("p","Tutkimusyhteys · "+pair.domains.join(" × "),"eyebrow"));
        card.append(el("strong","Muistit #"+pair.first_event_id+" ja #"+
                       pair.second_event_id));
        card.append(el("p","Yhteisiä käsitteitä: "+pair.shared_terms.join(", ")));
        card.append(el("p","Molempien otsikoiden yhteiset käsitteet: "+
                    (pair.shared_title_concepts||[]).join(", "),"atlas-stats"));
        card.append(el("p","Laatuseula E8.3 · yleistason sanat ja toistuvat taivutusmuodot karsittu.","atlas-stats"));
        card.append(el("p","Perustelu: "+(pair.justification||"Tutkittava sanastoyhtäläisyys"),"atlas-stats"));
        card.append(el("p","Tutkimisen prioriteetti "+pair.candidate_priority+
          " · erilliset julkaisijaryhmät: "+
          (pair.different_publisher_groups?"kyllä":"ei")));
        card.append(el("p",pair.next_experiment));
        card.append(el("p","Ei todennettua syy-yhteyttä tai riippumatonta vahvistusta.","atlas-stats"));
        root.append(card);
      }
      const debt=el("article",undefined,"atlas-packet");
      debt.append(el("h3","Evidenssivelka ja seuraavaksi tutkittavat alat"));
      for(const entry of report.attention_queue){
        const d=el("details");
        d.append(el("summary",entry.domain+" · rinki "+entry.preferred_ring+
          " · tutkimisen prioriteetti "+entry.attention_priority));
        const ul=el("ul");
        entry.epistemic_debt.forEach(item=>ul.append(el("li",item)));
        d.append(ul);debt.append(d);
      }
      root.append(debt);
      const critics=el("article",undefined,"atlas-packet");
      critics.append(el("h3","Kahdeksan kriittistä tutkimuslinssiä"));
      for(const lens of report.adversarial_research_lenses){
        const d=el("details");
        d.append(el("summary",lens.id));
        d.append(el("p",lens.question));critics.append(d);
      }
      root.append(critics);
      say("atlas-e8-status","Löytötutka valmis: "+report.cross_discipline_candidates.length+
         " tutkittavaa yhteyttä; ei muistikirjoituksia eikä ulkoisia hakuja.");
      id("atlas-e8-export").disabled=false;
    }catch(err){say("atlas-e8-status","Tutkan suoritus epäonnistui: "+err.message);}
    finally{id("atlas-e8-run").disabled=false;}
  });
  id("atlas-e8-export").addEventListener("click",()=>{
    if(!latestE8)return;
    const blob=new Blob([JSON.stringify(latestE8,null,2)],{type:"application/json"});
    const url=URL.createObjectURL(blob),a=document.createElement("a");
    a.href=url;a.download="KLONE-E8-loytotutka.json";a.click();
    setTimeout(()=>URL.revokeObjectURL(url),3000);
  });
  async function init(){
    try{
      state.catalog=await api("/api/limbo-atlas/catalog");
      renderCatalog();refreshRecords();
      say("atlas-status",state.catalog.domains.length+
        " Limbon nykyistä agenttia · "+state.catalog.sources.length+
        " hyväksyttyä julkista lähdettä. Haku vain Termuxista käskettäessä; ei automaattista julkaisua.");
    }catch(e){say("atlas-status","Uusi Atlas E2 -palvelin ei vielä vastaa: "+e.message+
      ". Päivitä lähdekoodi ja käynnistä KLONE 8031 uudelleen.");}
  }
  void init();
})();
