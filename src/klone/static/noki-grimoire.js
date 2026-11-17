(function(){
  "use strict";
  const root=document.getElementById("grimoire");
  if(!root){return;}
  const queryEl=document.getElementById("grimoire-query");
  const categoryEl=document.getElementById("grimoire-category");
  const resultsEl=document.getElementById("grimoire-results");
  const detailEl=document.getElementById("grimoire-detail");
  const statusEl=document.getElementById("grimoire-status");
  const provenanceEl=document.getElementById("grimoire-provenance");
  const relatedEl=document.getElementById("grimoire-rift");
  let library=null,items=[],showCount=16;
  function node(tag,cls,txt){
    const el=document.createElement(tag);
    if(cls){el.className=cls;}
    if(txt!==undefined){el.textContent=String(txt);}
    return el;
  }
  function norm(value){
    return String(value||"").normalize("NFKD").replace(/[\u0300-\u036f]/g,"").toLocaleLowerCase("fi");
  }
  function itemText(x){
    return [x.title,x.name,x.summary,x.description,x.category,...(x.tags||[]),...(x.ranks||[])].filter(Boolean).join(" ");
  }
  function sourceById(id){return library.sources.find(s=>s.id===id);}
  function buildSource(id){
    const s=sourceById(id);
    if(!s){return node("span","error-label","Lähde-ID puuttuu: "+id);}
    const a=node("a","source-ref",s.title);
    a.href=s.url;a.target="_blank";a.rel="noopener noreferrer";a.title=s.kind+" – "+s.note;
    return a;
  }
  function showDetail(item){
    detailEl.replaceChildren();
    if(!item){detailEl.append(node("p","muted","Valitse tietue nähdäksesi lähteet."));return;}
    detailEl.append(node("p","eyebrow","LÄHDETIETO – EI TODISTE YLILUONNOLLISESTA"));
    detailEl.append(node("h3","",item.title||("Ars Goetia #"+item.order+": "+item.name)));
    detailEl.append(node("p","",item.summary||item.description));
    detailEl.append(node("p","meta-row","Luokka: "+(library.categories[item.category]||item.category)+(item.order?" · luettelon numero "+item.order:"")));
    if(item.ranks?.length){detailEl.append(node("p","meta-row","Kirjalliset arvonimet: "+item.ranks.join(", ")+". Nämä eivät ole vahvistettuja yliluonnollisia arvoja."));}
    const links=node("div","source-links");
    (item.sources||[]).forEach(id=>links.append(buildSource(id)));
    detailEl.append(links);
    detailEl.append(node("p","hint","Tarkista yksityiskohdat alkuperäisestä lähteestä. Nokin kiroilu on fiktiivistä kerrontaa."));
  }
  function matches(item,q,cat){
    if(cat&&item.category!==cat){return false;}
    if(!q){return true;}
    const hay=norm(itemText(item));
    return q.split(/\s+/).every(t=>hay.includes(t));
  }
  function rank(item,q){
    if(!q){return item.order?30+item.order:0;}
    const target=norm(item.title||item.name);
    if(target===q){return 0;}
    if(target.startsWith(q)){return 1;}
    if(target.includes(q)){return 2;}
    return 3;
  }
  function filtered(){
    if(!library){return [];}
    const q=norm(queryEl.value.trim()).slice(0,120),cat=categoryEl.value;
    return items.filter(item=>matches(item,q,cat)).sort((a,b)=>rank(a,q)-rank(b,q)||(a.order||0)-(b.order||0));
  }
  function render(){
    resultsEl.replaceChildren();
    if(!library){return;}
    const found=filtered();
    statusEl.textContent=found.length+" osumaa / "+items.length+" tietuetta · "+library.sources.length+" lähdettä";
    for(const item of found.slice(0,showCount)){
      const btn=node("button","grimoire-hit",(item.order?"#"+String(item.order).padStart(2,"0")+" · ":"")+(item.title||item.name));
      btn.type="button";btn.title=library.categories[item.category]||item.category;
      btn.addEventListener("click",function(){showDetail(item);});
      resultsEl.append(btn);
    }
    if(!found.length){resultsEl.append(node("p","muted","Ei osumia. Kokeile muuta hakusanaa tai luokkaa."));}
    if(found.length>showCount){
      const more=node("button","secondary","Näytä lisää ("+(found.length-showCount)+")");
      more.addEventListener("click",function(){showCount+=20;render();});
      resultsEl.append(more);
    }
  }
  function resetPagination(){showCount=16;render();}
  queryEl.addEventListener("input",resetPagination);
  categoryEl.addEventListener("change",resetPagination);
  document.getElementById("grimoire-reset").addEventListener("click",function(){queryEl.value="";categoryEl.value="";resetPagination();showDetail(null);});
  function findOne(text){
    if(!library){return null;}
    const q=norm(text).slice(0,220);
    const padded=" "+q.replace(/[^a-z0-9äöå]+/g," ")+" ";
    const direct=items.find(x=>x.name&&padded.includes(" "+norm(x.name).replace(/[^a-z0-9äöå]+/g," ")+" "));
    if(direct){return direct;}
    const words=q.split(/[^a-z0-9äöå]+/).filter(t=>t.length>=4);
    const scored=items.filter(x=>!x.name).map(x=>{
      const target=norm(itemText(x));
      return {x,score:words.reduce((n,t)=>n+(target.includes(t)?1:0),0)};
    }).filter(it=>it.score>0).sort((a,b)=>b.score-a.score);
    return scored.length&&scored[0].score>=Math.min(2,words.length)?scored[0].x:null;
  }
  function answer(text){
    const item=findOne(text);
    if(!item){return null;}
    showDetail(item);
    const first=sourceById(item.sources[0]);
    return (item.title||item.name)+": "+(item.summary||item.description)+" Lähde: "+(first?first.title:"tietoaineisto")+". Loput lähteet näkyvät Grimoire-kortissa.";
  }
  function creativeRift(){
    if(!library){return;}
    const a=items[Math.floor(Math.random()*items.length)];
    const different=items.filter(x=>x.category!==a.category);
    const b=different[Math.floor(Math.random()*different.length)];
    relatedEl.replaceChildren();
    relatedEl.append(node("p","eyebrow","FIKTIIVINEN TAIDEIDEA / EI HISTORIAVÄITE"));
    relatedEl.append(node("p","","Yhdistä '"+(a.title||a.name)+"' ja '"+(b.title||b.name)+
      "' yhteen kuvitteelliseen kohtaukseen. Tee toinen kerros symboleina, toinen äänenä. "+
      "Pidä lähteiden erot näkyvissä. Älä esitä yhteyttä historiallisena tosiasiana."));
    const links=node("div","source-links");
    links.append(buildSource(a.sources[0]));links.append(buildSource(b.sources[0]));
    relatedEl.append(links);
  }
  document.getElementById("grimoire-random").addEventListener("click",creativeRift);
  async function init(){
    statusEl.textContent="Ladataan paikallista Grimoire-kirjastoa...";
    try{
      const response=await fetch("/static/noki-grimoire.json",{credentials:"same-origin",cache:"no-store"});
      if(!response.ok){throw new Error("HTTP "+response.status);}
      const data=await response.json();
      if(data.schema_version!==1||!Array.isArray(data.entries)||!Array.isArray(data.spirits)||!Array.isArray(data.sources)){throw new Error("Tuntematon tietokantarakenne");}
      const known=new Set(data.sources.map(x=>x.id));
      for(const item of [...data.entries,...data.spirits]){
        if(!item.sources||!item.sources.length||item.sources.some(id=>!known.has(id))){throw new Error("Lähdeviite puuttuu");}
      }
      library=data;items=[...data.entries,...data.spirits];
      for(const [key,label] of Object.entries(data.categories)){const o=node("option","",label);o.value=key;categoryEl.append(o);}
      provenanceEl.textContent=data.claim+" Päiväys: "+data.prepared_on+". Ei automaattista verkkokeruuta, ei kopioituja kokonaisia kirjoja.";
      showDetail(null);render();
      window.NokiGrimoire={answer,search:function(t){queryEl.value=String(t||"").slice(0,120);resetPagination();},dataVersion:data.edition,ready:true};
    }catch(e){statusEl.textContent="Kirjasto ei latautunut: "+e.message+". Kopioi myös noki-grimoire.json hakemistoon /static.";}
  }
  window.NokiGrimoire={answer:function(){return null;},ready:false};
  void init();
})();