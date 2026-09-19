/* In-app companion. Input state and visual frames are ephemeral, never stored. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id), key='emilia.companion.v1';
  let saved; try {saved=JSON.parse(localStorage.getItem(key));} catch {}
  let state=PetState.create(saved), page='dashboard', paused=false, drag=null, moved=false;
  let enabled=false,busy=false,lastStarted=0,generation=0,controller=null,previous=null;
  let input={left:false,right:false,mouse:false,focused:document.hasFocus()}, held=new Set();
  let base=new Image(),sprites=new Image(),frame=0,zoom=1,form='full',bubbleTimer,walkTimer;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  function act(action){state=PetState.reduce(state,action);try{localStorage.setItem(key,JSON.stringify(state));}catch{} sync();}
  function say(text){$('petBubble').textContent=text;clearTimeout(bubbleTimer);bubbleTimer=setTimeout(()=>$('petBubble').textContent='',6500);}
  function clampPosition(x,y){return {x:Math.max(innerWidth>760?228:4,Math.min(innerWidth-150,x)),y:Math.max(180,Math.min(innerHeight-185,y))};}
  function position(x,y){const p=clampPosition(x,y);$('petOverlay').style.left=p.x+'px';$('petOverlay').style.top=p.y+'px';return p;}
  function visitFurniture(activity){
    if(!['tea','phone','magic'].includes(activity))return false;
    const kind=activity==='tea'?'chair':activity==='phone'?'desk':'shelf';
    const furniture=document.querySelector(`.view.active [data-pet-furniture="${kind}"]`);
    if(!furniture)return false;const r=furniture.getBoundingClientRect(),pet=$('petOverlay').getBoundingClientRect();
    if(r.top<180+pet.height+12||r.bottom>innerHeight-60)return false;
    const p=position(r.left+r.width/2-pet.width/2,r.top-pet.height-12);act({type:'position/set',...p});return true;
  }
  function draw(canvas,normal=false){
    if(!canvas)return;const ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);
    const customized=['top','bottom','socks','shoes'].some(slot=>state.outfit[slot]!=='default')||!['none','default'].includes(state.outfit.headwear);
    if(!normal&&(!customized||state.mode==='bongo')&&sprites.complete&&sprites.naturalWidth){
      let cell=0;
      if(state.mode==='bongo')cell=12+['idle','left','right','both'].indexOf(PetState.bongoPose(input));
      else if(state.activity==='walk')cell=4+frame%4;
      else cell=({tea:8,magic:9,phone:10,sleep:11,greet:2,dragged:3})[state.activity]??(frame%20===0?1:0);
      const w=sprites.naturalWidth/4,h=sprites.naturalHeight/4;
      ctx.drawImage(sprites,cell%4*w,Math.floor(cell/4)*h,w,h,0,0,canvas.width,canvas.height);
    }else if(base.complete&&base.naturalWidth){
      const w=base.naturalWidth/2,h=base.naturalHeight,scale=normal?zoom:1;
      ctx.drawImage(base,(normal&&form==='full'?1:0)*w,0,w,h,(1-scale)*canvas.width/2,(1-scale)*canvas.height/2,canvas.width*scale,canvas.height*scale);
      PetWardrobe.draw(ctx,normal?form:'chibi',state.outfit,canvas.width,scale,base);
    }
  }
  function sync(){
    if(!$('petOverlay'))return;
    $('petOverlay').hidden=!state.visible||document.hidden||!!document.querySelector('dialog[open]');
    $('petLabel').textContent=state.mode==='bongo'?'Bongo · live input':paused?'Resting here':state.activity;
    $('petMode').textContent=state.mode==='roam'?'Switch to Bongo':'Switch to roaming';
    $('petVisibility').textContent=state.visible?'Hide companion':'Show companion';
    $('petLevel').textContent='Level '+PetState.level(state);$('petXp').value=state.xp%100;
    $('petStats').textContent=`${state.xp%100} / 100 XP · Energy ${state.energy} · Affection ${state.affection}`;
    $('petRoam').setAttribute('aria-pressed',state.mode==='roam');$('petBongo').setAttribute('aria-pressed',state.mode==='bongo');
    draw($('petCanvas'));draw($('petModel'),true);
  }
  function resetInput(){held.clear();input={left:false,right:false,mouse:false,focused:document.hasFocus()&&!document.hidden};sync();}
  function renderWardrobe(){
    const labels={top:'Tops',bottom:'Bottoms',socks:'Socks',shoes:'Shoes',headwear:'Headwear',glasses:'Glasses',earrings:'Earrings'};
    $('petWardrobe').replaceChildren();
    for(const [slot,label] of Object.entries(labels)){
      const field=document.createElement('label');field.textContent=label;const select=document.createElement('select');select.dataset.slot=slot;
      for(const item of PetWardrobe.options(slot)){const option=document.createElement('option');option.value=item.id;option.textContent=item.label;select.append(option);}
      select.value=state.outfit[slot];if(!select.value)select.value=['top','bottom'].includes(slot)?'base':'none';select.disabled=select.options.length===1;
      select.onchange=()=>act({type:'outfit/set',slot,item:select.value});field.append(select);$('petWardrobe').append(field);
    }
    $('petWardrobeStatus').textContent='Mix clothing independently on the same character. Custom outfits use a standing pose; Bongo and animated actions wear the original outfit. The lilac base garment stays underneath. Summer clothing is catalogued; its hat and shoes can be worn. No glasses or earrings were present in the source assets.';
  }
  function invalidate(){generation++;controller?.abort();previous=null;}
  function awareness(on){enabled=on;invalidate();$('petAwareness').checked=on;$('petObserving').hidden=!on;$('petObserving').textContent='Local awareness on · click to stop';$('petVisionStatus').textContent=on?'Awareness enabled · waiting for a changed screen.':'Awareness off. No screenshots are being taken.';}
  async function api(path,body,signal){const r=await fetch('/api/companion/vision/'+path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal});const data=await r.json();if(!r.ok)throw Error(data.detail||'Local vision unavailable.');return data;}
  async function observe(){
    const privateView=page==='settings'||page==='companion'||!!document.querySelector('dialog[open]');
    if(!PetAwareness.canObserve({enabled,hidden:document.hidden,privateView,busy,now:Date.now(),lastStarted}))return;
    busy=true;lastStarted=Date.now();const token=generation;controller=new AbortController();
    try{
      const target=document.querySelector('.view.active');if(!target)return;
      const rect=target.getBoundingClientRect();const width=Math.min(rect.width,innerWidth-Math.max(0,rect.left)),height=Math.min(rect.height,innerHeight-Math.max(0,rect.top));if(width<=0||height<=0)return;
      const canvas=await html2canvas(target,{backgroundColor:'#171c25',scale:Math.min(1,960/width),width,height,logging:false,useCORS:false,allowTaint:false,proxy:null,
        ignoreElements:el=>el.matches?.('input,textarea,[contenteditable],iframe,video,[data-private],[data-pet-private],[data-sensitive],[data-html2canvas-ignore],img[src^="http"]'),
        onclone:doc=>{doc.querySelectorAll('input,textarea,[contenteditable],[data-private],[data-sensitive]').forEach(el=>{el.textContent='';el.style.visibility='hidden';});}
      });
      if(token!==generation||!enabled||document.hidden)return;
      const small=document.createElement('canvas');small.width=64;small.height=48;small.getContext('2d').drawImage(canvas,0,0,64,48);const pixels=small.getContext('2d').getImageData(0,0,64,48).data;
      if(!PetAwareness.frameChanged(previous,pixels))return;
      const result=await api('analyze',{image:canvas.toDataURL('image/jpeg',.7),context:'Current app page: '+page},controller.signal);
      if(token!==generation||!enabled||document.hidden)return;previous=pixels;
      say(PetAwareness.cleanObservation(result.observation));$('petObserving').textContent='Local awareness on · click to stop';$('petVisionStatus').textContent='Last local observation: '+new Date().toLocaleTimeString();
    }catch(e){if(e.name!=='AbortError'&&token===generation){$('petVisionStatus').textContent=e.message;$('petObserving').textContent='Awareness unavailable · click to stop';}}
    finally{busy=false;}
  }
  function init(){
    const nav=document.createElement('button');nav.id='navCompanionBtn';nav.className='side-item';nav.innerHTML='<svg class="ico-svg" aria-hidden="true"><use href="#i-zap"/></svg><span class="label">Companion</span>';$('navMediaBtn').after(nav);
    const room=document.createElement('section');room.className='view pet-room';room.id='view-companion';room.innerHTML=`<div class="companion-room"><header class="companion-heading"><div><span class="pet-eyebrow">A little company, while you create</span><h1>Emilia’s room</h1><p>Your companion across EMILIA LAB.</p></div><button id="petVisibility">Hide companion</button></header><div class="companion-grid"><div><div class="pet-stage"><div class="pet-stage-controls"><button id="petForm">Show chibi</button><label>Zoom <input id="petZoom" type="range" min="1" max="2" step=".1" value="1"></label></div><canvas id="petModel" width="700" height="700" role="img" aria-label="Emilia character preview"></canvas></div><p class="pet-muted">Silver hair, violet eyes, and a little ice magic. Drag Emilia to a comfortable spot, or click her for controls.</p></div><div><section class="pet-panel"><h2 id="petLevel">Level 1</h2><progress class="pet-meter" id="petXp" max="100" value="0" aria-label="Experience toward next level"></progress><p id="petStats"></p><div class="pet-actions"><button data-care="feed">Share tea</button><button data-care="pet">Say hello</button><button data-care="play">Practice magic</button></div><p class="pet-muted">Care earns XP every 30 seconds, up to 120 a day. Tea has a one-minute cooldown.</p></section><section class="pet-panel"><h2>Keep me company</h2><div class="pet-actions"><button id="petRoam">Roaming</button><button id="petBongo">Bongo keyboard</button><button id="petPause">Pause roaming</button></div><p class="pet-muted">Bongo follows real keyboard and mouse activity inside this app. Password fields and Settings are excluded.</p></section><section class="pet-panel"><h2>Dressing room</h2><div id="petWardrobe" class="pet-wardrobe"></div><p id="petWardrobeStatus" class="pet-muted">Character base ready. Clothing layers are being prepared; the original outfit files remain untouched.</p></section><section class="pet-panel" data-private><h2>Local awareness</h2><p class="pet-muted">When enabled, Emilia observes changed visible app screens at most once every 10 seconds. Screenshots stay on this computer. Settings, this room, input fields and private elements are excluded.</p><label class="pet-toggle"><input id="petAwareness" type="checkbox">Let Emilia see this workspace</label><div class="pet-config"><label>Local vision endpoint<input id="petEndpoint" value="http://127.0.0.1:11434/v1" spellcheck="false"></label><label>Vision model<input id="petVisionModel" placeholder="Model name from your local service" spellcheck="false"></label><div class="pet-actions"><button id="petConnect">Save and test</button></div></div><p class="pet-status" id="petVisionStatus" role="status">Awareness off. No screenshots are being taken.</p><p class="pet-muted">Requires a running local vision model with an OpenAI-compatible API. No cloud fallback. Embedded media and some visual effects may not appear in captures.</p></section></div></div></div>`;
    $('view-settings').before(room);
    room.querySelector('.companion-grid').firstElementChild.classList.add('companion-preview');
    const furniture=document.createElement('div');furniture.className='pet-furniture';furniture.innerHTML='<button data-pet-furniture="chair" data-activity="tea">Tea chair</button><button data-pet-furniture="desk" data-activity="phone">Little desk</button><button data-pet-furniture="shelf" data-activity="magic">Crystal shelf</button>';
    room.querySelector('.pet-stage').after(furniture);furniture.querySelectorAll('button').forEach(b=>b.onclick=()=>{act({type:'mode/set',mode:'roam'});act({type:'activity/set',activity:b.dataset.activity});visitFurniture(b.dataset.activity);say(b.dataset.activity==='tea'?'A warm cup of tea, right here.':b.dataset.activity==='magic'?'A little ice magic for our shelf.':'I’ll keep you company at the desk.');});
    const overlay=document.createElement('div');overlay.id='petOverlay';overlay.className='pet-overlay';overlay.dataset.html2canvasIgnore='true';overlay.innerHTML='<div id="petBubble" class="pet-bubble" role="status"></div><div id="petMenu" class="pet-menu" hidden><button id="petMode">Switch to Bongo</button><button id="petOpenRoom">Open companion room</button><button id="petHide">Hide companion</button></div><button id="petBody" class="pet-body" aria-label="Emilia: click for controls or drag to move" aria-expanded="false"><canvas id="petCanvas" width="300" height="300"></canvas></button><div id="petLabel" class="pet-label"></div>';document.body.append(overlay);
    const indicator=document.createElement('button');indicator.id='petObserving';indicator.className='pet-observing';indicator.hidden=true;indicator.dataset.html2canvasIgnore='true';indicator.textContent='Local awareness on · click to stop';indicator.onclick=()=>awareness(false);document.body.append(indicator);
    nav.onclick=()=>App.showView('companion');$('petOpenRoom').onclick=()=>{App.showView('companion');$('petMenu').hidden=true;};
    $('petVisibility').onclick=()=>act({type:'visible/set',visible:!state.visible});$('petHide').onclick=()=>act({type:'visible/set',visible:false});
    const mode=m=>{clearTimeout(walkTimer);overlay.style.transition='';resetInput();act({type:'activity/set',activity:'idle'});act({type:'mode/set',mode:m});};$('petMode').onclick=()=>mode(state.mode==='roam'?'bongo':'roam');$('petRoam').onclick=()=>mode('roam');$('petBongo').onclick=()=>mode('bongo');
    $('petPause').onclick=()=>{paused=!paused;clearTimeout(walkTimer);overlay.style.transition='';$('petPause').textContent=paused?'Resume roaming':'Pause roaming';act({type:'activity/set',activity:'idle'});};
    room.querySelectorAll('[data-care]').forEach(el=>el.onclick=()=>{const before=state.xp;act({type:el.dataset.care});say(state.xp>before?{feed:'Tea together makes a lovely break.',pet:'I’m happy to keep you company.',play:'Let’s make a little ice crystal!'}[el.dataset.care]:'Let’s enjoy a quiet moment together.');});
    $('petForm').onclick=()=>{form=form==='full'?'chibi':'full';$('petForm').textContent=form==='full'?'Show chibi':'Show normal form';draw($('petModel'),true);};$('petZoom').oninput=e=>{zoom=Number(e.target.value);if(zoom>1){form='full';$('petForm').textContent='Show chibi';}draw($('petModel'),true);};
    $('petAwareness').onchange=e=>awareness(e.target.checked);
    $('petConnect').onclick=async()=>{awareness(false);$('petVisionStatus').textContent='Checking local service…';try{await api('config',{endpoint:$('petEndpoint').value,model:$('petVisionModel').value});const s=await api('test',{});$('petVisionStatus').textContent=s.message;}catch(e){$('petVisionStatus').textContent=e.message;}};
    api('status').then(s=>{$('petEndpoint').value=s.endpoint;$('petVisionModel').value=s.model;}).catch(()=>{});
    base.onload=sync;base.src='assets/pet/base.png';sprites.onload=sync;sprites.src='assets/pet/sprites.png';
    PetWardrobe.load(()=>{renderWardrobe();sync();});
    const initialPosition=position(saved?state.position.x:innerWidth-175,saved?state.position.y:innerHeight-300);act({type:'position/set',...initialPosition});
    $('petBody').onpointerdown=e=>{if(e.button!==0)return;clearTimeout(walkTimer);const r=overlay.getBoundingClientRect();overlay.style.transition='';position(r.left,r.top);drag={x:e.clientX,y:e.clientY,left:r.left,top:r.top};moved=false;e.currentTarget.setPointerCapture(e.pointerId);};
    $('petBody').onpointermove=e=>{if(!drag)return;if(Math.hypot(e.clientX-drag.x,e.clientY-drag.y)>5)moved=true;if(moved){state.activity='dragged';position(drag.left+e.clientX-drag.x,drag.top+e.clientY-drag.y);sync();}};
    $('petBody').onpointerup=()=>{if(moved){const r=overlay.getBoundingClientRect();act({type:'position/set',x:r.left,y:r.top});act({type:'activity/set',activity:'idle'});}drag=null;};
    $('petBody').onpointercancel=()=>{drag=null;moved=false;};$('petBody').onclick=()=>{if(moved){moved=false;return;}$('petMenu').hidden=!$('petMenu').hidden;$('petBody').setAttribute('aria-expanded',!$('petMenu').hidden);$('petBubble').textContent='';};
    $('petBody').addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;e.preventDefault();clearTimeout(walkTimer);overlay.style.transition='';const r=overlay.getBoundingClientRect(),step=e.shiftKey?30:10;const p=position(r.left+(e.key==='ArrowRight'?step:e.key==='ArrowLeft'?-step:0),r.top+(e.key==='ArrowDown'?step:e.key==='ArrowUp'?-step:0));act({type:'position/set',...p});});
    document.addEventListener('click',e=>{if(!overlay.contains(e.target)){$('petMenu').hidden=true;$('petBody').setAttribute('aria-expanded','false');}});
    document.addEventListener('keydown',e=>{if(e.key==='Escape'){$('petMenu').hidden=true;return;}if(PetState.isPrivateInput(e.target)||page==='settings')return;held.add(e.code);input.focused=true;input.left=[...held].some(k=>/^(Key[QWERTASDFGZXCVB]|Digit[1-5]|Space)/.test(k));input.right=[...held].some(k=>! /^(Key[QWERTASDFGZXCVB]|Digit[1-5]|Space)/.test(k));sync();});
    document.addEventListener('keyup',e=>{held.delete(e.code);input.left=[...held].some(k=>/^(Key[QWERTASDFGZXCVB]|Digit[1-5]|Space)/.test(k));input.right=held.size>0&&[...held].some(k=>! /^(Key[QWERTASDFGZXCVB]|Digit[1-5]|Space)/.test(k));sync();});
    document.addEventListener('pointerdown',e=>{if(!PetState.isPrivateInput(e.target)&&page!=='settings'){input.mouse=true;input.focused=true;sync();}});document.addEventListener('pointerup',()=>{input.mouse=false;sync();});
    document.addEventListener('focusin',e=>{if(PetState.isPrivateInput(e.target))resetInput();});
    window.addEventListener('blur',resetInput);window.addEventListener('resize',()=>{const r=overlay.getBoundingClientRect();position(r.left,r.top);});
    document.addEventListener('visibilitychange',()=>{resetInput();invalidate();sync();});document.addEventListener('studio:view',e=>{page=e.detail;invalidate();resetInput();nav.classList.toggle('active',page==='companion');});
    setInterval(()=>{if(document.hidden||!state.visible)return;frame++;overlay.hidden=!!document.querySelector('dialog[open]');draw($('petCanvas'));},160);
    setInterval(()=>{if(paused||drag||state.mode!=='roam'||!state.visible||document.hidden||!$('petMenu').hidden)return;const custom=['top','bottom','socks','shoes'].some(s=>state.outfit[s]!=='default');const activity=reduced.matches||custom?'idle':PetState.chooseIdle();act({type:'activity/set',activity});visitFurniture(activity);if(activity==='walk'){const r=overlay.getBoundingClientRect();const p=clampPosition(r.left+(Math.random()-.5)*300,Math.min(r.top,innerHeight-300));overlay.style.transition='left 3s linear, top 3s linear';position(p.x,p.y);walkTimer=setTimeout(()=>{overlay.style.transition='';act({type:'position/set',...p});act({type:'activity/set',activity:'idle'});},3000);}},12000);
    setInterval(observe,1500);sync();
  }
  document.addEventListener('DOMContentLoaded',init);
})();
