import {Room,RoomEvent} from 'livekit-client';
import {photoHuman} from './photoHuman.js';
export function createAvatar(container,{actor,onAction=()=>{}}={}){
 container.replaceChildren();container.classList.add('photo-human-stage');
 const canvas=document.createElement('canvas');canvas.setAttribute('aria-label',actor.name+'擬真人物');container.appendChild(canvas);
 const status=document.createElement('span');status.className='human-status';status.textContent='人物載入中…';container.appendChild(status);
 const rig=photoHuman(canvas,{atlasUrl:actor.atlas_url,face:actor.face,fit:'cover'});
 let disposed=false,frame,speaking=false,amplitude=0,start=performance.now();
 rig.ready.then(()=>{if(disposed)return;container.dataset.characterLoaded=actor.id;container.dataset.visualType='photoreal-portrait';status.textContent=actor.name+' · 聆聽中';}).catch(()=>{status.textContent='人物素材載入失敗，請重新整理';container.dataset.characterLoaded='failed';});
 function tick(){if(disposed)return;rig.renderAt((performance.now()-start)/1000,amplitude);frame=requestAnimationFrame(tick);}tick();
 const identify=()=>onAction('identify');canvas.addEventListener('click',identify);
 return{available:true,ready:rig.ready,setSpeaking(v){speaking=v;if(!v)amplitude=0;status.textContent=actor.name+(v?' · 說話中':' · 聆聽中');},setAmplitude(v){amplitude=Math.max(0,Math.min(1,v));status.textContent=actor.name+(amplitude>.025?' · 說話中':' · 聆聽中');},setTrust(){},dispose(){disposed=true;cancelAnimationFrame(frame);canvas.removeEventListener('click',identify);rig.dispose();container.replaceChildren();}};
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
