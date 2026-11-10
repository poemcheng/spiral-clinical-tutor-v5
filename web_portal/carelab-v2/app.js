import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin } from '@pixiv/three-vrm';
const $=id=>document.getElementById(id);
let scene, camera, renderer, controls, human, vrm=null, clock=new THREE.Clock(),paused=false,t=0,scenario='baseline',pose='stand',questions=[];
const api=(path, options={})=>window.carelabAPI(path,options);
const post=(path,data)=>api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
// Procedural 3D elderly character for a synthetic, non-diagnostic care lab.
// All motions are authored animation, NOT reconstructed from patient observations.
function createAvatar(){
  const root=new THREE.Group(); root.name='SyntheticPatient_Lin';
  const material=(color,roughness=.8,metalness=0)=>new THREE.MeshStandardMaterial({color,roughness,metalness});
  const skin=material('#d0a68d',.86), skinShade=material('#b98770'), coat=material('#458d89'), coatLight=material('#70b4aa'), coatDark=material('#286c6e'), shirt=material('#eee8da'), pants=material('#35475b'), seams=material('#223a50'), hair=material('#bdc5c7'), hairShadow=material('#86979c'), shoes=material('#2d3644'), glasses=material('#c2a47a',.38,.55), iris=material('#4b5c60'), white=material('#f3f1e9'), lip=material('#a97368');
  const ell=(parent,m,x,y,z,a,b,c)=>{const q=new THREE.Mesh(new THREE.SphereGeometry(1,32,24),m);q.position.set(x,y,z);q.scale.set(a,b,c);q.castShadow=true;q.receiveShadow=true;parent.add(q);return q};
  const cyl=(parent,m,x,y,z,r1,r2,h)=>{const q=new THREE.Mesh(new THREE.CylinderGeometry(r1,r2,h,20),m);q.position.set(x,y,z);q.castShadow=true;parent.add(q);return q};
  // The longitudinal axes of the limbs are parent-relative, so elbow/knee motion is independent.
  const hips=new THREE.Group();hips.position.y=.96;root.add(hips);ell(hips,pants,0,-.02,0,.245,.19,.18);
  const torso=new THREE.Group();torso.position.set(0,1.02,0);root.add(torso);
  ell(torso,coat,0,.30,0,.325,.42,.205);ell(torso,shirt,0,.305,.187,.165,.33,.025);
  // Open cardigan edges and collar; mild asymmetry looks less mannequin-like.
  for(const s of [-1,1]){
    ell(torso,coatDark,s*.166,.285,.183,.045,.33,.030);
    let collar=ell(torso,coatLight,s*.105,.635,.166,.115,.07,.045);collar.rotation.z=s*.35;
    for(let n=0;n<3;n++){ell(torso,coatDark,s*.273,.31-n*.13,.168,.012,.013,.012)}
  }
  ell(torso,coatDark,0,.015,.192,.225,.045,.025);
  cyl(torso,skin,0,.755,0,.074,.078,.17);
  const head=new THREE.Group();head.position.set(0,.84,0);torso.add(head);
  ell(head,skin,0,.15,0,.214,.265,.193); // face
  ell(head,skin,0,.06,.167,.107,.11,.045); // chin
  ell(head,skinShade,0,.126,.196,.039,.067,.041); // nose bridge
  ell(head,skin,0,.093,.222,.051,.049,.054); // nose tip
  for(const s of [-1,1]){
    ell(head,skin,s*.210,.143,0,.033,.069,.052); // ears
    ell(head,white,s*.098,.205,.177,.068,.036,.015); // eye sclera
    ell(head,iris,s*.099,.202,.194,.020,.026,.009); // pupils
    const brow=ell(head,hairShadow,s*.098,.253,.169,.078,.013,.016);brow.rotation.z=-s*.08;
    const eyeLine=ell(head,skinShade,s*.104,.163,.183,.064,.010,.008);
    const lens=new THREE.Mesh(new THREE.TorusGeometry(.093,.008,8,36),glasses);
    lens.position.set(s*.113,.202,.208);head.add(lens);
    // realistic mottled gray hair forming a swept short crop
    for(let i=0;i<6;i++){
      const lock=ell(head,i%3===0?hairShadow:hair,s*(.025+i*.029),.371-i*.016,-.005+i*.008,.089-i*.008,.068,.136);
      lock.rotation.z=s*(-.17-.03*i);
    }
  }
  cyl(head,glasses,0,.213,.207,.011,.011,.008).rotation.z=Math.PI/2; // bridge
  const mouth=ell(head,lip,0,.012,.184,.063,.008,.010);
  const mouthHi=ell(head,skin,0,.025,.189,.071,.012,.008);
  ell(head,hair,0,.368,-.055,.218,.104,.165);
  for(let i=-3;i<=3;i++){const x=i*.056;let w=ell(head,i%2?hair:hairShadow,x,.412-Math.abs(i)*.01,.10,.070,.055,.083);w.rotation.z=-.25}
  const arms=[],legs=[];
  for(const s of [-1,1]){
    const arm=new THREE.Group();arm.position.set(s*.328,.575,-.005);torso.add(arm);
    ell(arm,coat,s*.015,-.18,0,.112,.24,.122);
    const cuff=ell(arm,coatLight,s*.014,-.36,0,.088,.045,.094);
    const elbow=new THREE.Group();elbow.position.set(0,-.365,0);arm.add(elbow);
    ell(elbow,coat,0,-.145,0,.085,.185,.090);ell(elbow,shirt,0,-.292,0,.088,.038,.087);
    const hand=ell(elbow,skin,0,-.365,.013,.071,.103,.048);
    for(let k=0;k<4;k++)ell(elbow,skin,(-.044+k*.029),-.432,.029,.014,.055,.021);
    ell(elbow,skin,s*.084,-.356,.043,.029,.063,.027);
    arms.push({g:arm,elbow,s});
    const leg=new THREE.Group();leg.position.set(s*.147,.92,0);root.add(leg);
    ell(leg,pants,0,-.225,0,.133,.294,.147);
    const knee=new THREE.Group();knee.position.set(0,-.465,0);leg.add(knee);
    ell(knee,pants,0,-.204,0,.111,.25,.118);ell(knee,seams,0,-.411,0,.116,.035,.124);
    const foot=new THREE.Group();foot.position.set(0,-.412,0);knee.add(foot);
    ell(foot,shoes,0,.02,.100,.128,.075,.220);
    ell(foot,material('#566578'),0,.003,.205,.107,.028,.095);
    legs.push({g:leg,knee,foot,s});
  }
  // A subtle anatomy marker is decorative and never interpreted as a joint measurement.
  root.userData.parts={arms,legs,trunk:torso,hips,head,root};
  return root;
}
function buildChair(){const root=new THREE.Group();const m=new THREE.MeshStandardMaterial({color:'#607888',roughness:.66,metalness:.12});const wood=new THREE.MeshStandardMaterial({color:'#c1afa0',roughness:.85});
  function box(w,h,d,x,y,z,mat=m){const v=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),mat);v.position.set(x,y,z);v.castShadow=true;root.add(v)}
  box(.66,.065,.54,0,.49,-.32,wood);box(.66,.65,.06,0,.815,-.565,wood);
  for(const s of [-1,1]){box(.046,.47,.046,s*.275,.245,-.51);box(.046,.47,.046,s*.275,.245,-.08)}
  root.visible=false;return root;
}
function initScene(){
  const mount=$('scene');scene=new THREE.Scene();scene.background=new THREE.Color('#111f33');scene.fog=new THREE.Fog('#111f33',8,16);
  camera=new THREE.PerspectiveCamera(37,1,.1,60);camera.position.set(3.05,2.15,4.4);
  renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.8));renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.15;mount.appendChild(renderer.domElement);
  scene.add(new THREE.HemisphereLight(0xe9f4ff,0x2c465b,2.5));
  const key=new THREE.DirectionalLight(0xf6f8ff,3.3);key.position.set(4,7,6);key.castShadow=true;key.shadow.mapSize.set(1024,1024);key.shadow.camera.left=-4;key.shadow.camera.right=4;key.shadow.camera.top=5;key.shadow.camera.bottom=-4;scene.add(key);
  const rim=new THREE.DirectionalLight(0x6acfc4,2.5);rim.position.set(-3,4,-3);scene.add(rim);
  const fill=new THREE.PointLight(0x87accb,70,18);fill.position.set(-4,2,3);scene.add(fill);
  const groundMat=new THREE.MeshStandardMaterial({color:'#21374a',roughness:.83,metalness:.15});const ground=new THREE.Mesh(new THREE.CylinderGeometry(1.7,1.8,.115,80),groundMat);ground.position.y=-.115;ground.receiveShadow=true;scene.add(ground);
  for(let i=0;i<3;i++){const r=new THREE.Mesh(new THREE.TorusGeometry(1.27+i*.14,.007,7,96),new THREE.MeshBasicMaterial({color:i===1?'#57c5c5':'#4a8399',transparent:true,opacity:i===1?.48:.2}));r.rotation.x=Math.PI/2;r.position.y=-.034;scene.add(r)}
  const grid=new THREE.GridHelper(10,28,0x29495d,0x23394a);grid.position.y=-.19;scene.add(grid);
  human=createAvatar();scene.add(human);window.carelabChair=buildChair();scene.add(window.carelabChair);
  controls=new OrbitControls(camera,renderer.domElement);controls.target.set(0,1.07,0);controls.enableDamping=true;controls.enablePan=false;controls.minDistance=2.6;controls.maxDistance=7;controls.minPolarAngle=.36;controls.maxPolarAngle=1.62;controls.update();
  window.carelabSetView=mode=>{const vec={front:[0,1.75,4.4],side:[4.4,1.75,0],three:[3.05,2.15,4.4]}[mode]||[3.05,2.15,4.4];camera.position.set(...vec);controls.target.set(0,1.07,0);controls.update();document.querySelectorAll('.view-btn').forEach(b=>b.classList.toggle('selected',b.id==='view-'+mode));};
  for(const mode of ['front','side','three'])$('view-'+mode)?.addEventListener('click',()=>window.carelabSetView(mode));
  function resize(){const w=Math.max(mount.clientWidth,1),h=Math.max(mount.clientHeight,1);camera.aspect=w/h;camera.updateProjectionMatrix();renderer.setSize(w,h,false)}new ResizeObserver(resize).observe(mount);resize();$('render-status').textContent='3D 完整關節人物 · 可旋轉';
  requestAnimationFrame(animate);
}
function animate(){requestAnimationFrame(animate);const dt=Math.min(clock.getDelta(),.05);if(!paused)t+=dt;
  if(human){const p=human.userData.parts,w=2.8*t;
    p.arms.forEach(({g,elbow,s})=>{g.rotation.x=0;g.rotation.z=s*.055;elbow.rotation.x=-.13});
    p.legs.forEach(({g,knee,foot})=>{g.rotation.x=0;knee.rotation.x=0;foot.rotation.x=0});
    p.trunk.rotation.x=.015;p.head.rotation.y=Math.sin(t*.43)*.032;p.head.rotation.x=Math.sin(t*.63)*.012;p.root.position.y=Math.sin(t*1.6)*.006;
    if(pose==='walk'){
      p.legs.forEach(({g,knee,foot,s})=>{g.rotation.x=s*.42*Math.sin(w);knee.rotation.x=Math.max(0,-s*Math.sin(w))*.51;foot.rotation.x=-g.rotation.x*.17-knee.rotation.x*.42});
      p.arms.forEach(({g,elbow,s})=>{g.rotation.x=-s*.30*Math.sin(w);elbow.rotation.x=-.22-.12*Math.max(0,s*Math.sin(w))});
      p.trunk.rotation.x=.025;p.trunk.rotation.y=.028*Math.sin(w);p.root.position.y=.015*Math.cos(w*2);
    }else if(pose==='lean'){
      p.trunk.rotation.x=.24;p.head.rotation.x=-.10;p.legs.forEach(({g,knee})=>{g.rotation.x=-.045;knee.rotation.x=.045});
      p.arms.forEach(({g,elbow})=>{g.rotation.x=-.14;elbow.rotation.x=-.10});
    }else if(pose==='sit'){
      const v=(1-Math.cos(t*1.65))*.5;
      p.legs.forEach(({g,knee,foot})=>{g.rotation.x=-1.12*v;knee.rotation.x=1.38*v;foot.rotation.x=-.13*v});
      p.trunk.rotation.x=.10*v;p.arms.forEach(({g,elbow})=>{g.rotation.x=-.23*v;elbow.rotation.x=-.6*v});
      p.root.position.y=-.37*v;p.root.position.z=-.22*v;window.carelabChair.visible=true;
    }
    if(pose!=='sit'){p.root.position.z=0;window.carelabChair.visible=false}
  }
  if(vrm&&!paused){vrm.update(dt);const hips=vrm.humanoid?.getNormalizedBoneNode('hips');if(hips)hips.position.y=.01*Math.sin(t*4)}
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