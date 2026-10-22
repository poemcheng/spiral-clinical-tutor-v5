import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';

export function riggedHuman(modelUrl){
 const group=new THREE.Group();let root,disposed=false;const meshes=[],bones=new Map(),rest=new Map();
 const ready=new GLTFLoader().loadAsync(modelUrl).then(gltf=>{
  root=gltf.scene;if(disposed){disposeRoot(root);return;}
  const bounds=new THREE.Box3().setFromObject(root),height=bounds.max.y-bounds.min.y;
  if(height<.1)throw Error('角色模型尺寸異常');root.scale.multiplyScalar(1.74/height);root.updateMatrixWorld(true);
  const centered=new THREE.Box3().setFromObject(root);root.position.x-=((centered.max.x+centered.min.x)/2);root.position.z-=((centered.max.z+centered.min.z)/2);root.position.y-=centered.min.y;
  root.traverse(o=>{
   if(o.isBone){const name=o.name.replaceAll('_','.');bones.set(name,o);rest.set(name,o.quaternion.clone());}
   if(o.isMesh){o.castShadow=true;o.receiveShadow=true;o.frustumCulled=false;if(o.isSkinnedMesh)meshes.push(o);
    for(const m of Array.isArray(o.material)?o.material:[o.material]){if(!m)continue;m.roughness=Math.max(.4,m.roughness??.7);m.transparent=false;m.depthWrite=true;m.side=THREE.FrontSide;if(/high-poly/i.test(o.name)){m.transparent=true;m.depthWrite=false;m.side=THREE.DoubleSide;}if(/short02|bob01|hair|eyelash|eyebrow/i.test(o.name)){m.alphaTest=.35;m.transparent=false;m.side=THREE.DoubleSide;}}
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
  expression('viseme_aa',Math.min(.65,a*.68));expression('jawOpen',Math.min(.23,a*.26));expression('viseme_O',a>.38?(Math.sin(t*12)*.5+.5)*a*.18:0);
  const phase=(t+1.9)%4.3,blink=phase<.16?Math.sin(phase/.16*Math.PI):0;expression('eyeBlinkLeft',blink);expression('eyeBlinkRight',blink);
  expression('mouthSmileLeft',.025);expression('mouthSmileRight',.025);
  rotate('spine02',axisX,Math.sin(t*1.5)*.006);rotate('head',axisX,Math.sin(t*.75)*.018+(a>.05?Math.sin(t*2.5)*.012:0));rotate('neck03',axisY,Math.sin(t*.4)*.018);
  rotateWorld('upperarm01.L',-.65);rotateWorld('upperarm01.R',.65);rotate('lowerarm01.L',axisX,.08);rotate('lowerarm01.R',axisX,.08);
  root.updateMatrixWorld(true);for(const m of meshes)m.skeleton.update();
 }
 function disposeRoot(object){const textures=new Set(),materials=new Set(),geometries=new Set();object.traverse(o=>{if(o.geometry)geometries.add(o.geometry);for(const m of Array.isArray(o.material)?o.material:[o.material])if(m){materials.add(m);for(const v of Object.values(m))if(v?.isTexture)textures.add(v);}});textures.forEach(t=>t.dispose());materials.forEach(m=>m.dispose());geometries.forEach(g=>g.dispose());}
 return {group,ready,renderAt,dispose(){disposed=true;if(root)disposeRoot(root);group.clear();}};
}
