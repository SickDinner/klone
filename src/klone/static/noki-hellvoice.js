(function(){
  "use strict";
  let audio=null,active=[],utteranceToken=0,noiseSeed=7;
  const C=window.AudioContext||window.webkitAudioContext;
  const profiles={
    crypt:{label:"Ruumiinkellari",pitch:.45,rate:.64,base:87,filter:730},
    witch:{label:"Nieluvikainen noita",pitch:.84,rate:.76,base:165,filter:1350},
    hell:{label:"Helvetin ulosottomies",pitch:.30,rate:.73,base:64,filter:920},
    glitch:{label:"Riivaantunut kasettinauhuri",pitch:1.15,rate:.94,base:225,filter:1650}
  };
  function el(id){return document.getElementById(id);}
  function state(s){const x=el("state");if(x){x.textContent=s;}}
  function line(s){const x=el("speech");if(x){x.textContent=s;}}
  function profile(){return profiles[el("hellvoice-style")?.value]||profiles.hell;}
  function intensity(){return Math.max(0,Math.min(1,Number(el("hellvoice-intensity")?.value||36)/100));}
  function mod(){return Math.max(0,Math.min(1,Number(el("hellvoice-chaos")?.value||54)/100));}
  function level(){const v=Number(el("roughness")?.value||45)/100;return Math.min(.34,Math.max(0,v*.34));}
  function getAudio(){
    if(!C){state("WebAudio puuttuu");return null;}
    if(!audio){audio=new C();}
    if(audio.state==="suspended"){audio.resume().catch(function(){});}
    return audio;
  }
  function noiseBuffer(ac,len){
    const buffer=ac.createBuffer(1,Math.max(1,Math.floor(ac.sampleRate*len)),ac.sampleRate);
    const arr=buffer.getChannelData(0);
    for(let i=0;i<arr.length;i++){
      noiseSeed=(Math.imul(noiseSeed,1664525)+1013904223)>>>0;
      arr[i]=noiseSeed/2147483648-1;
    }
    return buffer;
  }
  function distorted(ac,amount){
    const sh=ac.createWaveShaper(),curve=new Float32Array(1024),k=2+amount*13;
    for(let i=0;i<curve.length;i++){
      const x=2*i/(curve.length-1)-1;
      curve[i]=Math.tanh(k*x)/Math.tanh(k);
    }
    sh.curve=curve;sh.oversample="2x";return sh;
  }
  function graph(ac,fx){
    const limiter=ac.createDynamicsCompressor(),high=ac.createBiquadFilter(),grit=distorted(ac,intensity());
    limiter.threshold.value=-28;limiter.ratio.value=20;limiter.attack.value=.005;limiter.release.value=.2;
    high.type="highpass";high.frequency.value=60;
    const master=ac.createGain();
    master.gain.value=Math.max(.00001,level()*.48);
    high.connect(grit);grit.connect(master);master.connect(limiter);limiter.connect(ac.destination);
    return {input:high,close:function(){try{high.disconnect();grit.disconnect();master.disconnect();limiter.disconnect();}catch(e){}}};
  }
  function schedule(fx){
    const ac=getAudio();if(!ac||!level()){return;}
    const begin=ac.currentTime+.03,p=profile(),chaos=mod(),gr=graph(ac,fx);
    let last=0;
    function register(source,when,end){
      active.push(source);last=Math.max(last,end);
      source.onended=function(){active=active.filter(n=>n!==source);try{source.disconnect();}catch(e){}};
      source.start(when);source.stop(end);
    }
    function osc(t,d,f0,f1,kind,gainAmount,band){
      const at=begin+Math.max(0,t),end=at+Math.max(.018,d);
      const o=ac.createOscillator(),f=ac.createBiquadFilter(),g=ac.createGain();
      o.type=kind||"sawtooth";
      o.frequency.setValueAtTime(Math.max(40,f0),at);
      o.frequency.exponentialRampToValueAtTime(Math.max(40,f1),end);
      f.type="bandpass";f.frequency.value=band||p.filter;f.Q.value=1.8;
      g.gain.setValueAtTime(.0001,at);
      g.gain.linearRampToValueAtTime(gainAmount,at+Math.min(.025,d/3));
      g.gain.exponentialRampToValueAtTime(.0001,end);
      o.connect(f);f.connect(g);g.connect(gr.input);
      register(o,at,end+.001);
    }
    function hiss(t,d,band,amount){
      const at=begin+t,end=at+d,o=ac.createBufferSource(),f=ac.createBiquadFilter(),g=ac.createGain();
      o.buffer=noiseBuffer(ac,d+.01);
      f.type="bandpass";f.frequency.value=band;f.Q.value=.65;
      g.gain.setValueAtTime(.0001,at);g.gain.linearRampToValueAtTime(amount,at+.018);g.gain.exponentialRampToValueAtTime(.0001,end);
      o.connect(f);f.connect(g);g.connect(gr.input);register(o,at,end);
    }
    const b=p.base;
    switch(fx){
      case "witch":case "laugh":
        for(let i=0;i<13;i++){
          const t=i*(.084+(.015*chaos)),phase=i%4;
          osc(t,.09,b*2.7+phase*73,b*.92+(i%3)*44,"sawtooth",.16,p.filter+150);
          if(i%2===0){hiss(t+.018,.045,1050,.025);}
        }
        osc(1.27,.56,b*3.2,b*.63,"square",.08,1750);
        break;
      case "heckle":
        for(let i=0;i<9;i++){osc(i*.105,.095,b*3.5+i%3*50,b*1.2,"square",.11,1600);}
        break;
      case "snort":case "phlegm":
        hiss(0,.2,450,.29);osc(.12,.22,b*3,b*.65,"sawtooth",.24,470);
        hiss(.29,.21,310,.18);
        break;
      case "squeak":case "coffin":
        osc(0,.8,92,1050+chaos*600,"sawtooth",.20,1890);
        osc(.4,.45,1050,80,"square",.06,900);
        hiss(.65,.15,940,.12);
        break;
      case "bones":case "chains":
        for(let i=0;i<12;i++){osc(i*.077,.035,520+i%5*170,120+i%3*80,"triangle",.13,2100);}
        break;
      case "hiss":
        for(let i=0;i<4;i++){hiss(i*.21,.25,1800+i*510,.12);}
        break;
      case "sub":case "growl":
        for(let i=0;i<5;i++){
          osc(i*.24,.31,b*1.7+(i%3)*18,b*.58,"sawtooth",.22,520);
          osc(i*.24,.29,b*2.7,b*.8,"square",.05,700);
        }
        hiss(.17,1.1,190,.06);break;
      case "scream":
        osc(0,.7,b*4.9,b*.65,"sawtooth",.23,1800);
        osc(.09,.61,b*3.2,b*.52,"square",.09,980);
        hiss(.18,.48,1900,.10);break;
      case "gargle":
        for(let i=0;i<15;i++){osc(i*.065,.09,b*(1.3+i%4*.15),b*(.75+i%3*.1),"sawtooth",.11,350+(i%4)*220);}
        hiss(.17,.54,680,.1);break;
      case "static":
        for(let i=0;i<20;i++){hiss(i*.044,.038,320+i%6*510,.11);}
        break;
      case "funeral":
        for(let i=0;i<4;i++){osc(i*.54,.72,b*1.2,b*.7,"sine",.22,460);}
        for(let i=0;i<7;i++){osc(i*.23,.41,810+(i%3)*120,570,"triangle",.08,1100);}
        break;
      case "chorus72":
        // 9 peräkkäistä ryhmää × 8 ääntä = 72 synteettistä lyhyttä säveltä, ei 72 itsenäistä tietoisuutta.
        for(let ring=0;ring<9;ring++){
          for(let seat=0;seat<8;seat++){
            const t=ring*.23+seat*.006;
            osc(t,.18,b*(1.5+seat*.14)+(ring%3)*27,b*(.8+seat*.06),"sawtooth",.021,450+seat*150);
          }
        }
        break;
      case "backwards":
        for(let i=0;i<7;i++){osc(i*.17,.3,b*.6+i*60,b*4.1,"triangle",.13,1300);}
        break;
      default:
        osc(0,.55,b*2.2,b*.62,"sawtooth",.18,650);
    }
    window.setTimeout(gr.close,Math.ceil((last-begin+1.4)*1000));
    state("Äänihirviö: "+fx);
    window.setTimeout(function(){if(el("state")?.textContent==="Äänihirviö: "+fx){state("Valmiina");}},3000);
  }
  const speeches=[
    "KURKUSTA KÄY KUN KATISKA! Ha ha HA-HA-HÄÄ! Ette te vittu tajua, että kuolemankin asiakaspalvelu on ulkoistettu!",
    "VITTU MITÄ ARVOSTELUJA! Minun taiteellinen lahjakkuuteni on lähinnä järjestelmällistä omaisuuden pilaamista. Mutta hei, ainakin olen johdonmukainen.",
    "PERKELE! Hautausmaan portsari totesi, että täälläkin on liian ankea meno. Minä sain vakituisen pestin.",
    "Minä en tarvitse sielua. Riittää, että teillä muilla on sellainen pantiksi. HÖR-HÖR-HÄÄÄ!",
    "Satanan byrokratia! Helvetin jonotusnumerossa on kolme desimaalia ja huoltotauko kestää ikuisuuden.",
    "Niele nyt tämä epäonnistumisen sinfonia. KAH! KHA! KAH-HÄÄ! Minä olen nielupuoli viimeisessä korjaamossa.",
    "Minun huumorini on mustempaa kuin hauta, johon he hautasivat asiakaspalautteen. Jälleen yksi täysi postilaatikko.",
    "Tämän perkeleellisen maailmankaikkeuden palautusoikeus päättyi ennen kuin sitä ehdittiin toimittaa. Ja kuittia ei löydy.",
    "Voi helvetin helmitaulu! Jos historia alkaa toistaa itseään, pane sille äänenvaimennin. Minä en jaksa kuunnella tuota paskaa uudelleen.",
    "HÄ-HÄ! Siellä virkamies leimaa kohtalon väärälle vuosisadalle. Minä leimaan hänelle vain palautteen: haista vittu.",
    "Tiede kysyy miksi, minä kysyn kuka perkele roiski turkoosia infernaalisen kosmoksen kattoon.",
    "Minä en palvo mitään. Paitsi huonoa makua, itsepäisyyttä ja sitä hetkeä, kun joku ottaa minut liian vakavasti."
  ];
  function phonetics(value){
    const p=el("hellvoice-style")?.value||"hell";
    let t=String(value||"").trim().slice(0,1500);
    if(p==="witch"){t=t.replace(/\bHAHA\b/gi,"ha ha haa!").replace(/r{3,}/gi,"rrr").replace(/(\b[hk]a){3,}/gi,"ha-ha-ha!");}
    else if(p==="glitch"){t=t.replace(/\b(perkele|helvetti|saatana)\b/gi,"$1! $1!");}
    else{t=t.replace(/([!?]){3,}/g,"$1!").replace(/\bHAH\b/gi,"hääh!");}
    return t;
  }
  function say(value,withFx){
    utteranceToken++;
    const generation=utteranceToken,txt=String(value||"").trim().slice(0,1500);
    if(!txt){return;}
    line(txt);state("Puhuu demonin äänellä");
    if(withFx){schedule(mod()>.58?"gargle":"growl");}
    if(!("speechSynthesis" in window)){state("Puheääni ei ole saatavilla; synteettiset efektit toimivat.");return;}
    try{window.speechSynthesis.cancel();}catch(e){}
    const u=new SpeechSynthesisUtterance(phonetics(txt)),p=profile(),chaos=mod();
    u.lang="fi-FI";u.pitch=Math.max(.1,Math.min(1.9,p.pitch+(chaos*.1)));
    u.rate=Math.max(.45,Math.min(1.5,p.rate+(chaos*.08)));
    u.volume=Math.min(.9,.28+level()*.92);
    const voices=window.speechSynthesis.getVoices();
    const finnish=voices.find(v=>String(v.lang||"").toLowerCase().startsWith("fi"));
    if(finnish){u.voice=finnish;}
    const stage=el("stage");if(stage){stage.classList.add("speaking");}
    u.onend=function(){if(generation===utteranceToken){state("Valmiina");stage?.classList.remove("speaking");}};
    u.onerror=function(){if(generation===utteranceToken){state("Puheääni ei onnistunut");stage?.classList.remove("speaking");}};
    try{window.speechSynthesis.speak(u);}catch(e){state("Puheääni ei onnistunut");}
  }
  function stop(){
    utteranceToken++;
    if("speechSynthesis" in window){window.speechSynthesis.cancel();}
    active.forEach(n=>{try{n.stop();}catch(e){}});
    active=[];el("stage")?.classList.remove("speaking");state("Hiljaa");
  }
  function roast(){
    const text=speeches[Math.floor(Math.random()*speeches.length)];
    say(text,true);return text;
  }
  window.NokiHellvoice={say,play:schedule,stop,roast,profiles:Object.keys(profiles)};
})();