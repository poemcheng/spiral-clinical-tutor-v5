import {poseMeasurements} from './pose-panel.js?v=5.4.1';
import {stepExplanation,teachingForFrame} from './learning-levels.js?v=5.4.1';
import {mountPanorama} from './vendor/panorama.bundle.js?v=5.4.1';
const $=s=>document.querySelector(s),q=new URLSearchParams(location.search),sid=q.get('session'),id=q.get('analysis');
let result,index=0,view;
try{
 if(!/^\d+$/.test(sid||'')||!/^[a-f0-9]{32}$/.test(id||''))throw Error('無效分析連結。');
 const response=await fetch(`/api/sessions/${sid}/pose-analysis/${id}/result`),data=await response.json();if(!response.ok)throw Error(data.detail||'讀取失敗');result=data;
 $('#review-body').hidden=false;$('#review-title').textContent=data.source.title;
 $('#review-source').textContent=`${data.frame_count}格 · ${data.fps.toFixed(3)} fps · ${data.model} · 影片 ${data.actual_video_sha256.slice(0,12)} · 模型 ${data.model_sha256.slice(0,12)}`;
 const video=$('#review-video');video.src=`/api/sessions/${sid}/resources/video/${encodeURIComponent(data.source.id)}`;
 const flat=data.source.projection==='flat';$('#review-source-heading').textContent=flat?'原始一般影片 · 核對前後動作與現場語音':'原始360影片 · 核對前後畫面與現場語音';
 if(flat){video.hidden=false;video.controls=true;$('#review-panorama').hidden=true;$('#review-reset').hidden=true;}else{view=mountPanorama($('#review-panorama'),video,()=>{});view.setAngle(data.view);}
 $('#review-overlay').disabled=!data.raw_frames_available;$('#review-overlay').onchange=()=>draw(false);
 $('#review-slider').max=data.frames.length-1;
 $('#review-play').onclick=()=>{if(video.paused)video.play().catch(e=>$('#review-status').textContent=e.message);else video.pause();};video.addEventListener('play',()=>$('#review-play').textContent='暫停原始影片');video.addEventListener('pause',()=>$('#review-play').textContent='播放原始影片（含現場語音）');$('#review-video-seek').oninput=e=>{if(Number.isFinite(video.duration))video.currentTime=Number(e.target.value)/100*video.duration;};video.addEventListener('timeupdate',()=>{$('#review-video-time').textContent=video.currentTime.toFixed(3)+'秒';$('#review-video-seek').value=video.duration?video.currentTime/video.duration*100:0;});
 function draw(seek=true){const f=data.frames[index];$('#review-position').textContent=`${f.seconds.toFixed(3)}秒 · 第${f.frame}格`;$('#review-image').src=`/api/sessions/${sid}/pose-analysis/${id}/frames/${f.frame}?overlay=${$('#review-overlay').checked}`;$('#review-slider').value=index;$('#review-metrics').innerHTML=stepExplanation(teachingForFrame(data,f))+poseMeasurements(f.poses);if(seek){video.pause();if(video.readyState)video.currentTime=f.seconds;}}
 $('#review-next').onclick=()=>{index=Math.min(data.frames.length-1,index+1);draw();};$('#review-prev').onclick=()=>{index=Math.max(0,index-1);draw();};$('#review-slider').oninput=e=>{index=Number(e.target.value);draw();};$('#review-reset').onclick=()=>view?.setAngle(data.view);
 video.addEventListener('timeupdate',()=>{if(video.paused)return;const n=Math.round(video.currentTime*data.fps)-data.first_frame;if(n>=0&&n<data.frames.length){if(n!==index){index=n;draw(false);}$('#review-status').textContent='播放原始影片，骨架取自本次逐格分析結果。';}else $('#review-status').textContent='目前在分析區間外；骨架停在最後檢視的分析影格，未推算區間外動作。';});
 video.addEventListener('seeking',()=>$('#review-status').textContent='原始影片定位中，請待畫面完成更新後再判讀。');video.addEventListener('seeked',()=>{const n=Math.round(video.currentTime*data.fps)-data.first_frame;if(n>=0&&n<data.frames.length){index=n;draw(false);$('#review-status').textContent='定位完成：原始影片與骨架影格已對齊，可核對前後脈絡。';}else $('#review-status').textContent='目前原始影片在分析區間外；骨架停在最後檢視的分析影格。';});
 $('#review-limit').textContent=data.limitation;$('#review-status').textContent='登入與來源版本核對完成；可逐格覆核並聆聽前後現場語音。';video.addEventListener('loadedmetadata',()=>draw(),{once:true});draw();
}catch(e){$('#review-status').textContent=e.message+' 請使用原訓練頁登入後再開啟此連結。';}
window.addEventListener('pagehide',()=>view?.dispose(),{once:true});
