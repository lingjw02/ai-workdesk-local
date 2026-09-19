/* Clothing fragments are independent of the immutable character atlas. */
(() => {
 const images={}, rects={
  full:{top:[.245,.253,.46,.44],bottom:[.337,.478,.28,.17],socks:[.375,.625,.23,.35],shoes:[.398,.918,.19,.066],headwear:[.344,.074,.07,.25]},
  chibi:{top:[.29,.437,.44,.345],bottom:[.386,.63,.275,.145],socks:[.443,.77,.145,.205],shoes:[.445,.937,.145,.045],headwear:[.30,.21,.1,.30]}
 };
 const original={chibi:{top:[40,60,315,265],bottom:[404,129,273,148],socks:[805,98,170,230],shoes:[126,628,148,75],headwear:[440,407,86,284]},full:{top:[23,745,349,335],bottom:[399,862,300,168],socks:[801,752,178,335],shoes:[122,1360,158,82],headwear:[442,1090,90,334]}};
 const labels={default:'Original',casual:'Casual',ice_queen:'Ice queen',kimono:'Kimono',maid:'Maid',swimsuit:'Summer'};
 const variants=['casual','ice_queen','kimono','maid','swimsuit'];
 const pieces={
  casual:{top:[8,30,288,235],bottom:[296,48,244,197],shoes:[766,62,212,181],headwear:[1050,61,165,200]},
  ice_queen:{top:[10,264,278,246],bottom:[273,266,295,242],shoes:[777,297,195,201],headwear:[1035,286,172,226]},
  kimono:{top:[4,507,287,255],bottom:[320,502,194,263],socks:[561,577,149,156],shoes:[768,581,212,150],headwear:[1074,530,133,234]},
  maid:{top:[3,768,290,245],bottom:[280,774,273,234],socks:[567,766,147,253],shoes:[774,807,194,196],headwear:[1000,795,249,200]},
  swimsuit:{top:[47,1018,199,224],bottom:[294,1080,236,145],shoes:[771,1040,206,185],headwear:[973,1045,280,158]}
 };
 const available=(slot,item)=>item==='default'||(item==='swimsuit'?['headwear','shoes'].includes(slot):!(slot==='socks'&&['casual','ice_queen'].includes(item)));
 let ready=false,variantsReady=false,manifest=null;
 async function load(onload){try{const response=await fetch('assets/pet/manifest.json');if(!response.ok)throw Error('Missing wardrobe catalog');manifest=await response.json();for(const [name,atlas] of Object.entries(manifest.clothingLayers)){const im=new Image();images[name]=im;im.onload=()=>{if(name==='default')ready=true;else variantsReady=true;onload();};im.src='assets/pet/'+atlas.file;}}catch{onload();}}
 function draw(ctx,form,outfit,size,scale=1,baseImage=null){
  if(!ready)return;
  ctx.save();ctx.translate((1-scale)*size/2,(1-scale)*size/2);ctx.scale(scale,scale);
  for(const slot of ['socks','shoes','top','bottom','headwear']){
   const item=outfit[slot];if(!item||item==='none'||item==='base')continue;let image,crop,target=[...rects[form][slot]];
   if(item==='default'){image=images.default;crop=original[form][slot].map((v,i)=>v*(i%2===0?image.naturalWidth/1086:image.naturalHeight/1448));}
   else if(variantsReady&&available(slot,item)){
    image=images.variants;if(!pieces[item]?.[slot])continue;
    crop=pieces[item][slot].map((v,i)=>v*(i%2===0?image.naturalWidth/1254:image.naturalHeight/1254));
    if(slot==='top'){target[3]=form==='full'?.31:.24;}
    if(slot==='bottom'&&item==='casual'&&form==='full')target=[.35,.478,.25,.16];
    if(slot==='bottom'&&item==='kimono')target=form==='full'?[.28,.46,.4,.49]:[.32,.63,.38,.34];
    if(slot==='bottom'&&item==='maid')target=form==='full'?[.31,.478,.33,.21]:[.35,.63,.34,.19];
    if(slot==='shoes'&&item==='casual'){target[1]=.9;target[3]=.08;}
    if(slot==='bottom'&&item==='ice_queen'){target[0]-=.08;target[2]+=.16;target[3]=form==='full'?.40:.27;}
    if(slot==='socks'&&item==='kimono'){target[1]=.87;target[3]=.1;}
    if(slot==='headwear'&&item==='maid')target=form==='full'?[.37,.015,.225,.12]:[.31,.13,.37,.17];
    if(slot==='headwear'&&item==='casual')target=form==='full'?[.39,.075,.06,.09]:[.32,.21,.085,.12];
    if(slot==='headwear'&&item==='ice_queen')target=form==='full'?[.345,.09,.11,.145]:[.275,.205,.155,.205];
    if(slot==='headwear'&&item==='kimono')target=form==='full'?[.35,.085,.075,.14]:[.28,.20,.115,.215];
    if(slot==='headwear'&&item==='swimsuit')target=form==='full'?[.31,.005,.34,.16]:[.24,.105,.55,.23];
   }else continue;
   if(slot==='socks'&&baseImage?.naturalWidth){ctx.drawImage(fittedStockings(image,crop,baseImage,form,item,size,target),0,0);}
   else ctx.drawImage(image,...crop,target[0]*size,target[1]*size,target[2]*size,target[3]*size);
  }ctx.restore();
 }
 const sockCache=new Map();
 function fittedStockings(image,crop,base,form,item,size,target){
  const key=[form,item,size].join(':');if(sockCache.has(key))return sockCache.get(key);
  const result=document.createElement('canvas');result.width=result.height=size;const out=result.getContext('2d');
  const body=document.createElement('canvas');body.width=body.height=size;const bc=body.getContext('2d',{willReadFrequently:true});
  bc.drawImage(base,form==='full'?base.naturalWidth/2:0,0,base.naturalWidth/2,base.naturalHeight,0,0,size,size);
  const silhouette=bc.getImageData(0,0,size,size).data;
  const texture=document.createElement('canvas');texture.width=Math.ceil(crop[2]);texture.height=Math.ceil(crop[3]);const tc=texture.getContext('2d',{willReadFrequently:true});tc.drawImage(image,...crop,0,0,texture.width,texture.height);const pixels=tc.getImageData(0,0,texture.width,texture.height).data;
  const y0=Math.floor(target[1]*size),y1=Math.ceil(.982*size);
  const ranges=form==='full'?[[.34,.49],[.49,.65]]:[[.40,.52],[.52,.65]];
  for(let leg=0;leg<2;leg++){
   const a=Math.floor(leg*texture.width/2),b=Math.floor((leg+1)*texture.width/2);
   const rows=[];
   for(let y=0;y<texture.height;y++){let lo=b,hi=a;for(let x=a;x<b;x++)if(pixels[(y*texture.width+x)*4+3]>160){lo=Math.min(lo,x);hi=Math.max(hi,x);}if(hi-lo>4)rows.push({y,lo,hi});}
   if(!rows.length)continue;
   for(let y=y0;y<y1;y++){
    let lo=size,hi=0;for(let x=Math.floor(ranges[leg][0]*size);x<ranges[leg][1]*size;x++)if(silhouette[(y*size+x)*4+3]>100){lo=Math.min(lo,x);hi=Math.max(hi,x);}
    if(hi<=lo)continue;
    const row=rows[Math.min(rows.length-1,Math.floor((y-y0)/(y1-y0)*rows.length))];
    out.drawImage(texture,row.lo,row.y,row.hi-row.lo+1,1,lo,y,hi-lo+1,1);
   }
  }
  sockCache.set(key,result);return result;
 }
 function options(slot){if(['glasses','earrings'].includes(slot))return [{id:'none',label:'No items imported'}];return [{id:['top','bottom'].includes(slot)?'base':'none',label:['top','bottom'].includes(slot)?'Base garment':'None'},...Object.entries(labels).filter(([id])=>(id==='default'?ready:variantsReady)&&available(slot,id)).map(([id,label])=>({id,label}))];}
 window.PetWardrobe={load,draw,options,get ready(){return ready},get variantsReady(){return variantsReady},get manifest(){return manifest}};
})();
