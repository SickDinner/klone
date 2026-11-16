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
 void init();
})();
