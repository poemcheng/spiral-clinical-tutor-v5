import test from 'node:test';
import assert from 'node:assert/strict';
import {mountEPA} from '../../frontend/epa-panel.js';

function fixture(t,{projection='flat'}={}){
 const old=globalThis.fetch;t.after(()=>{globalThis.fetch=old;});const calls=[];
 const report={title:'EPA',frame_count:1000,detection_frames:900,fps:30,analyzed_every_frame:true,first_frame:0,last_frame:999,
  source_sha256:'a'.repeat(64),model_sha256:'b'.repeat(64),version:'test',projection,view:{yaw:0,pitch:0,fov:70},segments:[],
  keyframes:[{frame:300,id:'K1',seconds:10,title:'代表格'}],media_url:'/original.mp4',annotation_sources:[]};
 globalThis.fetch=async url=>{calls.push(url);return {ok:true,json:async()=>url.endsWith('/report')?report:{frame:Number(url.split('/').at(-1)),seconds:Number(url.split('/').at(-1))/30,poses:[]}};};
 const nodes={};for(const name of ['select','status','report','retry','position','slider','number','overlay','explanation','prev','next','jump','play','panorama'])nodes['.epa-'+name]={textContent:'',value:'',hidden:true};
 nodes['.epa-select'].value='test-clip';nodes['.epa-select'].options=[{value:'test-clip'}];nodes['.epa-overlay'].checked=true;
 const image={};Object.defineProperty(image,'src',{set(v){this.value=v;queueMicrotask(()=>this.onload?.());},get(){return this.value;}});nodes['.epa-image']=image;
 const events={};const video={paused:true,readyState:1,loads:0,plays:0,addEventListener:(n,fn)=>events[n]=fn,
  pause(){this.paused=true;},play(){this.plays++;this.paused=false;return Promise.resolve();},
  hasAttribute(n){return this[n]!==undefined;},removeAttribute(n){delete this[n];},load(){this.loads++;}};nodes['.epa-video']=video;
 const root={dataset:{sid:'1',readonly:'true'},querySelector:s=>nodes[s]||null,querySelectorAll:()=>[]};
 return {root,nodes,video,events,calls};
}
test('EPA opens a representative JPEG without starting original video or WebGL',async t=>{
 const f=fixture(t,{projection:'equirectangular'});let webgl=0;
 const dispose=await mountEPA(f.root,{panoramaLoader:async()=>{webgl++;throw Error('unavailable');}});
 assert.equal(f.nodes['.epa-number'].value,300);assert.match(f.nodes['.epa-image'].src,/frames\/300\/image/);
 assert.equal(f.video.src,undefined);assert.equal(f.video.loads,0);assert.equal(webgl,0);assert.match(f.nodes['.epa-status'].textContent,/已載入/);
 await f.nodes['.epa-next'].onclick();assert.equal(f.nodes['.epa-number'].value,301);
 await f.nodes['.epa-play'].onclick();assert.equal(f.video.src,'/original.mp4');assert.equal(f.video.plays,1);assert.equal(webgl,1);
 assert.match(f.nodes['.epa-status'].textContent,/仍可檢視/);await f.nodes['.epa-next'].onclick();assert.equal(f.nodes['.epa-number'].value,302);dispose();
});
test('Safari seek errors cannot prevent frame controls or evidence from loading',async t=>{
 const f=fixture(t);Object.defineProperty(f.video,'currentTime',{set(){throw Error('Safari seek not ready');}});
 const dispose=await mountEPA(f.root,{initialFrame:0});assert.equal(f.nodes['.epa-number'].value,0);
 await f.nodes['.epa-play'].onclick();f.events.loadedmetadata();await f.nodes['.epa-next'].onclick();
 assert.equal(f.nodes['.epa-number'].value,1);assert.match(f.nodes['.epa-status'].textContent,/已載入/);dispose();
});
test('a stalled report times out with a working retry instead of loading forever',async t=>{
 const f=fixture(t);const working=globalThis.fetch;
 globalThis.fetch=(url,{signal})=>new Promise((resolve,reject)=>signal.addEventListener('abort',()=>reject(Error('aborted'))));
 const dispose=await mountEPA(f.root,{requestTimeoutMs:5});assert.match(f.nodes['.epa-status'].textContent,/逾時/);assert.equal(f.nodes['.epa-retry'].hidden,false);
 globalThis.fetch=working;await f.nodes['.epa-retry'].onclick();assert.match(f.nodes['.epa-status'].textContent,/已載入/);dispose();
});
