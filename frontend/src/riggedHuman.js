import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';

export function riggedHuman(modelUrl){
 const group=new THREE.Group();let root,disposed=false,behavior='neutral',presence='ready',visemes=null;const meshes=[],bones=new Map(),rest=new Map();
 const ready=new GLTFLoader().loadAsync(modelUrl).then(gltf=>{
  root=gltf.scene;if(disposed){disposeRoot(root);return;}
  const bounds=new THREE.Box3().setFromObject(root),height=bounds.max.y-bounds.min.y;
  if(height<.1)throw Error('角色模型尺寸異常');root.scale.multiplyScalar(1.74/height);root.updateMatrixWorld(true);
  const centered=new THREE.Box3().setFromObject(root);root.position.x-=((centered.max.x+centered.min.x)/2);root.position.z-=((centered.max.z+centered.min.z)/2);root.position.y-=centered.min.y;
  root.traverse(o=>{
   if(o.isBone){const name=o.name.replaceAll('_','.');bones.set(name,o);rest.set(name,o.quaternion.clone());}
   if(o.isMesh){o.castShadow=true;o.receiveShadow=true;o.frustumCulled=false;if(o.isSkinnedMesh)meshes.push(o);
    for(const m of Array.isArray(o.material)?o.material:[o.material]){if(!m)continue;m.roughness=Math.max(.4,m.roughness??.7);m.transparent=false;m.depthWrite=true;m.side=THREE.FrontSide;if(/high-poly/i.test(o.name)){m.transparent=true;m.depthWrite=false;m.side=THREE.DoubleSide;}if(/short0[1-4]|bob0[12]|long01|ponytail|hair|eyelash|eyebrow/i.test(o.name)){m.alphaTest=.25;m.transparent=false;m.side=THREE.DoubleSide;}}
   }
  });
  if(!meshes.length)throw Error('角色缺少骨架蒙皮，無法啟用3D互動');group.add(root);group.userData.skinnedMeshes=meshes.length;group.userData.bones=bones.size;renderAt(0,0);
 });
 const q=new THREE.Quaternion(),axisX=new THREE.Vector3(1,0,0),axisY=new THREE.Vector3(0,1,0),axisZ=new THREE.Vector3(0,0,1);
 function rotate(name,axis,amount){const b=(bones.get(name)||bones.get(name.replaceAll('.','')));if(b)b.quaternion.copy((rest.get(name)||rest.get(name.replaceAll('.','')))).multiply(q.setFromAxisAngle(axis,amount));}
 function rotateWorld(name,amount){const b=(bones.get(name)||bones.get(name.replaceAll('.','')));if(!b)return;const parentQ=b.parent.getWorldQuaternion(new THREE.Quaternion());const turn=new THREE.Quaternion().setFromAxisAngle(axisZ.clone().applyQuaternion(group.getWorldQuaternion(new THREE.Quaternion())),amount);b.quaternion.copy(parentQ.clone().invert().multiply(turn).multiply(parentQ).multiply((rest.get(name)||rest.get(name.replaceAll('.','')))));}
 function expression(name,value){for(const m of meshes){const i=m.morphTargetDictionary?.[name];if(i!==undefined)m.morphTargetInfluences[i]=value;}}
 function renderAt(t,amplitude=0){if(!root||disposed)return;const a=THREE.MathUtils.clamp(amplitude,0,1);
  for(const m of meshes)if(m.morphTargetInfluences)m.morphTargetInfluences.fill(0);
  if(visemes){for(const [key,name] of Object.entries({aa:'viseme_aa',ih:'viseme_I',ou:'viseme_U',ee:'viseme_E',oh:'viseme_O'}))expression(name,Math.min(.75,visemes[key]||0));expression('jawOpen',Math.min(.23,(visemes.aa||0)*.26));}
  else{expression('viseme_aa',Math.min(.65,a*.68));expression('jawOpen',Math.min(.23,a*.26));}
  const phase=(t+1.9)%4.3,blink=phase<.16?Math.sin(phase/.16*Math.PI):0;expression('eyeBlinkLeft',blink);expression('eyeBlinkRight',blink);
  const friendly=behavior==='friendly',reserved=behavior==='reserved',talk=Math.min(1,a*3);
  expression('mouthSmileLeft',friendly?.16:reserved?0:.025);expression('mouthSmileRight',friendly?.16:reserved?0:.025);
  expression('browInnerUp',behavior==='concerned'?.18:presence==='thinking'?.06:0);
  expression('browDownLeft',reserved?.12:0);expression('browDownRight',reserved?.1:0);
  expression('eyeLookInLeft',.015);expression('eyeLookInRight',.015);
  rotate('spine02',axisX,Math.sin(t*1.5)*.006+(reserved?-.012:0));rotate('head',axisX,Math.sin(t*.75)*.012+(a>.05?Math.sin(t*2.5)*.018:0)+(presence==='listening'?Math.sin(t*1.1)*.022:0)+(reserved?-.015:0));rotate('neck03',axisY,Math.sin(t*.4)*.018+(presence==='thinking'?.07:0)+(reserved?.035:0));
  // Small speech-synchronous gestures. The rig stays volumetric from all camera directions.
  rotateWorld('upperarm01.L',-.65+talk*(.035+Math.sin(t*1.8)*.035));rotateWorld('upperarm01.R',.65-talk*.045);rotate('lowerarm01.L',axisX,.08+talk*.13);rotate('lowerarm01.R',axisX,.08+talk*.08);
  root.updateMatrixWorld(true);for(const m of meshes)m.skeleton.update();
 }
 function disposeRoot(object){const textures=new Set(),materials=new Set(),geometries=new Set();object.traverse(o=>{if(o.geometry)geometries.add(o.geometry);for(const m of Array.isArray(o.material)?o.material:[o.material])if(m){materials.add(m);for(const v of Object.values(m))if(v?.isTexture)textures.add(v);}});textures.forEach(t=>t.dispose());materials.forEach(m=>m.dispose());geometries.forEach(g=>g.dispose());}
 return {group,ready,renderAt,setVisemes(value){visemes=value;},setPresence(value){presence=value;},setBehavior(value){behavior=['friendly','reserved','concerned','neutral'].includes(value)?value:'neutral';},dispose(){disposed=true;if(root)disposeRoot(root);group.clear();}};
}
