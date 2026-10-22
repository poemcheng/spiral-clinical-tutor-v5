import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import {VRMLoaderPlugin,VRMUtils} from '@pixiv/three-vrm';

export async function loadCharacter(scene,url){
 const loader=new GLTFLoader();loader.register(parser=>new VRMLoaderPlugin(parser));
 const gltf=await loader.loadAsync(url),vrm=gltf.userData.vrm;
 if(!vrm)throw new Error('缺少 VRM 人形結構');
 VRMUtils.rotateVRM0(vrm);scene.add(vrm.scene);
 vrm.humanoid.setNormalizedPose({leftUpperArm:{rotation:[0,0,-.12,.99]},rightUpperArm:{rotation:[0,0,.12,.99]}});
 return {vrm,renderAt(t,amplitude=0){
  for(const [name,sign] of [['leftUpperArm',-1],['rightUpperArm',1]]){
   const bone=vrm.humanoid.getNormalizedBoneNode(name);if(bone)bone.rotation.z=sign*(1.18+Math.sin(t*.9)*.05);
  }
  const head=vrm.humanoid.getNormalizedBoneNode('head');if(head)head.rotation.set(Math.sin(t*1.3)*.025,Math.sin(t*.7)*.04,0);
  vrm.expressionManager?.setValue('aa',Math.min(1,amplitude));vrm.expressionManager?.setValue('blink',(t%4.3)<.11?1:0);
  vrm.update(1/24);
 }};
}
