import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin } from '@pixiv/three-vrm';
const $=id=>document.getElementById(id);
let scene, camera, renderer, controls, human, vrm=null, clock=new THREE.Clock(),paused=false,t=0,scenario='baseline',pose='stand',questions=[];
const api=(path, options={})=>window.carelabAPI(path,options);
const post=(path,data)=>api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
function createAvatar(){
  const root=new THREE.Group();const mat=(c,metal=0)=>new THREE.MeshStandardMaterial({color:c,roughness:.85,metalness:metal});
  const shirt=mat('#418f8a'),pant=mat('#344e62'),skin=mat('#ccaa90'),hair=mat('#aab1b1'),shoe=mat('#454e57');
  function ell(parent,w,h,d,m,x,y,z){const mesh=new THREE.Mesh(new THREE.SphereGeometry(1,16,12),m);mesh.scale.set(w,h,d);mesh.position.set(x,y,z);parent.add(mesh);return mesh}
  const trunk=new THREE.Group();trunk.position.y=1.62;root.add(trunk);
  ell(trunk,.33,.48,.2,shirt,0,-.10,0);ell(trunk,.22,.23,.21,skin,0,.48,0);ell(trunk,.235,.105,.215,hair,0,.648,-.025);
  const glasses=mat('#788b92');for(const s of [-1,1]){const ring=new THREE.Mesh(new THREE.TorusGeometry(.086,.009,8,20),glasses);ring.position.set(s*.115,.49,.198);trunk.add(ring)}
  let parts={arms:[],legs:[],trunk,root};
  for(const s of [-1,1]){
    const arm=new THREE.Group();arm.position.set(s*.32,.19,0);trunk.add(arm);ell(arm,.115,.30,.12,shirt,0,-.30,0);ell(arm,.083,.14,.085,skin,0,-.65,0);parts.arms.push({g:arm,s});
    const leg=new THREE.Group();leg.position.set(s*.16,.99,0);root.add(leg);ell(leg,.13,.45,.15,pant,0,-.43,0);ell(leg,.13,.15,.21,shoe,0,-.90,.10);parts.legs.push({g:leg,s});
  }
  root.userData.parts=parts;root.scale.setScalar(1);return root;
}
function initScene(){const mount=$('scene');scene=new THREE.Scene();scene.background=new THREE.Color('#e4efed');camera=new THREE.PerspectiveCamera(45,1,.1,100);camera.position.set(3.3,2.2,4.5);
  renderer=new THREE.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio||1,2));renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.shadowMap.enabled=true;mount.appendChild(renderer.domElement);scene.add(new THREE.HemisphereLight(0xffffff,0xa1c0bd,2.2));const light=new THREE.DirectionalLight(0xffffff,2.4);light.position.set(3,6,4);light.castShadow=true;scene.add(light);
  const ground=new THREE.Mesh(new THREE.CylinderGeometry(2.1,2.1,.07,64),new THREE.MeshStandardMaterial({color:'#b9d4cf'}));ground.position.y=-.07;scene.add(ground);
  const rings=new THREE.GridHelper(4,16,'#c5d8d6','#d2e2e0');rings.position.y=.01;scene.add(rings);
  human=createAvatar();scene.add(human);controls=new OrbitControls(camera,renderer.domElement);controls.target.set(0,1.2,0);controls.enableDamping=true;controls.maxPolarAngle=Math.PI*.57;controls.update();
  function resize(){const w=mount.clientWidth,h=mount.clientHeight;camera.aspect=w/h;camera.updateProjectionMatrix();renderer.setSize(w,h,false)}new ResizeObserver(resize).observe(mount);resize();$('render-status').textContent='程序化人物 · 可以旋轉';
  requestAnimationFrame(animate);
}
function animate(){requestAnimationFrame(animate);const dt=Math.min(clock.getDelta(),.06);if(!paused)t+=dt;
  if(human){const p=human.userData.parts,w=2.9*t;if(pose==='walk'){p.legs.forEach(({g,s})=>g.rotation.x=s*.33*Math.sin(w));p.arms.forEach(({g,s})=>g.rotation.x=-s*.21*Math.sin(w));p.trunk.rotation.x=.04;p.root.position.y=.035*Math.sin(w*2)}
  else if(pose==='lean'){p.legs.forEach(({g})=>g.rotation.x=0);p.arms.forEach(({g})=>g.rotation.x=0);p.trunk.rotation.x=.25;p.root.position.y=0}
  else if(pose==='sit'){const v=(Math.sin(w*.45)+1)/2;p.legs.forEach(({g})=>g.rotation.x=-.62*v);p.arms.forEach(({g})=>g.rotation.x=0);p.trunk.rotation.x=.1*v;p.root.position.y=-.3*v}
  else {p.legs.forEach(({g})=>g.rotation.x=0);p.arms.forEach(({g})=>g.rotation.x=0);p.trunk.rotation.x=0;p.root.position.y=0}}
  if(vrm && !paused){vrm.update(dt);const hips=vrm.humanoid?.getNormalizedBoneNode('hips');if(hips)hips.position.y=.01*Math.sin(t*4)}
  controls.update();renderer.render(scene,camera);
}
$('vrmfile').addEventListener('change',async e=>{const file=e.target.files[0];if(!file)return;const url=URL.createObjectURL(file);$('render-status').textContent='載入 VRM…';try{const loader=new GLTFLoader();loader.register(parser=>new VRMLoaderPlugin(parser));loader.load(url,gltf=>{if(vrm)scene.remove(vrm.scene);vrm=gltf.userData.vrm;scene.add(vrm.scene);human.visible=false;$('render-status').textContent='VRM 模型已載入（未做臨床骨架標定）';URL.revokeObjectURL(url)},undefined,err=>{$('render-status').textContent='VRM 載入失敗';URL.revokeObjectURL(url)})}catch(e){$('render-status').textContent='VRM 模型不相容；使用預設人物'}});
function wave(u){const x=(u%1+1)%1;const gauss=(m,s,a)=>a*Math.exp(-((x-m)/s)**2);return .03*Math.sin(x*6.28)+gauss(.23,.055,.14)-gauss(.43,.014,.15)+gauss(.46,.007,1.05)-gauss(.49,.012,.28)+gauss(.72,.1,.25)}
function drawECG(){const el=$('ecg'),ctx=el.getContext('2d');const dpr=Math.min(devicePixelRatio||1,2),w=el.clientWidth,h=el.clientHeight;el.width=w*dpr;el.height=h*dpr;ctx.scale(dpr,dpr);ctx.clearRect(0,0,w,h);ctx.lineWidth=1;ctx.strokeStyle='#e1ecea';for(let x=0;x<w;x+=20){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke()}for(let y=0;y<h;y+=20){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke()}ctx.strokeStyle='#208e80';ctx.lineWidth=2;ctx.beginPath();for(let x=0;x<w;x++){const y=h*.61-wave((x/125)+(t*.42))*h*.40;if(x===0)ctx.moveTo(x,y);else ctx.lineTo(x,y)}ctx.stroke()}
function drawFeet(){const el=$('feet'),ctx=el.getContext('2d');const dpr=Math.min(devicePixelRatio||1,2),w=el.clientWidth,h=el.clientHeight;el.width=w*dpr;el.height=h*dpr;ctx.scale(dpr,dpr);ctx.clearRect(0,0,w,h);for(let s of [-1,1]){const cx=w*(s<0?.32:.68),cy=h*.55;ctx.save();ctx.translate(cx,cy);ctx.scale(s,1);ctx.fillStyle='#dceae8';ctx.beginPath();ctx.ellipse(0,0,30,56,-.12,0,Math.PI*2);ctx.fill();const pat=ctx.createRadialGradient(4,28,2,0,10,56);pat.addColorStop(0,'rgba(233,146,72,.84)');pat.addColorStop(.45,'rgba(245,201,99,.58)');pat.addColorStop(1,'rgba(24,153,132,.12)');ctx.fillStyle=pat;ctx.beginPath();ctx.ellipse(0,0,28,52,-.12,0,Math.PI*2);ctx.fill();ctx.restore()}ctx.fillStyle='#667f81';ctx.font='11px sans-serif';ctx.fillText('左足（合成）',w*.32-32,h-8);ctx.fillText('右足（合成）',w*.68-32,h-8)}
function walkChart(){const vals=[15,20,null,10,25,20,15],date=['11/01','11/02','11/03','11/04','11/05','11/06','11/07'];$('walkchart').innerHTML=vals.map((v,i)=>`<div class="walkbar"><span class="v">${v??'缺失'}</span><div class="bar ${v===null?'missing':''}" style="height:${v===null?4:v*2.45}px"></div><small>${date[i]}</small></div>`).join('')}
function metrics(f){$('hr').textContent=f.hr_bpm;$('spo').textContent=f.spo2_pct??'缺失';$('bp').textContent=f.bp_mmHg.join('/');$('gait').textContent=f.gait_m_s}
async function update(){try{const f=await api(`/api/frame?t=${t.toFixed(1)}&scenario=${scenario}`);metrics(f)}catch{}drawECG();drawFeet();$('timetxt').textContent=Math.floor(t)+' s';$('time').value=Math.floor(t)%121}
let talkPending=false;
function addBubble(msg,type){const bubble=document.createElement('div');bubble.className='bubble '+type;bubble.textContent=msg;$('chatlog').appendChild(bubble);$('chatlog').scrollTop=$('chatlog').scrollHeight}
async function send(q){if(!q?.trim()||talkPending)return;talkPending=true;addBubble(q,'user');questions.push(q);$('chatstatus').textContent='回應中…';try{const data=await post('/api/chat',{question:q,provider:$('provider').value});addBubble(data.reply,'bot');$('chatstatus').textContent=`模式：${data.mode}｜來源：${data.evidence}`;if($('voice').checked&&window.speechSynthesis){speechSynthesis.cancel();let utterance=new SpeechSynthesisUtterance(data.reply);utterance.lang='zh-TW';utterance.rate=.9;speechSynthesis.speak(utterance)}}catch(e){addBubble('模型未連線：'+e.message,'bot');$('chatstatus').textContent='未提供有效模型結果'}finally{talkPending=false;$('question').value=''}}
$('send').onclick=()=>send($('question').value);$('question').onkeydown=e=>{if(e.key==='Enter')send($('question').value)};document.querySelectorAll('.quick button').forEach(b=>b.onclick=()=>send(b.dataset.q));
$('mic').onclick=()=>{const Rec=window.SpeechRecognition||window.webkitSpeechRecognition;if(!Rec){$('chatstatus').textContent='本瀏覽器不支援語音辨識，請改用鍵盤';return}const r=new Rec();r.lang='zh-TW';r.onresult=e=>{$('question').value=e.results[0][0].transcript};r.onerror=e=>$('chatstatus').textContent='語音辨識無法使用：'+e.error;r.start()};
async function runAnalysis(){try{const x=await post('/api/analyze',{scenario});$('evidence').innerHTML='';for(const f of x.facts){const el=document.createElement('div');el.className='evidence-item';const strong=document.createElement('strong');strong.textContent=f.claim;const source=document.createElement('div');source.className='source';source.textContent='來源：'+f.source+' · 合成案例';el.append(strong,source);$('evidence').append(el)}$('issues').textContent='核對界線：'+x.issues.join(' ｜ ')}catch(e){$('issues').textContent='分析失敗：'+e.message}}
$('analyze').onclick=runAnalysis;
$('fill').onclick=async()=>{const x=await post('/api/sbar',{scenario});for(const k of 'SBAR')$(k).value=x[k];$('graderesult').textContent='草稿已載入；請查核並手動修改後評分。'};
$('grade').onclick=async()=>{const fields=Object.fromEntries('SBAR'.split('').map(k=>[k,$(k).value]));const g=await post('/api/grade',{fields});$('graderesult').innerHTML=`<div class="gradecard"><b>${g.score} / 100</b>　${g.unsafe_claim?'⚠ 不可宣稱確診':''}<small>${g.label}</small></div>`};
$('scenario').onchange=async e=>{scenario=e.target.value;await runAnalysis();await update()};$('pose').onchange=e=>{pose=e.target.value};$('pause').onclick=()=>{paused=!paused;$('pause').textContent=paused?'繼續':'暫停'};$('time').oninput=e=>{t=+e.target.value;update()};
$('export').onclick=()=>{const state={exported_at:new Date().toISOString(),patient:'SYN-LIN72-01',scenario,pose,synthetic:true,questions,sbar:Object.fromEntries('SBAR'.split('').map(k=>[k,$(k).value])),disclaimer:'All data synthetic; not a diagnostic record'};const blob=new Blob([JSON.stringify(state,null,2)],{type:'application/json'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='carelab_learning_record.json';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),500)};
window.__CARELAB_READY=true;initScene();walkChart();runAnalysis();update();setInterval(()=>{if(!paused)update()},800);