// Local recording + authenticated transcription. No third-party speech service.
export function createVoiceInput({sid,onText,onStatus,onError,onListening=()=>{},beforeListen=()=>{},inputStreamFactory=null,transcribeUrl=null,onEvent=()=>{}}){
 let stream,context,analyser,recorder,frame,timer,retryTimer,interruptFrame,disposed=false,enabled=false,cancelled=false,started=0,lastSound=0,heard=false,epoch=0,request,pending=false,cancelPermission;
 const label=(text,state)=>{onStatus(text,state);const el=document.querySelector('#voice-status');if(el)el.dataset.state=state;};
 function finish(cancel=false){cancelled=cancel;clearTimeout(retryTimer);cancelAnimationFrame(interruptFrame);if(cancel){epoch++;request?.abort();cancelPermission?.();}clearTimeout(timer);cancelAnimationFrame(frame);if(recorder?.state==='recording')recorder.stop();onListening(false);}
 function watchInterrupt(callback){
  cancelAnimationFrame(interruptFrame);if(!enabled||disposed||!analyser)return;
  const samples=new Uint8Array(analyser.fftSize);let loudSince=0;
  function check(){if(!enabled||disposed)return;analyser.getByteTimeDomainData(samples);const rms=Math.sqrt(samples.reduce((s,v)=>s+((v-128)/128)**2,0)/samples.length),now=performance.now();
   if(rms>.065){if(!loudSince)loudSince=now;if(now-loudSince>320){onEvent('interrupted',{source:'echo-cancelled-microphone'});callback();return;}}else loudSince=0;
   interruptFrame=requestAnimationFrame(check);
  }interruptFrame=requestAnimationFrame(check);
 }
 async function listen(){
  if(disposed||pending||recorder?.state==='recording')return;
  try{
   if((!inputStreamFactory&&!navigator.mediaDevices?.getUserMedia)||!window.MediaRecorder)throw Error('此瀏覽器無法錄音，請以 Chrome 或 Edge 開啟本機網址。');
   beforeListen();
   if(!stream){
    pending=true;const attempt=++epoch;let permissionTimer;
    label(inputStreamFactory?'準備測試音源（非實體麥克風）…':'等待瀏覽器麥克風權限；請在網址列允許。若內嵌瀏覽器沒有提示，請以 Chrome／Edge 開啟本機網址。','permission');
    try{stream=await Promise.race([(inputStreamFactory?inputStreamFactory():navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}})).then(s=>{if(disposed||attempt!==epoch){s.getTracks().forEach(t=>t.stop());throw new DOMException('錄音已取消','AbortError');}return s;}),new Promise((_,reject)=>{cancelPermission=()=>reject(new DOMException('錄音已取消','AbortError'));permissionTimer=setTimeout(()=>{epoch++;reject(Error('音源準備逾時；請確認音源或麥克風權限後重試。'));},20000);})]);}
    finally{pending=false;cancelPermission=null;clearTimeout(permissionTimer);}
   }
   if(disposed){stream.getTracks().forEach(t=>t.stop());return;}
   context??=new AudioContext();await context.resume();analyser??=context.createAnalyser();
   if(!analyser._source){analyser._source=context.createMediaStreamSource(stream);analyser._source.connect(analyser);analyser.fftSize=1024;}
   const mime=['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4'].find(t=>MediaRecorder.isTypeSupported(t));
   recorder=new MediaRecorder(stream,mime?{mimeType:mime}:{});const current=recorder,turn=++epoch,chunks=[];cancelled=false;heard=false;started=lastSound=performance.now();
   recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
   recorder.onstop=async()=>{
    if(turn!==epoch||cancelled||disposed||!chunks.length)return;
    if(!heard){if(enabled){label('我還在聽，您可以慢慢想。','listening');retryTimer=setTimeout(()=>{if(enabled&&!disposed&&turn===epoch)listen();},0);}return;}
    try{label('正在本機辨識語音…','transcribing');const blob=new Blob(chunks,{type:current.mimeType});request=new AbortController();
     onEvent('recorded',{bytes:blob.size,mime:blob.type,heard,elapsedMs:performance.now()-started});
     const response=await fetch(transcribeUrl||`/api/sessions/${sid}/transcribe`,{method:'POST',headers:{'Content-Type':blob.type},body:blob,signal:request.signal});
     const data=await response.json();if(!response.ok)throw Error(data.detail||'語音辨識失敗');if(disposed||turn!==epoch)return;
     onEvent('transcribed',{...data});label('辨識完成，可確認文字或自動送出。','ready');onText(data.text);
    }catch(e){if(!disposed&&turn===epoch&&e.name!=='AbortError'){if(enabled&&/沒有辨識到清楚語音|另一段語音辨識中/.test(e.message)){label('還沒聽清楚，我會繼續聽。','listening');retryTimer=setTimeout(()=>{if(enabled&&!disposed&&turn===epoch)listen();},800);}else{enabled=false;label(e.message,'error');onError(e);}}}
   };
   recorder.start(250);onListening(true);label('正在聆聽，您可以直接說話。停頓後自動回應。','listening');
   const samples=new Uint8Array(analyser.fftSize);
   function level(){if(disposed||recorder.state!=='recording')return;analyser.getByteTimeDomainData(samples);const rms=Math.sqrt(samples.reduce((s,v)=>s+((v-128)/128)**2,0)/samples.length),now=performance.now();
    if(rms>.025){heard=true;lastSound=now;}const meter=document.querySelector('#mic-level');if(meter)meter.value=Math.min(1,rms*8);
    if(heard&&now-lastSound>1700&&now-started>1900){finish();return;}if(!heard&&now-started>12000){finish();return;}frame=requestAnimationFrame(level);
   }level();timer=setTimeout(()=>finish(),59000);
  }catch(e){if(disposed||e.name==='AbortError')return;enabled=false;const messages={NotAllowedError:'麥克風未獲允許，請在網址列開啟麥克風權限後重試。',NotFoundError:'找不到麥克風，請接上裝置後重試。',NotReadableError:'麥克風正被其他程式使用，請關閉後重試。'};label(messages[e.name]||e.message,'error');onError(Error(messages[e.name]||e.message));}
 }
 return {async start(){enabled=true;await listen();},watchInterrupt,finish(){finish();},stop(){enabled=false;finish(true);stream?.getTracks().forEach(t=>t.stop());stream=null;context?.close().catch(()=>{});context=null;analyser=null;label('語音對話已停止。','idle');},pause(){finish(true);},resume(){cancelAnimationFrame(interruptFrame);if(enabled&&!disposed)return listen();},get enabled(){return enabled;},dispose(){disposed=true;enabled=false;finish(true);stream?.getTracks().forEach(t=>t.stop());context?.close().catch(()=>{});}};
}
