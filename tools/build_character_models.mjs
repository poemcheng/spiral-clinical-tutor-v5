// Original geometry authored for this project. Card pixels are not edited.
// VRM 1.0 humanoid bones, rigid geometry attached to bones, aa/blink morph binds.
import * as THREE from 'three';
import fs from 'node:fs';
import path from 'node:path';
const dir=path.resolve('data/characters'),catalog=JSON.parse(fs.readFileSync(path.join(dir,'catalog.json')));
function build(actor){
 const nodes=[],meshes=[],materials=[],accessors=[],views=[],parts=[];let offset=0;
 function bytes(array,target){let b=Buffer.from(array.buffer,array.byteOffset,array.byteLength),pad=(4-offset%4)%4;if(pad){parts.push(Buffer.alloc(pad));offset+=pad;}const i=views.length;views.push({buffer:0,byteOffset:offset,byteLength:b.length,...(target?{target}:{})});parts.push(b);offset+=b.length;return i;}
 function attr(array,type,minmax=false,target=34962){const item=type==='VEC3'?3:1;const a={bufferView:bytes(array,target),componentType:array instanceof Float32Array?5126:array instanceof Uint16Array?5123:5125,count:array.length/item,type};if(minmax){a.min=Array(item).fill(Infinity);a.max=Array(item).fill(-Infinity);for(let i=0;i<array.length;i++){a.min[i%item]=Math.min(a.min[i%item],array[i]);a.max[i%item]=Math.max(a.max[i%item],array[i]);}}accessors.push(a);return accessors.length-1;}
 function material(color){const c=new THREE.Color(color);let i=materials.findIndex(m=>m.name===color);if(i>=0)return i;materials.push({name:color,pbrMetallicRoughness:{baseColorFactor:[c.r,c.g,c.b,1],metallicFactor:0,roughnessFactor:.8},doubleSided:true});return materials.length-1;}
 const boneMap={};
 function node(name,pos,parent){const index=nodes.length;nodes.push({name,translation:pos,children:[]});if(parent!==undefined)nodes[parent].children.push(index);return index;}
 const root=node('Character',[0,0,0]);
 function bone(name,pos,parent){return boneMap[name]=node(name,pos,parent);}
 const hips=bone('hips',[0,.91,0],root),spine=bone('spine',[0,.18,0],hips),chest=bone('chest',[0,.18,0],spine),neck=bone('neck',[0,.17,0],chest),head=bone('head',[0,.15,0],neck);
 for(const [side,sign] of [['left',1],['right',-1]]){
  const leg=bone(side+'UpperLeg',[sign*.13,-.06,0],hips),calf=bone(side+'LowerLeg',[0,-.40,0],leg),foot=bone(side+'Foot',[0,-.40,0],calf);
  const arm=bone(side+'UpperArm',[sign*.23,.08,0],chest),fore=bone(side+'LowerArm',[sign*.27,0,0],arm),hand=bone(side+'Hand',[sign*.25,0,0],fore);
  mesh(new THREE.CapsuleGeometry(.085,.28,4,12), '#536379',[0,-.20,0],leg);
  mesh(new THREE.CapsuleGeometry(.07,.28,4,12),'#536379',[0,-.20,0],calf);
  mesh(new THREE.BoxGeometry(.17,.1,.28),'#26364a',[0,-.02,.07],foot);
  const g=new THREE.CapsuleGeometry(.065,.16,4,12);g.rotateZ(Math.PI/2);mesh(g,actor.outfit,[sign*.13,0,0],arm);
  const g2=new THREE.CapsuleGeometry(.053,.14,4,12);g2.rotateZ(Math.PI/2);mesh(g2,actor.outfit,[sign*.12,0,0],fore);
  mesh(new THREE.SphereGeometry(.064,12,10),'#e6bea3',[sign*.04,0,0],hand,[1,.7,.65]);
 }
 let mouthNode,eyes=[];
 function mesh(g,color,pos,parent,scale){if(scale)g.scale(...scale);const p={attributes:{POSITION:attr(g.attributes.position.array,'VEC3',true),NORMAL:attr(g.attributes.normal.array,'VEC3')},material:material(color)};if(g.index)p.indices=attr(g.index.array,'SCALAR',false,34963);const idx=meshes.length;meshes.push({primitives:[p]});const n=node('Mesh-'+idx,pos,parent);nodes[n].mesh=idx;return {index:n,primitive:p,geometry:g};}
 mesh(new THREE.CapsuleGeometry(.22,.30,6,16),actor.outfit,[0,.06,0],spine,[1,1,.68]);
 mesh(new THREE.BoxGeometry(.13,.34,.025),actor.kind==='patient'?'#b8a7a0':'#6f9bc2',[0,-.03,.16],chest);
 mesh(new THREE.CylinderGeometry(.065,.07,.15,12),'#e6bea3',[0,.02,0],neck);
 mesh(new THREE.SphereGeometry(.185,24,18),'#edc7ad',[0,.06,0],head,[.9,1.16,.88]);
 mesh(new THREE.SphereGeometry(.191,24,12,0,Math.PI*2,0,1.6),actor.hair,[0,.12,-.02],head,[.94,1.05,.95]);
 if(actor.gender==='female'&&!actor.id.includes('auntie'))mesh(new THREE.CapsuleGeometry(.12,.16,4,12),actor.hair,[0,-.05,-.12],head,[1,.95,.6]);
 mesh(new THREE.SphereGeometry(.038,10,8),'#edc7ad',[0,.045,.163],head,[.5,.75,1]);
 for(const x of [-.066,.066]){
  const e=mesh(new THREE.SphereGeometry(.014,10,8),'#28374b',[x,.082,.148],head);eyes.push(e);
  if(actor.glasses){const g=new THREE.TorusGeometry(.046,.005,6,20);mesh(g,'#40444d',[x,.082,.165],head,[1,.8,1]);}
 }
 if(actor.glasses)mesh(new THREE.BoxGeometry(.05,.005,.008),'#40444d',[0,.082,.168],head);
 mouthNode=mesh(new THREE.SphereGeometry(.027,12,10),'#9d5857',[0,-.022,.156],head,[1,.22,.25]);
 if(actor.profession==='PT')mesh(new THREE.BoxGeometry(.045,.35,.02),'#449c83',[-.15,-.02,.16],chest);
 if(actor.kind==='clinician'&&actor.profession!=='PT')mesh(new THREE.BoxGeometry(.07,.09,.015),'#315d9e',[-.14,-.07,.16],chest);
 // Genuine VRM expression morph targets; geometry stays attached to humanoid head.
 const binds={};
 function morph(obj,name,axis,mult){const source=obj.geometry.attributes.position.array,delta=new Float32Array(source.length);for(let i=axis;i<source.length;i+=3)delta[i]=source[i]*mult;obj.primitive.targets=[{POSITION:attr(delta,'VEC3',true)}];meshes[nodes[obj.index].mesh].weights=[0];binds[name]??=[];binds[name].push({node:obj.index,index:0,weight:1});}
 morph(mouthNode,'aa',1,5);eyes.forEach(e=>morph(e,'blink',1,-.97));
 const expressions={preset:Object.fromEntries(Object.entries(binds).map(([k,morphTargetBinds])=>[k,{morphTargetBinds}]))};
 const gltf={asset:{version:'2.0',generator:'ClinicalTutor original stylized humanoid generator 1'},extensionsUsed:['VRMC_vrm'],extensions:{VRMC_vrm:{specVersion:'1.0',meta:{name:actor.name+' 風格化教學角色',version:'1',authors:['Clinical Tutor project'],licenseUrl:'https://vrm.dev/licenses/1.0/',copyrightInformation:'Original mesh; card reference supplied by user. No third-party card redistribution license granted.',avatarPermission:'onlySeparatelyLicensedPerson',commercialUsage:'personalNonProfit',allowRedistribution:false,modification:'allowModification'},humanoid:{humanBones:Object.fromEntries(Object.entries(boneMap).map(([k,node])=>[k,{node}]))},expressions}},scene:0,scenes:[{nodes:[root]}],nodes,meshes,materials,accessors,bufferViews:views,buffers:[{byteLength:offset}]};
 let json=Buffer.from(JSON.stringify(gltf));json=Buffer.concat([json,Buffer.alloc((4-json.length%4)%4,32)]);let bin=Buffer.concat(parts);bin=Buffer.concat([bin,Buffer.alloc((4-bin.length%4)%4)]);const header=Buffer.alloc(12);header.writeUInt32LE(0x46546c67);header.writeUInt32LE(2,4);header.writeUInt32LE(12+8+json.length+8+bin.length,8);const jc=Buffer.alloc(8);jc.writeUInt32LE(json.length);jc.writeUInt32LE(0x4e4f534a,4);const bc=Buffer.alloc(8);bc.writeUInt32LE(bin.length);bc.writeUInt32LE(0x004e4942,4);fs.writeFileSync(path.join(dir,actor.model_file),Buffer.concat([header,jc,json,bc,bin]));
}
catalog.actors.forEach(build);console.log('Built '+catalog.actors.length+' original VRM 1.0 humanoids');
