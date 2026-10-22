// Seekable photographic portrait. Source atlases remain unchanged on disk.
// Blend only facial regions so changing a mouth never jumps the whole head.
export function photoHuman(canvas,{atlasUrl,face={},fit='contain'}={}){
 const ctx=canvas.getContext('2d');
 if(!ctx)throw new Error('無法建立人物畫面');
 const atlas=new Image();let loaded=false,disposed=false;
 const patch=document.createElement('canvas'),pc=patch.getContext('2d');
 const ready=new Promise((resolve,reject)=>{atlas.onload=()=>{if(disposed)return resolve();loaded=true;canvas.dataset.visualType='photoreal-portrait';renderAt(0,0);resolve();};atlas.onerror=()=>reject(new Error('擬真人物素材載入失敗'));atlas.src=atlasUrl;});
 function renderAt(t,amplitude=0){
  if(!loaded||disposed)return;
  const w=Math.round(canvas.clientWidth||canvas.width||480),h=Math.round(canvas.clientHeight||canvas.height||600);
  if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}
  const sw=atlas.naturalWidth/2,sh=atlas.naturalHeight/2;
  const scale=(fit==='cover'?Math.max:Math.min)(w/sw,h/sh),dw=sw*scale,dh=sh*scale,dx=(w-dw)/2,dy=fit==='cover'?0:(h-dh)/2;
  ctx.fillStyle='#101a27';ctx.fillRect(0,0,w,h);ctx.drawImage(atlas,0,0,sw,sh,dx,dy,dw,dh);
  function region(frame,x,y,rx,ry,opacity){
   if(opacity<=0)return;
   if(patch.width!==w||patch.height!==h){patch.width=w;patch.height=h;}
   pc.clearRect(0,0,w,h);pc.globalCompositeOperation='source-over';
   pc.drawImage(atlas,(frame%2)*sw,Math.floor(frame/2)*sh,sw,sh,dx,dy,dw,dh);
   pc.globalCompositeOperation='destination-in';pc.save();pc.translate(dx+x*dw,dy+y*dh);pc.scale(rx*dw,ry*dh);
   const gradient=pc.createRadialGradient(0,0,.55,0,0,1);gradient.addColorStop(0,'#fff');gradient.addColorStop(1,'#fff0');pc.fillStyle=gradient;pc.fillRect(-1,-1,2,2);pc.restore();
   ctx.globalAlpha=opacity;ctx.drawImage(patch,0,0);ctx.globalAlpha=1;
  }
  const a=Math.max(0,Math.min(1,amplitude));
  const mouth=face.mouth||[.5,.53,.18,.105],eyes=face.eyes||[.5,.335,.32,.10];
  if(a>.025){region(1,...mouth,Math.min(1,a*6));if(a>.36)region(2,...mouth,Math.min(1,(a-.36)*2));canvas.dataset.expression=a>.5?'speaking-open':'speaking';}
  else canvas.dataset.expression='neutral';
  const blink=(t+1.2)%4.7;if(blink<.17){region(3,...eyes,Math.sin(blink/.17*Math.PI));canvas.dataset.expression='blink';}
 }
 return{ready,renderAt,dispose(){disposed=true;atlas.onload=null;atlas.onerror=null;ctx.clearRect(0,0,canvas.width,canvas.height);}};
}
