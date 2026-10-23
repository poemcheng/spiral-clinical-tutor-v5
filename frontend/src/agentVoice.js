import {Room,RoomEvent} from 'livekit-client';

export async function connectAgentVoice(info,{avatar,context,onReply,onStatus}){
 const room=new Room(),elements=[];let source;
 room.on(RoomEvent.TrackSubscribed,(track)=>{if(track.kind!=='audio')return;const el=track.attach();el.dataset.clinicalVoice='agent';elements.push(el);document.body.append(el);el.play().catch(()=>onStatus('請點開始語音以播放聲音。'));
  const stream=new MediaStream([track.mediaStreamTrack]);source=context.createMediaStreamSource(stream);avatar.attachAudio(context,source);
 });
 room.on(RoomEvent.ParticipantAttributesChanged,(changed,p)=>{if(!p.identity.startsWith('agent-'))return;const phase=changed['lk.agent.state'];if(phase){avatar.setSpeaking(phase==='speaking');avatar.setState(phase);onStatus(({listening:'正在聽您說',thinking:'正在思考您的話',speaking:'角色回覆中；您可直接說話打斷'})[phase]||phase);}});
 room.on(RoomEvent.DataReceived,(payload,participant,kind,topic)=>{if(topic==='clinical-agent'&&participant?.identity.startsWith('agent-')){try{const data=JSON.parse(new TextDecoder().decode(payload));if(data.type==='clinical-reply')onReply(data);}catch{onStatus('語音會談訊息無法讀取，請重新連線。');}}});
 room.on(RoomEvent.Disconnected,()=>{source?.disconnect();elements.forEach(e=>e.remove());avatar.setSpeaking(false);onStatus('即時語音會談已停止。');});
 try{await room.connect(info.url,info.token);await room.startAudio();await room.localParticipant.setMicrophoneEnabled(true,{echoCancellation:true,noiseSuppression:true,autoGainControl:true});onStatus('連續語音已啟動，您可以開始說話。');return room;}
 catch(e){await room.disconnect();throw e;}
}
