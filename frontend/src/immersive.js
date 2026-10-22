import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {photoHuman} from './photoHuman.js';

// Shared by live interaction and seekable lecturer exports. Source portraits
// remain photographic planes; the room, lighting and camera are genuine 3D.
export function clinicScene(canvas,{atlasUrl,face={},interactive=false,onAction=()=>{}}={}){
 const renderer=new THREE.WebGLRenderer({canvas,antialias:true,preserveDrawingBuffer:true});
 renderer.setPixelRatio(interactive?Math.min(devicePixelRatio,1.5):1);renderer.outputColorSpace=THREE.SRGBColorSpace;
 renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
 const scene=new THREE.Scene();scene.background=new THREE.Color('#dce6ea');
 const camera=new THREE.PerspectiveCamera(55,1,.1,100);camera.position.set(0,1.65,4.5);
 const clinic=new THREE.Group();scene.add(clinic);const disposable=[],hotspots=[];
 const standard=(color,extra={})=>new THREE.MeshStandardMaterial({color,roughness:.68,...extra});
 function box(w,h,d,color,x,y,z,extra={}){const material=standard(color,extra),mesh=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),material);mesh.position.set(x,y,z);mesh.castShadow=true;mesh.receiveShadow=true;clinic.add(mesh);disposable.push(mesh.geometry,material);return mesh;}
 scene.add(new THREE.HemisphereLight(0xf5fcff,0x65777e,2.3));const sun=new THREE.DirectionalLight(0xfff4dc,2.4);sun.position.set(-3,6,3);sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);scene.add(sun);
 box(10,.12,10,'#bdc5c1',0,-.06,0);box(10,3.7,.12,'#e5eeec',0,1.85,-3.4);box(.12,3.7,9,'#d6e3e1',-4.7,1.85,.3);box(.12,3.7,9,'#e7eeed',4.7,1.85,.3);
 for(let i=-4;i<=4;i++){box(.012,.005,9,'#a6b4b2',i,.008,.3);box(9,.005,.012,'#a6b4b2',0,.008,i);}
 box(9,.18,.08,'#80a9a1',0,.85,-3.3);box(9,.08,.08,'#859a94',0,.08,-3.3);
 // Daylight window, wall-mounted monitor, bed, consultation desk and chairs.
 box(2.55,1.65,.09,'#91c4d3',-2.4,2.25,-3.25,{roughness:.3});
 for(const dx of [-1.3,0,1.3])box(.055,1.72,.13,'#f7faf8',-2.4+dx,2.25,-3.15);
 box(2.65,.055,.13,'#f7faf8',-2.4,2.25,-3.15);
 box(1.25,.78,.12,'#263e48',2.7,2.05,-3.2);box(1.1,.62,.02,'#1c6a78',2.7,2.05,-3.12,{emissive:'#16404a',emissiveIntensity:.35});
 for(let i=0;i<9;i++)box(.07,.03,.025,'#73ddcd',2.25+i*.11,2.04+Math.sin(i*1.9)*.13,-3.09);
 box(1.28,.19,2.2,'#c5d7dc',-2.9,.73,-1.15);box(1.24,.2,2.14,'#eef4ed',-2.9,.92,-1.15);box(.9,.15,.48,'#fffefa',-2.9,1.08,-1.9);
 for(const x of [-3.42,-2.38]){box(.06,.55,2.18,'#7b969c',x,.73,-1.15,{metalness:.7});for(const z of [-2,-.3])box(.1,.68,.1,'#758d94',x,.35,z);}
 box(1.7,.12,.8,'#d1b08b',2.3,.92,.3);for(const x of [1.62,2.98])for(const z of [.02,.58])box(.07,.9,.07,'#70878c',x,.45,z);
 box(.65,.07,.49,'#284550',2.25,1.02,.3);box(.68,.43,.05,'#233d47',2.25,1.26,.06);
 for(const [x,z] of [[1.85,1.4],[.8,-1.45]]){box(.55,.12,.53,'#4c7f86',x,.5,z);box(.56,.57,.1,'#4c7f86',x,.82,z-.23);for(const dx of [-.22,.22])for(const dz of [-.2,.2])box(.045,.45,.045,'#6c8489',x+dx,.23,z+dz);}
 box(.75,1.75,.45,'#f3f7f2',3.8,.87,-2.7);box(.035,.65,.05,'#64868a',3.8,1.1,-2.45);
 const portraitCanvas=document.createElement('canvas');portraitCanvas.width=512;portraitCanvas.height=640;portraitCanvas.style.width='512px';portraitCanvas.style.height='640px';
 const rig=photoHuman(portraitCanvas,{atlasUrl,face,fit:'contain'}),texture=new THREE.CanvasTexture(portraitCanvas);texture.colorSpace=THREE.SRGBColorSpace;
 // The available characters are photographic portraits. Present them as a
 // life-size consultation display, instead of implying a floating 3D body.
 box(1.7,2.12,.075,'#254650',0,1.43,-.06,{metalness:.35,roughness:.34});
 box(.18,.38,.18,'#46636a',0,.21,-.06,{metalness:.5});box(.85,.06,.55,'#34515a',0,.04,-.04,{metalness:.5});
 const material=new THREE.MeshBasicMaterial({map:texture});
 const portrait=new THREE.Mesh(new THREE.PlaneGeometry(1.6,2),material);portrait.position.set(0,1.43,-.015);clinic.add(portrait);disposable.push(texture,portrait.geometry,material);
 function label(text,x,y,z,action){const c=document.createElement('canvas');c.width=512;c.height=112;const ctx=c.getContext('2d');ctx.fillStyle='#183a47ee';ctx.beginPath();ctx.roundRect(2,2,508,108,25);ctx.fill();ctx.fillStyle='white';ctx.font='500 32px "Microsoft JhengHei",sans-serif';ctx.textAlign='center';ctx.fillText(text,256,69);const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;const m=new THREE.SpriteMaterial({map:t,depthTest:false}),sprite=new THREE.Sprite(m);sprite.position.set(x,y,z);sprite.scale.set(1.25,.273,1);sprite.userData.action=action;clinic.add(sprite);hotspots.push(sprite);disposable.push(t,m);}
 if(interactive){label('查看案例資料',-2.2,1.7,.2,'report');label('檢查情境安全',2.3,1.7,.3,'safety');label('確認互動對象',0,2.67,0,'identify');}
 let controls,disposed=false,videoTexture,panorama,mode='clinic',width=0,height=0;
 if(interactive){controls=new OrbitControls(camera,canvas);controls.target.set(0,1.45,0);controls.enablePan=false;controls.enableDamping=false;controls.minDistance=2.5;controls.maxDistance=6;controls.minPolarAngle=.8;controls.maxPolarAngle=1.75;controls.minAzimuthAngle=-.65;controls.maxAzimuthAngle=.65;controls.update();}
 const ready=rig.ready.then(()=>renderAt(0));
 function size(){const w=canvas.clientWidth||960,h=canvas.clientHeight||540;if(width===w&&height===h)return;width=w;height=h;renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();}
 function renderAt(time,amplitude=0){if(disposed)return;size();rig.renderAt(time,amplitude);texture.needsUpdate=true;portrait.position.y=1.43+Math.sin(time*1.4)*.005;portrait.rotation.z=Math.sin(time*.8)*.004;portrait.rotation.y=Math.sin(time*.65)*.012;
  if(!interactive){camera.position.set(Math.sin(time*.08)*.18,1.68,4.35);camera.lookAt(0,1.45,0);}renderer.render(scene,camera);canvas.dataset.sceneMode=mode;canvas.dataset.renderer='three.js';canvas.dataset.speaking=amplitude>.025?'true':'false';
 }
 const ray=new THREE.Raycaster(),mouse=new THREE.Vector2();let down;
 const start=e=>{down=[e.clientX,e.clientY];};const end=e=>{if(!down||Math.hypot(e.clientX-down[0],e.clientY-down[1])>7||mode!=='clinic')return;const rect=canvas.getBoundingClientRect();mouse.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);ray.setFromCamera(mouse,camera);const hit=ray.intersectObjects(hotspots)[0];if(hit)onAction(hit.object.userData.action);};
 if(interactive){canvas.addEventListener('pointerdown',start);canvas.addEventListener('pointerup',end);}
 return {ready,renderAt,reset(){if(mode==='clinic'){camera.position.set(0,1.65,4.5);controls?.target.set(0,1.45,0);controls?.update();}},setPanorama(video){
   if(panorama){scene.remove(panorama);panorama.geometry.dispose();panorama.material.dispose();videoTexture.dispose();panorama=null;}
   mode=video?'vr360':'clinic';clinic.visible=!video;scene.background=new THREE.Color(video?'#101a27':'#dce6ea');
   if(video){videoTexture=new THREE.VideoTexture(video);videoTexture.colorSpace=THREE.SRGBColorSpace;const geo=new THREE.SphereGeometry(25,64,40);geo.scale(-1,1,1);panorama=new THREE.Mesh(geo,new THREE.MeshBasicMaterial({map:videoTexture}));scene.add(panorama);camera.position.set(0,1.45,.01);controls.target.set(0,1.45,0);controls.minDistance=.01;controls.maxDistance=.01;controls.minAzimuthAngle=-Infinity;controls.maxAzimuthAngle=Infinity;controls.minPolarAngle=.1;controls.maxPolarAngle=Math.PI-.1;}
   else if(controls){controls.minDistance=2.5;controls.maxDistance=6;controls.minAzimuthAngle=-.65;controls.maxAzimuthAngle=.65;controls.minPolarAngle=.8;controls.maxPolarAngle=1.75;camera.position.set(0,1.65,4.5);controls.target.set(0,1.45,0);}controls?.update();
  },dispose(){if(disposed)return;disposed=true;controls?.dispose();rig.dispose();if(panorama){panorama.geometry.dispose();panorama.material.dispose();videoTexture.dispose();}disposable.forEach(x=>x.dispose());renderer.dispose();canvas.removeEventListener('pointerdown',start);canvas.removeEventListener('pointerup',end);}};
}
