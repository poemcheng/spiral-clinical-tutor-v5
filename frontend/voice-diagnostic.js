import {createVoiceInput} from '/static/voice.js?v=5.5.0';
import {createAvatar} from '/static/vendor/avatar.bundle.js?v=5.5.0';
const $=s=>document.querySelector(s),sid=Number(new URLSearchParams(location.search).get('session'));
let avatar,controller,context,destination,source,frame,watchdog,active=false,report;
let audio=$('#reply');const expected=['您好，請說明目前需要一起確認的資料。','謝謝您的說明，還有哪些資訊需要再核對？'];
const update=()=>{$('#report').textContent=JSON.stringify(report,null,2);};
function event(kind,data={}){report.events.push({kind,ms:Math.round(performance.now()-report.started),...data});update();}
function fail(error){if(!active)return;event('error',{message:error.message});report.passed=false;finish('測試未通過：'+error.message);}
function finish(label){active=false;clearTimeout(watchdog);controller?.stop();source?.stop();source=null;audio.pause();avatar?.setSpeaking(false);cancelAnimationFrame(frame);context?.close().catch(()=>{});context=null;$('#start').disabled=false;$('#stop').disabled=true;$('#result').textContent=label;report.finishedAt=new Date().toISOString();report.lipSync=$('#avatar').dataset.lipSync;report.observedVisemes=$('#avatar').dataset.visemeObserved;report.visemePeak=Number($('#avatar').dataset.visemePeak||0);update();}
async function json(url,body){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw Error(d.detail||'服務錯誤');return d;}
function similarity(a,b){const norm=x=>x.replace(/[^\p{L}\p{N}]/gu,'');a=norm(a);b=norm(b);const row=Array(b.length+1).fill(0);for(const c of a){let last=0;for(let j=1;j<=b.length;j++){const before=row[j];row[j]=c===b[j-1]?last+1:Math.max(row[j],row[j-1]);last=before;}}return row[b.length]/Math.max(a.length,b.length,1);}
try{if(!sid)throw Error('請從 Step 4 的語音自動驗證連結進入。');const r=await fetch('/api/characters');if(!r.ok)throw Error('請先登入學員帳號。');const data=await r.json();const actor=data.actors.find(a=>a.id===(new URLSearchParams(location.search).get('actor')||'wang-pt'));avatar=createAvatar($('#avatar'),{actor});await avatar.ready;$('#voice-status').textContent='立體骨架角色就緒，請按開始。';}catch(e){$('#result').textContent=e.message;$('#start').disabled=true;}
$('#start').onclick=async()=>{
 if(active)return;const fresh=audio.cloneNode(false);audio.replaceWith(fresh);audio=fresh;active=true;$('#start').disabled=true;$('#stop').disabled=false;$('#turns').replaceChildren();
 report={test:'continuous-voice-v5.5.0',testId:crypto.randomUUID().replaceAll('-',''),inputSource:'controlled-synthetic-audio',physicalMicrophoneTested:false,formalLearningEvidence:false,started:performance.now(),startedAt:new Date().toISOString(),rounds:[],events:[],passed:false};update();
 try{
  context=new AudioContext();await context.resume();destination=context.createMediaStreamDestination();
  const analyser=context.createAnalyser();analyser.fftSize=1024;const audioSource=context.createMediaElementSource(audio);audioSource.connect(analyser);analyser.connect(context.destination);await avatar.attachAudio(context,audioSource);
  const buffers=[];for(let turn=1;turn<=2;turn++){const r=await fetch(`/api/sessions/${sid}/voice-diagnostic/input/${turn}`);if(!r.ok)throw Error('測試音源服務未就緒');buffers.push(await context.decodeAudioData(await r.arrayBuffer()));}
  controller=createVoiceInput({sid,transcribeUrl:`/api/sessions/${sid}/voice-diagnostic/transcribe`,inputStreamFactory:async()=>destination.stream,
   onStatus:text=>{$('#voice-status').textContent=text;},onError:fail,
   onEvent:(kind,data)=>{if(!active)return;Object.assign(report.rounds.at(-1),kind==='recorded'?{recording:data}:{recognition:data,similarity:similarity(data.text,expected[report.rounds.length-1])});event(kind,data);},
   onListening:value=>{if(!active||!value)return;const index=report.rounds.length;if(index>=2){fail(Error('測試輪數異常'));return;}report.rounds.push({turn:index+1,expected:expected[index],inputSeconds:buffers[index].duration,maxOutputRms:0,playbackEnded:false});event(index?'resumed':'listening',{turn:index+1});source=context.createBufferSource();source.buffer=buffers[index];source.connect(destination);source.start(context.currentTime+.2);source.onended=()=>{source=null;};$('#result').textContent=`第 ${index+1} / 2 輪：錄音與停頓偵測`;},
   onText:async text=>{if(!active)return;controller.pause();try{const round=report.rounds.at(-1);const p=document.createElement('p');p.textContent=`第 ${round.turn} 輪辨識：${text}`;$('#turns').append(p);$('#result').textContent=`第 ${round.turn} / 2 輪：實際 AI 回覆與語音合成`;const reply=await json(`/api/sessions/${sid}/voice-diagnostic/reply`,{text,test_id:report.testId});if(!active)return;round.reply=reply;event('ai-reply',{turn:round.turn,source:reply.source,model:reply.model,text:reply.text});const q=document.createElement('p');q.textContent=`角色回覆：${reply.text}`;$('#turns').append(q);audio.src=reply.audio_url;
    audio.onplay=()=>{avatar.setSpeaking(true);event('playback-started',{turn:round.turn});const samples=new Uint8Array(analyser.fftSize);function sync(){if(!active||audio.paused||audio.ended)return;analyser.getByteTimeDomainData(samples);const rms=Math.sqrt(samples.reduce((sum,x)=>sum+((x-128)/128)**2,0)/samples.length);round.maxOutputRms=Math.max(round.maxOutputRms,rms);avatar.setAmplitude(Math.min(1,rms*7));frame=requestAnimationFrame(sync);}sync();};
    audio.onended=()=>{avatar.setSpeaking(false);round.playbackEnded=true;round.outputSeconds=audio.duration;event('playback-ended',{turn:round.turn,seconds:audio.currentTime});if(round.turn<2){controller.resume();}else{report.passed=report.rounds.length===2&&report.rounds.every(r=>r.recording?.bytes>0&&r.recording.heard&&r.similarity>=.6&&r.reply?.source==='ollama'&&r.playbackEnded&&r.maxOutputRms>.005)&&report.events.some(e=>e.kind==='resumed');finish(report.passed?'通過：兩輪錄音 → 辨識 → AI → 語音 → 接續收音':'測試未通過：請檢查報告');}};
    audio.onerror=()=>fail(Error('角色語音載入失敗'));await audio.play();
   }catch(e){fail(e);}}
  });
  watchdog=setTimeout(()=>fail(Error('完整流程超過四分鐘')),240000);await controller.start();
 }catch(e){fail(e);}
};
$('#stop').onclick=()=>{if(active){event('cancelled');finish('已停止測試');}};
window.addEventListener('pagehide',()=>{active=false;clearTimeout(watchdog);controller?.dispose();source?.stop();audio.pause();context?.close().catch(()=>{});avatar?.dispose();cancelAnimationFrame(frame);});
