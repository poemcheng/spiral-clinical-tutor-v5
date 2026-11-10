/* On-site offline safety net when the Three.js CDN cannot load. */
(function(){
 const $=id=>document.getElementById(id);let t=0,paused=false,scenario='baseline',questions=[];
 async function post(path,data){return window.carelabAPI(path,{method:'POST',body:JSON.stringify(data)});}
 function bubble(str,type){let d=document.createElement('div');d.className='bubble '+type;d.textContent=str;$('chatlog').appendChild(d);$('chatlog').scrollTop=99999}
 function skeleton(){
  const container=$('scene');
  container.innerHTML=`<svg id="offline-rig" viewBox="0 0 600 500" preserveAspectRatio="xMidYMid meet" style="width:100%;height:100%;display:block" role="img" aria-label="2D 合成高齡虛擬人物，具有衣著、五官、上下肢動作的示意動畫">
  <defs>
  <linearGradient id="cardigan" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#6fc2b9"/><stop offset="1" stop-color="#337e7c"/></linearGradient>
  <linearGradient id="face" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#ecc4a7"/><stop offset="1" stop-color="#c8977e"/></linearGradient>
  <linearGradient id="slacks" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#536982"/><stop offset="1" stop-color="#35485d"/></linearGradient>
  <linearGradient id="floor" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#355a70" stop-opacity=".5"/><stop offset="1" stop-color="#243e53" stop-opacity="0"/></linearGradient>
  <filter id="rigshadow"><feGaussianBlur stdDeviation="9"/></filter>
  </defs>
  <ellipse cx="300" cy="450" rx="120" ry="22" fill="#000a19" opacity=".36" filter="url(#rigshadow)"/>
  <ellipse cx="300" cy="445" rx="160" ry="25" fill="url(#floor)" stroke="#478a94" stroke-opacity=".45"/>
  <path d="M130 445 H470" stroke="#75cfc4" stroke-opacity=".17" stroke-dasharray="4 8"/>
  <g id="figure">
   <g id="left-leg" style="transform-origin:276px 294px"><path d="M265 286 Q260 343 260 382 L255 427 Q255 439 270 439 L289 438 L291 378 L299 293Z" fill="url(#slacks)"/><path d="M254 422 Q272 411 290 425 Q297 439 304 444 Q310 451 292 453 L251 452 Q241 451 247 439Z" fill="#27394c"/></g>
   <g id="right-leg" style="transform-origin:322px 294px"><path d="M300 290 Q303 345 305 388 L306 432 Q307 440 322 439 L341 436 L336 378 L337 289Z" fill="url(#slacks)"/><path d="M306 422 Q325 411 341 426 Q348 439 358 444 Q365 451 341 453 L306 452 Q294 448 304 437Z" fill="#26374a"/></g>
   <path d="M269 270 L333 270 Q349 284 335 310 L266 310 Q251 288 269 270Z" fill="#35495e"/>
   <g id="left-arm" style="transform-origin:256px 191px"><path d="M251 190 Q226 195 220 233 L204 314 Q200 332 216 337 Q230 340 236 324 L265 238Z" fill="url(#cardigan)"/><path d="M203 322 Q207 317 221 323 L229 345 Q227 360 218 367 Q210 368 201 346Z" fill="url(#face)"/></g>
   <g id="right-arm" style="transform-origin:345px 191px"><path d="M345 190 Q375 195 380 233 L396 314 Q401 332 385 337 Q372 340 365 324 L333 238Z" fill="url(#cardigan)"/><path d="M384 322 Q393 317 397 325 L402 346 Q396 369 386 367 Q377 365 374 346Z" fill="url(#face)"/></g>
   <g id="body" style="transform-origin:298px 283px"><path d="M268 186 Q252 192 245 222 L253 284 Q259 303 296 304 L340 303 Q354 295 351 276 L352 221 Q347 190 329 187Z" fill="url(#cardigan)"/><path d="M289 190 L310 190 L323 302 L279 302Z" fill="#ece9df"/><path d="M282 190 L296 202 L276 284 L261 278Z" fill="#3b8584"/><path d="M316 188 L303 202 L325 284 L342 276Z" fill="#397c7d"/><path d="M287 194 L298 211 L307 194" fill="none" stroke="#fff" stroke-width="3" stroke-opacity=".55"/><circle cx="318" cy="250" r="3" fill="#d1d3be"/><circle cx="319" cy="275" r="3" fill="#d1d3be"/>
   <rect x="291" y="169" width="18" height="28" rx="7" fill="url(#face)"/>
   <g id="head" style="transform-origin:300px 150px">
    <ellipse cx="301" cy="132" rx="48" ry="55" fill="url(#face)"/>
    <ellipse cx="252" cy="143" rx="9" ry="14" fill="#d4aa90"/><ellipse cx="350" cy="143" rx="9" ry="14" fill="#d4aa90"/>
    <path d="M251 117 Q249 69 296 70 Q345 67 352 116 Q331 103 315 95 Q290 122 251 117Z" fill="#c3ced1"/>
    <path d="M258 105 Q253 81 277 76 M288 77 Q313 67 335 85 M318 91 Q338 91 350 109" fill="none" stroke="#94a5ad" stroke-width="8" stroke-linecap="round"/>
    <ellipse cx="281" cy="138" rx="13" ry="8" fill="#f9f4e9"/><ellipse cx="321" cy="138" rx="13" ry="8" fill="#f9f4e9"/>
    <circle cx="283" cy="138" r="5" fill="#4e6168"/><circle cx="319" cy="138" r="5" fill="#4e6168"/>
    <path d="M299 136 Q292 157 303 159" fill="none" stroke="#bd8c78" stroke-width="3" stroke-linecap="round"/>
    <path d="M285 172 Q301 181 317 170" fill="none" stroke="#a36d66" stroke-width="2.5" stroke-linecap="round"/>
    <rect x="266" y="126" width="31" height="23" rx="10" fill="none" stroke="#cbb896" stroke-width="3"/>
    <rect x="303" y="126" width="31" height="23" rx="10" fill="none" stroke="#cbb896" stroke-width="3"/>
    <path d="M297 137 H303 M267 137 L257 132 M334 137 L345 132" stroke="#cbb896" stroke-width="3" fill="none"/>
   </g></g>
  </g>
  <text x="25" y="475" fill="#a5d5db" font-size="13" font-family="sans-serif" opacity=".85">2D 模型示意 · Three.js 未載入</text>
  </svg>`;
  const figure=document.getElementById('figure'),l=document.getElementById('left-leg'),r=document.getElementById('right-leg'),la=document.getElementById('left-arm'),ra=document.getElementById('right-arm'),body=document.getElementById('body');
  function draw(){const pose=$('pose').value,w=t*2.6;let phase=Math.sin(w),bend=pose==='lean'?.14:0,sit=pose==='sit'?(1-Math.cos(t*1.5))*.5:0;
    figure.style.transform=`translateY(${-14*sit}px)`;
    body.style.transform=`rotate(${bend}rad)`;
    l.style.transform=`rotate(${pose==='walk'?-phase*.20:sit?-.72*sit:0}rad)`;
    r.style.transform=`rotate(${pose==='walk'?phase*.20:sit?.72*sit:0}rad)`;
    la.style.transform=`rotate(${pose==='walk'?phase*.17:0}rad)`;
    ra.style.transform=`rotate(${pose==='walk'?-phase*.17:0}rad)`;
    if(!paused)t+=.04;requestAnimationFrame(draw);
  }draw();$('render-status').textContent='高精細 2D 備援模式';
  for(const mode of ['front','side','three'])$('view-'+mode)?.addEventListener('click',()=>{document.querySelectorAll('.view-btn').forEach(b=>b.classList.toggle('selected',b.id==='view-'+mode));});
 }
 async function update(){const d=await window.carelabAPI('/api/frame?t='+Math.floor(t)+'&scenario='+scenario);$('hr').textContent=d.hr_bpm;$('spo').textContent=d.spo2_pct??'缺失';$('bp').textContent=d.bp_mmHg.join('/');$('gait').textContent=d.gait_m_s;$('timetxt').textContent=Math.floor(t)+' s';const c=$('ecg');let ctx=c.getContext('2d'),w=c.clientWidth,h=c.clientHeight;c.width=w;c.height=h;ctx.fillStyle='#f7fafa';ctx.fillRect(0,0,w,h);ctx.strokeStyle='#208e80';ctx.beginPath();for(let x=0;x<w;x++){let u=(x/110+t*.22)%1;let f=.01*Math.sin(u*6.28)+1.15*Math.exp(-(((u-.44)/.012)**2))+.18*Math.exp(-(((u-.71)/.09)**2));let y=h*.60-f*h*.38;if(!x)ctx.moveTo(x,y);else ctx.lineTo(x,y)}ctx.stroke();const ft=$('feet'),fctx=ft.getContext('2d');ft.width=ft.clientWidth;ft.height=ft.clientHeight;for(let x of [ft.width*.32,ft.width*.68]){let rad=fctx.createRadialGradient(x,ft.height/2,3,x,ft.height/2,55);rad.addColorStop(0,'#e99a57');rad.addColorStop(1,'#d5eee4');fctx.fillStyle=rad;fctx.beginPath();fctx.ellipse(x,ft.height/2,28,55,0,0,7);fctx.fill()}}
 async function analyze(){const a=await post('/api/analyze',{scenario});$('evidence').replaceChildren();for(let f of a.facts){const d=document.createElement('div');d.className='evidence-item';d.textContent=f.claim+' ｜ 來源 '+f.source;$('evidence').append(d)}$('issues').textContent=a.issues.join(' ｜ ')}
 function init(){if(window.__CARELAB_READY)return;window.__CARELAB_FALLBACK=true;skeleton();const days=['11/01','11/02','11/03','11/04','11/05','11/06','11/07'],vals=[15,20,null,10,25,20,15];$('walkchart').innerHTML=vals.map((v,i)=>`<div class="walkbar"><span class="v">${v??'缺失'}</span><div class="bar ${v===null?'missing':''}" style="height:${v==null?4:v*2.45}px"></div><small>${days[i]}</small></div>`).join('');$('scenario').onchange=e=>{scenario=e.target.value;analyze();update()};$('pause').onclick=()=>{paused=!paused;$('pause').textContent=paused?'繼續':'暫停'};$('time').oninput=e=>{t=+e.target.value;update()};$('analyze').onclick=analyze;
 $('send').onclick=send;$('question').onkeydown=e=>{if(e.key==='Enter')send()};document.querySelectorAll('.quick button').forEach(b=>b.onclick=()=>{$('question').value=b.dataset.q;send()});async function send(){const q=$('question').value.trim();if(!q)return;bubble(q,'user');questions.push(q);$('question').value='';try{let a=await post('/api/chat',{question:q,provider:$('provider').value});bubble(a.reply,'bot');$('chatstatus').textContent=a.mode+' / '+a.evidence;if($('voice').checked&&window.speechSynthesis){const u=new SpeechSynthesisUtterance(a.reply);u.lang='zh-TW';speechSynthesis.speak(u)}}catch(e){bubble('未取得模型回覆：'+e.message,'bot')}}$('mic').onclick=()=>{let R=window.SpeechRecognition||window.webkitSpeechRecognition;if(!R){$('chatstatus').textContent='瀏覽器不支援語音辨識';return}let r=new R();r.lang='zh-TW';r.onresult=e=>$('question').value=e.results[0][0].transcript;r.start()};
 $('fill').onclick=async()=>{const a=await post('/api/sbar',{scenario});for(let k of 'SBAR')$(k).value=a[k]};$('grade').onclick=async()=>{let a=await post('/api/grade',{fields:Object.fromEntries('SBAR'.split('').map(k=>[k,$(k).value]))});$('graderesult').textContent=a.score+'/100｜'+a.label};$('export').onclick=()=>{let b=new Blob([JSON.stringify({synthetic:true,scenario,questions,sbar:Object.fromEntries('SBAR'.split('').map(k=>[k,$(k).value]))},null,2)],{type:'application/json'}),u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download='carelab_learning_record.json';a.click();URL.revokeObjectURL(u)};update();analyze();setInterval(update,1000);}
 setTimeout(init,1800);
})();