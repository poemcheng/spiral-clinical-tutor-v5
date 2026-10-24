const sid=new URLSearchParams(location.search).get('session'),isBranch=new URLSearchParams(location.search).get('activity')==='branching';
const status=document.getElementById('status'),base='/api/sessions/'+sid+(isBranch?'/branching':'/h5p');
let saved,runId,instance,chain=Promise.resolve();
async function mountedInstance(){
 const deadline=Date.now()+15000;
 while(Date.now()<deadline){
  const candidate=document.querySelector('#h5p-container iframe')?.contentWindow?.H5P?.instances?.[0]||window.H5P?.instances?.[0];
  if(candidate?.on&&candidate?.getCurrentState)return candidate;
  await new Promise(resolve=>setTimeout(resolve,50));
 }
 throw Error('情境播放器未完成初始化，請重新載入。');
}
function notify(){parent.postMessage({type:'branching-progress',sid:Number(sid)},location.origin);}
function resize(){parent.postMessage({type:'h5p-height',sid:Number(sid),height:Math.ceil(document.body.getBoundingClientRect().height)+10},location.origin);}
function save(verb){
 if(saved.readonly)return;
 const current=instance?.getCurrentState?.()||{};
 const body=isBranch?{event_id:crypto.randomUUID(),run_id:runId,content_version:saved.content_version,verb,state:{userPath:current.userPath||[]}}:null;
 if(!body)return;
 chain=chain.then(async()=>{
  const res=await fetch(base+'/evidence',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const result=await res.json();
  if(!res.ok)throw Error(result.detail||'分支進度尚未保存');
  status.textContent='分支路徑已保存；重練歷程保留，正式分數不變。';notify();
 }).catch(error=>{status.textContent='保存未完成：'+error.message;});
}
try{
 if(!/^\d+$/.test(sid||''))throw Error('未知訓練');
 const response=await fetch(base+'/state');saved=await response.json();if(!response.ok)throw Error(saved.detail);
 runId=saved.run_id||crypto.randomUUID().replaceAll('-','');
 await new H5PStandalone.H5P(document.getElementById('h5p-container'),{h5pJsonPath:base,contentJsonPath:base+'/content',librariesPath:'/static/vendor/h5p-libraries',frameJs:'/static/vendor/h5p/frame.bundle.js',frameCss:'/static/vendor/h5p/styles/h5p.css',saveFreq:60,contentUserData:[{state:JSON.stringify(saved.state||{})}]});
 instance=await mountedInstance();
 status.textContent=saved.readonly?'歷程回顧模式：此頁操作不寫入訓練紀錄。':isBranch?'分支情境已載入；每個選擇會帶往不同回饋或結局。':'H5P 練習已載入；不列入正式能力分數。';
 if(isBranch){
  for(const verb of ['started','navigated'])instance.on(verb,()=>queueMicrotask(()=>save(verb)));
  instance.on('restarted',()=>{runId=crypto.randomUUID().replaceAll('-','');queueMicrotask(()=>save('restarted'));});
 }else{
  H5P.externalDispatcher.on('xAPI',async event=>{
   if(saved.readonly)return;const statement=event.data.statement;
   const res=await fetch(base+'/evidence',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({event_id:crypto.randomUUID(),content_version:saved.content_version,verb:statement.verb?.id?.split('/').pop()||'interacted',result:statement.result||{},state:instance?.getCurrentState?.()||{}})});
   status.textContent=res.ok?'練習事件與進度已保存（非正式評分）。':'保存未完成，請返回平台重新載入。';
  });
 }
 new ResizeObserver(resize).observe(document.body);resize();
}catch(error){status.textContent='H5P 載入失敗：'+error.message;}
