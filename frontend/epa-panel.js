import {epaAnnotation,bodyRegionSummary} from './epa-content.js?v=5.6.1-r2';
import {poseMeasurements} from './pose-panel.js?v=5.6.1-r2';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const time=x=>`${Math.floor(x/60)}:${String(Math.floor(x%60)).padStart(2,'0')}`;
export function epaLibraryPanel(library,sid,{readonly=false}={}){
 if(!library?.unlocked)return '';
 return `<section class="epa-library" data-sid="${sid}" data-readonly="${readonly}"><h3>Level 4 · EPA影格、動作與醫病互動解析</h3><p>先看完整段落，再以每張原圖、骨架、關節與肢段、對話功能、動作意義及EPA觀察點核對。</p><p class="source">${esc(library.notice||'')} ${esc(library.scope||'')}</p>${library.analyses?.length?`<label>選擇已完成EPA分析的影片<select class="epa-select">${library.analyses.map(a=>`<option value="${esc(a.clip_id)}">${esc(a.title)} · ${a.frame_count.toLocaleString()}格 · ${a.projection==='flat'?'一般影片':'360固定視角'}</option>`).join('')}</select></label><p class="epa-status" role="status">讀取教案解析…</p><div class="epa-report"></div>`:'<p class="note">預先分析尚未完成或原始教材未安裝，完成後可在此直接檢視。下方仍可自行選取區間作逐格分析。</p>'}</section>`;
}
export async function mountEPA(root,{initialClip,initialFrame=0}={}){
 if(!root)return ()=>{};
 const select=root.querySelector('.epa-select');if(!select)return ()=>{};
 const sid=Number(root.dataset.sid),readonly=root.dataset.readonly==='true',status=root.querySelector('.epa-status'),body=root.querySelector('.epa-report');
 let disposed=false,sequence=0,report,current,number=initialFrame,view,video;
 const api=async path=>{const r=await fetch(path);const d=await r.json();if(!r.ok)throw Error(d.detail||'分析讀取失敗');return d;};
 const base=()=>`/api/sessions/${sid}/epa-lessons/${encodeURIComponent(select.value)}`;
 const cleanupMedia=()=>{view?.dispose();view=null;if(video){video.pause();video.removeAttribute('src');video.load();video=null;}};
 async function draw(next){
  const seq=++sequence;number=Math.max(report.first_frame,Math.min(report.last_frame,Math.round(next)));current=null;const button=root.querySelector('.epa-save');if(button)button.disabled=true;
  try{
   const f=await api(base()+`/frames/${number}`);if(disposed||seq!==sequence)return;current=f;
   root.querySelector('.epa-position').textContent=`${time(f.seconds)} · ${f.seconds.toFixed(3)}秒 · 第${f.frame}格／${report.frame_count}格`;
   root.querySelector('.epa-slider').value=f.frame;root.querySelector('.epa-number').value=f.frame;
   root.querySelector('.epa-image').src=base()+`/frames/${f.frame}/image?overlay=${root.querySelector('.epa-overlay').checked}`;
   root.querySelector('.epa-explanation').innerHTML=epaAnnotation(f.annotation,f.reference_keyframe)+bodyRegionSummary(f.poses)+poseMeasurements(f.poses);
   video?.pause();if(video?.readyState)video.currentTime=f.seconds;
   if(button)button.disabled=false;status.textContent='已載入此格的原始證據與教學註記；不自動推定動作意圖或能力等級。';
  }catch(e){if(!disposed)status.textContent=e.message;}
 }
 async function change(){
  sequence++;current=null;cleanupMedia();body.innerHTML='';status.textContent='核對來源並讀取預先分析…';
  try{
   const clip=select.value;const data=await api(base()+'/report');if(disposed||select.value!==clip)return;report=data;
   body.innerHTML=`<h4>${esc(data.title)}</h4><p>全片 ${data.frame_count.toLocaleString()}格，${data.detection_frames.toLocaleString()}格偵測到人體 · ${data.fps.toFixed(3)} fps · ${data.analyzed_every_frame?'每格均已解碼分析':'未標示完整分析'}</p><p class="source">影片 ${esc(data.source_sha256.slice(0,12))} · 模型 ${esc(data.model_sha256.slice(0,12))} · ${esc(data.version)}。${data.projection==='flat'?'一般影片原構圖。':`固定視角 水平${data.view.yaw}°／垂直${data.view.pitch}°／視野${data.view.fov}°，未涵蓋球面所有方向。`}</p><details><summary>EPA段落總覽 · ${data.segments.length}段</summary><div class="epa-segments">${data.segments.map(s=>`<article><button type="button" data-epa-frame="${Math.round(s.start*data.fps)}">${time(s.start)}–${time(s.end)} · ${esc(s.title)}</button>${epaAnnotation(s)}</article>`).join('')}</div></details><details><summary>代表性關鍵影格 · ${data.keyframes.length}張</summary><p>代表格用於導覽；下方滑桿可以逐一檢視全片所有影格，沒有省略其他影格。</p><div class="epa-keyframes">${data.keyframes.map(k=>`<button type="button" data-epa-frame="${k.frame}"><img loading="lazy" src="${base()}/frames/${k.frame}/image?overlay=false" alt="${esc(k.title||k.id)}"><span>${esc(k.id)} · ${time(k.seconds)} · ${esc(k.title||k.visible_action||'代表格')}</span></button>`).join('')}</div></details><div class="row"><button type="button" class="epa-prev">上一個EPA影格</button><button type="button" class="epa-next">下一個EPA影格</button><output class="epa-position"></output></div><input class="epa-slider" type="range" min="${data.first_frame}" max="${data.last_frame}" step="1" value="${data.first_frame}" aria-label="EPA完整影片逐格進度"><label>指定EPA影格編號<input class="epa-number" type="number" min="${data.first_frame}" max="${data.last_frame}" step="1" value="${data.first_frame}"></label><button type="button" class="epa-jump">定位EPA影格</button><label class="checkline"><input class="epa-overlay" type="checkbox" checked>顯示EPA骨架（取消可看原圖）</label><div class="grid2 epa-media"><section><h4>選定影格與骨架</h4><img class="epa-image pose-preview" alt="選定EPA影格原圖與模型骨架"></section><section><h4>原始影片與前後語音</h4><video class="epa-video" controls playsinline preload="metadata" aria-label="EPA原始影片"></video><canvas class="epa-panorama" hidden aria-label="EPA原始環景固定分析視角"></canvas><button type="button" class="epa-play">播放原片前後脈絡</button><p class="source">原片播放時，骨架保留在選定證據格；請暫停後點選影格重新對齊。${esc(data.dialogue_status)}</p></section></div><div class="epa-explanation"></div><p class="source">${esc(data.limitation)}</p>${readonly?'<p>此頁供回看，請回原訓練頁保存學員觀察或教師回饋。</p>':`<form class="epa-note-form"><label>EPA動作、對話關聯與目的判讀<textarea name="observation" required minlength="5" maxlength="2000" placeholder="區分本格可見動作、可能目的、EPA觀察點與還需核對的語音或前後畫面"></textarea></label><button class="epa-save" disabled>保存EPA影格觀察給教師</button><p class="epa-save-status" role="status"></p></form>`}<details><summary>解析來源與核定狀態</summary><p>${esc(data.annotation_status)}</p><p>${esc(data.competency_codes_note)}</p>${data.annotation_sources.map(s=>`<p>${esc(s.file||s.title)} · ${esc(s.sha256?.slice(0,12)||'')}</p>`).join('')}<a href="${base()}/report" target="_blank" rel="noopener">開啟本片解析JSON</a> · <a href="${base()}/download">下載完整EPA圖文解析報告</a></details>`;
   video=root.querySelector('.epa-video');video.src=data.media_url;
   if(data.projection!=='flat'){
    const {mountPanorama}=await import('./vendor/panorama.bundle.js?v=5.6.1-r2');if(disposed)return;
    video.hidden=true;const canvas=root.querySelector('.epa-panorama');canvas.hidden=false;view=mountPanorama(canvas,video,()=>{});view.setAngle(data.view);
   }
   video.addEventListener('loadedmetadata',()=>{if(current)video.currentTime=current.seconds;},{once:true});
   root.querySelector('.epa-play').onclick=()=>{if(video.paused)video.play().catch(e=>status.textContent=e.message);else video.pause();};
   root.querySelector('.epa-prev').onclick=()=>draw(number-1);root.querySelector('.epa-next').onclick=()=>draw(number+1);
   root.querySelector('.epa-slider').onchange=e=>draw(Number(e.target.value));root.querySelector('.epa-number').onchange=e=>draw(Number(e.target.value));root.querySelector('.epa-jump').onclick=()=>draw(Number(root.querySelector('.epa-number').value));root.querySelector('.epa-number').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();draw(Number(e.target.value));}};
   root.querySelector('.epa-overlay').onchange=()=>{if(current)root.querySelector('.epa-image').src=base()+`/frames/${current.frame}/image?overlay=${root.querySelector('.epa-overlay').checked}`;};
   for(const b of root.querySelectorAll('[data-epa-frame]'))b.onclick=()=>draw(Number(b.dataset.epaFrame));
   root.querySelector('.epa-note-form')?.addEventListener('submit',async e=>{
    e.preventDefault();e.stopImmediatePropagation();if(!current)return;const selected=current,form=e.currentTarget,button=form.querySelector('button'),saveStatus=root.querySelector('.epa-save-status');button.disabled=true;
    try{
     const response=await fetch(`/api/sessions/${sid}/frame-notes`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({clip_id:select.value,seconds:selected.seconds,yaw:data.view.yaw,pitch:data.view.pitch,fov:data.view.fov,epa_analysis_id:data.id,analysis_frame:selected.frame,observation:form.elements.observation.value})});const result=await response.json();if(!response.ok)throw Error(result.detail||'保存失敗');saveStatus.textContent='已保存EPA影格、原始觀察、解析版本與骨架證據，教師可回饋；不改寫正式分數。';form.reset();
    }catch(err){saveStatus.textContent=err.message;}finally{button.disabled=false;}
   },{capture:true});
   await draw(number);
  }catch(e){if(!disposed)status.textContent=e.message;}
 }
 if(initialClip&&[...select.options].some(o=>o.value===initialClip))select.value=initialClip;
 select.onchange=()=>{number=0;change();};await change();
 return ()=>{disposed=true;sequence++;cleanupMedia();};
}
