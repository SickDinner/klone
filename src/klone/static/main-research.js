"use strict";
(function(){
 const id=x=>document.getElementById(x), node=(tag,text,cls)=>{
   const n=document.createElement(tag);
   if(text!==undefined)n.textContent=String(text);
   if(cls)n.className=cls;return n;
 };
 let latest=null;
 const write=(name,text)=>{id(name).textContent=String(text);};
 async function api(path){
   const r=await fetch(path,{cache:"no-store",credentials:"same-origin"});
   if(!r.ok){let d=await r.json().catch(()=>null);throw Error(d?.detail||"HTTP "+r.status);}
   return r.json();
 }
 async function init(){
   try{
     const h=await api("/health");
     if(h.service!=="klone-main-research-readonly"||h.read_only!==true)throw Error("Väärä palvelin.");
     write("main-status","Vain luku · päämuistin tietokanta: "+h.database_path);
   }catch(e){write("main-status","Päämuistiyhteys epäonnistui: "+e.message);}
 }
 id("main-form").addEventListener("submit",async event=>{
   event.preventDefault();
   const q=id("main-query").value.trim(),ring=id("main-ring").value,limit=id("main-limit").value;
   if(q.length<3){write("main-result-status","Kysymys on liian lyhyt.");return;}
   id("main-run").disabled=true;id("main-export").disabled=true;
   latest=null;id("main-results").replaceChildren();
   write("main-result-status","Tutkitaan julkisia lähdemuistoja...");
   try{
     const path="/api/limbo-atlas/intelligence?q="+encodeURIComponent(q)+
      "&limit="+encodeURIComponent(limit)+(ring?"&ring="+encodeURIComponent(ring):"");
     const r=await api(path);latest=r;
     write("main-result-status","Päämuistin haku: "+r.matched_memory_count+
       " / "+r.public_research_memory_count+" julkista lähdeviitettä · "+
       r.comparisons.length+" vertailua · "+r.research_drafts.length+
       " tutkimusluonnosta. Mitään ei kirjoitettu muistiin.");
     const root=id("main-results");
     const summary=node("article",undefined,"atlas-packet");
     summary.append(node("h3","Muistivertailun yhteenveto"));
     summary.append(node("p",Object.entries(r.domain_counts||{}).map(
       ([k,n])=>k+": "+n).join(" · ")));
     summary.append(node("p","Jokainen julkaisuviite on vahvistamaton lähdehavainto. Tuloksia ei ole todettu oikeiksi."));
     root.append(summary);
     const hiddenDuplicatePairs=new Set();
     try{
       const batch=await api("/api/limbo-atlas/dossiers?q="+encodeURIComponent(q));
       for(const dupe of batch.duplicate_memory_pairs||[])
         hiddenDuplicatePairs.add(dupe.event_ids.join(":"));
       const count=node("article",undefined,"atlas-packet");
       count.append(node("h3","E9.1 · Eri julkaisut, ei päällekkäisiä muistiviitteitä"));
       count.append(node("p",batch.raw_memory_pair_count+
         " muistiparia → "+batch.candidate_count+" eri julkaisuparia ("+
         batch.duplicate_memory_pair_count+" päällekkäistä muistiparia)."));
       count.append(node("p","Tutkimusmetatietopareja "+
         batch.source_type_counts.research_metadata_pairs+
         " · uutis-/viitelähteen sisältäviä pareja "+
         batch.source_type_counts.mixed_news_or_reference_pairs));
       count.append(node("p","Uutisartikkeli ei ole riippumaton tutkimus.","atlas-stats"));
       root.append(count);
       write("main-e8-status","E9.1: "+batch.candidate_count+
         " eri julkaisuparia, "+batch.duplicate_memory_pair_count+
         " päällekkäistä muistiparia. Ei muistikirjoituksia.");
     }catch(err){
       root.append(node("p","E9.1-julkaisujen deduplikointia ei voitu varmistaa: "+err.message,"atlas-stats"));
     }

     for(const x of r.memories){
       const card=node("article",undefined,"atlas-memory-card");
       card.append(node("p","Muisti #"+x.event_id+" · "+x.domain+" · versio "+x.version,"eyebrow"));
       card.append(node("strong",x.title));
       card.append(node("p","Lähde "+x.source_id+" · agentti #"+x.courier_id));
       const a=node("a","Lue alkuperäistä julkaisuviitettä");a.href=x.source_url;
       a.target="_blank";a.rel="noopener noreferrer";card.append(a);
       root.append(card);
     }
     if(r.comparisons.length){
       const card=node("article",undefined,"atlas-packet");
       card.append(node("h3","Mahdolliset tutkimusvertailut"));
       for(const c of r.comparisons){
         const d=node("details");d.append(node("summary",c.kind==="potential_claim_tension"?
           "Mahdollinen väitejännite – ei vahvistettu":"Yhteinen tutkimusaihe"));
         d.append(node("p","Muistit #"+c.first_event_id+" ja #"+c.second_event_id+
             " · samankaltaisia sanoja: "+c.shared_terms.join(", ")));
         d.append(node("p",c.explanation));
         d.append(node("p","Riippumatonta näyttöä ei ole varmistettu.","atlas-stats"));
         card.append(d);
       }
       root.append(card);
     }
     if(r.council72_preview?.packets?.length){
       const card=node("article",undefined,"atlas-packet");
       card.append(node("h3","Neuvoston simuloidut tutkimusideat"));
       for(const p of r.council72_preview.packets){
         const d=node("details");
         d.append(node("summary","Rinki "+p.target_ring+" · "+p.target_ring_name+
           " · "+p.specialist_ideas.length+" agenttia"));
         for(const idea of p.specialist_ideas){
           const item=node("section",undefined,"atlas-specialist");
           item.append(node("b","#"+idea.member_id+" "+idea.name));
           item.append(node("p",idea.research_prompt));
           item.append(node("p","Vain simuloitu tutkimusehdotus.","atlas-stats"));
           d.append(item);
         }
         card.append(d);
       }
       root.append(card);
     }
     id("main-export").disabled=false;
   }catch(error){write("main-result-status","Tutkimushaku epäonnistui: "+error.message);}
   finally{id("main-run").disabled=false;}
 });
 id("main-export").addEventListener("click",()=>{
   if(!latest)return;
   const blob=new Blob([JSON.stringify(latest,null,2)],{type:"application/json"});
   const url=URL.createObjectURL(blob),a=document.createElement("a");
   a.href=url;a.download="KLONE-paamuisti-E6-tutkimus.json";a.click();
   setTimeout(()=>URL.revokeObjectURL(url),3000);
 });
 let latestE8=null;
 id("main-e8-form").addEventListener("submit",async event=>{
   event.preventDefault();
   const q=id("main-e8-query").value.trim();
   if(q.length<3){write("main-e8-status","Anna vähintään kolme merkkiä.");return;}
   id("main-e8-run").disabled=true;id("main-e8-export").disabled=true;
   id("main-e8-results").replaceChildren();latestE8=null;
   write("main-e8-status","Vertaillaan päämuistin julkisia tutkimusviitteitä...");
   try{
     const r=await api("/api/limbo-atlas/discovery?q="+encodeURIComponent(q)+"&limit=48");
     latestE8=r;
     write("main-e8-status",r.selected+" tutkimusviitettä · "+
       r.cross_discipline_candidates.length+" tieteidenvälistä tutkittavaa yhteyttä. Ei muistikirjoituksia.");
     const root=id("main-e8-results");
     const summary=node("article",undefined,"atlas-packet");
     summary.append(node("h3","Löytötutkan yhteenveto"));
     summary.append(node("p",Object.entries(r.discipline_coverage||{}).map(
       ([name,n])=>name+" "+n).join(" · ")));
     summary.append(node("p","Pisteet tarkoittavat tutkimisen tarvetta, eivät todennäköisyyttä tai tieteellistä varmistusta."));
     root.append(summary);
     const diagnostics=r.diagnostics||{};
     const scan=node("article",undefined,"atlas-packet");
     scan.append(node("h3","E8.1 · Tieteidenvälisen haun tarkistus"));
     scan.append(node("p","Haun alat: "+
       (diagnostics.query_selected_domains||[]).join(", ")+
       " · muita julkisia lähteitä tutkittu: "+
       (r.outside_domain_documents_examined||0)+
       " · löydettyjä siltalähteitä: "+(r.bridge_document_count||0)));
     if(diagnostics.why_no_pairs)
       scan.append(node("p","Miksi tuloksia on nolla: "+diagnostics.why_no_pairs));
     for(const suggestion of diagnostics.suggested_next_queries||[])
       scan.append(node("p","Seuraava tarkistettava haku: "+suggestion,"atlas-stats"));
     root.append(scan);
     for(const found of r.bridge_documents||[]){
       const item=node("article",undefined,"atlas-memory-card");
       item.append(node("p","MUUN ALAN LÄHDE · "+found.domain,"eyebrow"));
       item.append(node("strong",found.title));
       item.append(node("p","Muisti #"+found.event_id+" · vahvistamaton"));
       const a=node("a","Tarkista alkuperäinen julkaisu");
       a.href=found.source_url;a.target="_blank";a.rel="noopener noreferrer";
       item.append(a);root.append(item);
     }
     if(r.weak_single_term_leads?.length){
       const weak=node("article",undefined,"atlas-packet");
       weak.append(node("h3","Heikot tutkintavihjeet"));
       weak.append(node("p","Yksi yhteinen termi ei riitä väittämään yhteyttä."));
       for(const hint of r.weak_single_term_leads){
         weak.append(node("p","Muistit #"+hint.first_event_id+" ja #"+
             hint.second_event_id+" · "+hint.shared_terms.join(", ")));
       }
       root.append(weak);
     }
     for(const pair of r.cross_discipline_candidates){
       if(hiddenDuplicatePairs.has(pair.first_event_id+":"+pair.second_event_id))continue;
       const item=node("article",undefined,"atlas-memory-card");
       item.append(node("p",pair.domains.join(" × "),"eyebrow"));
       item.append(node("strong","Muisti #"+pair.first_event_id+" + #"+pair.second_event_id));
       item.append(node("p","Yhteisiä käsitteitä: "+pair.shared_terms.join(", ")));
       item.append(node("p","Molempien otsikoiden vahvistama sanastoyhteys: "+
          (pair.shared_title_concepts||[]).join(", "),"atlas-stats"));
       item.append(node("p","Laatuseula E8.3 · käsitteiden muodot normalisoitu, ei varmistettua tieteellistä yhteyttä.","atlas-stats"));
       item.append(node("p","Perustelu: "+(pair.justification||"Tutkittava sanastoyhtäläisyys"),"atlas-stats"));
       item.append(node("p","Prioriteetti "+pair.candidate_priority+
           " · erilliset kustantajaryhmät: "+
           (pair.different_publisher_groups?"kyllä":"ei")));
       item.append(node("p",pair.next_experiment));
       item.append(node("p","Riippumatonta tutkimusnäyttöä ei ole osoitettu.","atlas-stats"));
       const open=node("button","Avaa E9-lähdeparin tutkimuskortti");
       open.type="button";
       open.addEventListener("click",async()=>{
         open.disabled=true;open.textContent="Luetaan oikeat lähdeviitteet...";
         try{
           const dossier=await api("/api/limbo-atlas/dossier?q="+encodeURIComponent(q)+
             "&first_event_id="+pair.first_event_id+
             "&second_event_id="+pair.second_event_id);
           const panel=node("section",undefined,"atlas-packet");
           panel.append(node("h3","E9 · Kaksi oikeaa julkaisua ja tutkimisen velat"));
           for(const source of [dossier.source_a,dossier.source_b]){
             panel.append(node("strong",source.title));
             panel.append(node("p",source.domain+" · julkaisija "+source.publisher_group+
               " · muistiviite #"+source.event_id+" · versio "+source.version));
             panel.append(node("p",source.source_excerpt));
             const link=node("a","Lue alkuperäinen julkaisu");
             const u=new URL(source.source_url);
             if(u.protocol==="https:"&&!u.username&&!u.password){
               link.href=u.href;link.rel="noopener noreferrer";link.target="_blank";
               panel.append(link);
             }
             panel.append(node("p","Täystekstiä ja tutkimusasetelmaa ei ole vielä tarkistettu.","atlas-stats"));
           }
           const protocol=node("ul");
           Object.values(dossier.research_protocol).forEach(x=>protocol.append(node("li",x)));
           panel.append(node("h3","Kriittiset tarkistustehtävät"));
           panel.append(protocol);
           const councilButton=node("button","Avaa E10 · kaikki 72 neuvoston tehtävää");
           councilButton.type="button";
           councilButton.addEventListener("click",async()=>{
             councilButton.disabled=true;councilButton.textContent="Laaditaan neuvoston tutkimussuunnitelma...";
             try{
               const board=await api("/api/limbo-atlas/council-workbench?q="+
                 encodeURIComponent(q)+"&first_event_id="+pair.first_event_id+
                 "&second_event_id="+pair.second_event_id);
               const block=node("section",undefined,"atlas-packet");
               block.append(node("h3","E10 · 9 rinkiä × 8 tehtävää = 72"));
               block.append(node("p","Vain tehtävänjako: 0 suoritettua arviota, 0 ääntä, ei päätösvaltaa."));
               block.append(node("p","Evidenssivelka: "+board.research_evidence_debt.join(", ")));
               for(const ring of board.rings){
                 const details=node("details");
                 details.append(node("summary","Rinki "+ring.ring+" · "+ring.name));
                 const list=node("ul");
                 for(const seat of board.assigned_seats.filter(x=>x.ring===ring.ring)){
                   list.append(node("li",seat.member_name+" (#"+seat.member_id+
                     "): "+seat.review_task+" — kesken; ei tarkistettua näyttöä."));
                 }
                 details.append(list);block.append(details);
               }
               panel.append(block);councilButton.remove();
             }catch(err){councilButton.disabled=false;
               councilButton.textContent="Yritä E10-tehtäväjakoa uudelleen";
               panel.append(node("p","E10: "+err.message,"atlas-stats"));}
           });
           panel.append(councilButton);
           item.append(panel);
           open.remove();
         }catch(err){open.disabled=false;open.textContent="Yritä tutkimuskortin hakua uudelleen";
           item.append(node("p","E9-haku epäonnistui: "+err.message,"atlas-stats"));}
       });
       item.append(open);
       root.append(item);
     }
     const debt=node("article",undefined,"atlas-packet");
     debt.append(node("h3","Evidenssivelka · jatkotutkimusjono"));
     for(const task of r.attention_queue){
       const d=node("details");
       d.append(node("summary",task.domain+" → rinki "+task.preferred_ring+
         " · tutkimisen prioriteetti "+task.attention_priority));
       const ul=node("ul");
       task.epistemic_debt.forEach(x=>ul.append(node("li",x)));
       d.append(ul);debt.append(d);
     }
     root.append(debt);
     const critiques=node("article",undefined,"atlas-packet");
     critiques.append(node("h3","Kahdeksan kriittistä näkökulmaa"));
     for(const lens of r.adversarial_research_lenses){
       const d=node("details");d.append(node("summary",lens.id));
       d.append(node("p",lens.question));critiques.append(d);
     }
     root.append(critiques);
     id("main-e8-export").disabled=false;
   }catch(err){write("main-e8-status","Löytötutkan virhe: "+err.message);}
   finally{id("main-e8-run").disabled=false;}
 });
 id("main-e8-export").addEventListener("click",()=>{
   if(!latestE8)return;
   const blob=new Blob([JSON.stringify(latestE8,null,2)],{type:"application/json"});
   const url=URL.createObjectURL(blob),a=document.createElement("a");
   a.href=url;a.download="KLONE-paamuisti-E8-loytotutka.json";a.click();
   setTimeout(()=>URL.revokeObjectURL(url),3000);
 });
 void init();
})();
