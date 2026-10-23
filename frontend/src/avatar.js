import {Room,RoomEvent} from 'livekit-client';
import {clinicScene} from './immersive.js';
import {createMouthAudio} from './mouthAudio.js';
export function createAvatar(container,{actor,difficulty,onAction=()=>{}}={}){
 actor={...actor,name:actor.display_name||actor.name};
 container.replaceChildren();container.classList.add('photo-human-stage');
 const canvas=document.createElement('canvas');canvas.setAttribute('aria-label',actor.name+'擬真人物');container.appendChild(canvas);
 const status=document.createElement('span');status.className='human-status';status.textContent='人物載入中…';container.appendChild(status);
 const rig=clinicScene(canvas,{modelUrl:actor.realistic_model_url,interactive:true,onAction});
 rig.setBehavior(difficulty?.visual_state||'neutral');
 let disposed=false,frame,speaking=false,amplitude=0,start=performance.now(),mouth,attachEpoch=0;const observed=new Set();
 rig.ready.then(()=>{if(disposed)return;container.dataset.characterLoaded=actor.id;container.dataset.visualType='rigged-realistic-3d';status.textContent=actor.name+' · 聆聽中';}).catch(()=>{status.textContent='人物素材載入失敗，請重新整理';container.dataset.characterLoaded='failed';});
 function tick(){if(disposed)return;const weights=speaking&&mouth?mouth.weights:null;rig.setVisemes(weights);if(weights){for(const [k,v] of Object.entries(weights))if(v>.01)observed.add(k);container.dataset.visemeObserved=[...observed].join(',');container.dataset.visemePeak=String(Math.max(Number(container.dataset.visemePeak||0),...Object.values(weights)));}rig.renderAt((performance.now()-start)/1000,amplitude);frame=requestAnimationFrame(tick);}tick();
 return{available:true,ready:rig.ready,async attachAudio(context,source){const token=++attachEpoch;mouth?.dispose();mouth=null;try{const m=await createMouthAudio(context,source);if(disposed||token!==attachEpoch){m.dispose();return;}mouth=m;container.dataset.lipSync='mfcc-five-viseme';}catch(e){container.dataset.lipSync='amplitude-fallback';console.warn('嘴型分析無法啟動',e.message);}},setState(value){container.dataset.presence=value;rig.setPresence(value);const labels={listening:'正在聽您說',thinking:'思考您的回應',speaking:'正在回應',ready:'準備交談',closed:'會談結束'};status.textContent=labels[value]||'準備交談';},setEmotion(value){rig.setBehavior(value);},setSpeaking(v){speaking=v;if(!v)amplitude=0;rig.setPresence(v?'speaking':'listening');status.textContent=actor.name+(v?' · 說話中':' · 聆聽中');},setAmplitude(v){amplitude=Math.max(0,Math.min(1,v));},setPanorama:rig.setPanorama,orbit:rig.orbit,focusFace:rig.focusFace,reset:rig.reset,setTrust(){},dispose(){disposed=true;attachEpoch++;mouth?.dispose();cancelAnimationFrame(frame);rig.dispose();container.replaceChildren();}};
}
export async function connectVoice({url,token,observer},onStatus,onAmplitude=()=>{}){
  const room=new Room();
  room.on(RoomEvent.TrackSubscribed,track=>{if(track.kind==='audio'){const el=track.attach();el.dataset.clinicalVoice='1';document.body.appendChild(el);}});
  room.on(RoomEvent.TrackUnsubscribed,track=>track.detach().forEach(el=>el.remove()));
  room.on(RoomEvent.Disconnected,()=>{document.querySelectorAll('[data-clinical-voice]').forEach(x=>x.remove());onStatus('語音已中斷');});
  let timer;room.on(RoomEvent.ActiveSpeakersChanged,speakers=>onAmplitude(Math.max(0,...speakers.filter(p=>!p.isLocal).map(p=>p.audioLevel*4))));
  room.on(RoomEvent.Disconnected,()=>{clearInterval(timer);onAmplitude(0);});
  await room.connect(url,token);await room.startAudio();onStatus(observer?'已連線，唯讀收聽病患回覆':'已連線：送出確認文字後，病患回覆以 LiveKit 語音播放');return room;
}

export {connectAgentVoice} from './agentVoice.js';
