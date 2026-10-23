import test from 'node:test';
import assert from 'node:assert/strict';
import {setImmediate as nextTick} from 'node:timers/promises';
import {createVoiceInput} from '../../frontend/voice.js';

function harness(){
 let now=0,sound=false,serial=0,stopped=0;const frames=new Map(),timers=new Map(),requests=[],texts=[],events=[];
 globalThis.performance={now:()=>now};globalThis.document={querySelector:()=>null};globalThis.window={MediaRecorder:true};
 globalThis.requestAnimationFrame=fn=>{const id=++serial;frames.set(id,fn);return id;};globalThis.cancelAnimationFrame=id=>frames.delete(id);
 globalThis.setTimeout=(fn,ms)=>{const id=++serial;timers.set(id,{fn,ms});return id;};globalThis.clearTimeout=id=>timers.delete(id);
 const stream={getTracks:()=>[{stop(){stopped++;}}]};
 globalThis.AudioContext=class{resume(){return Promise.resolve();}close(){return Promise.resolve();}createMediaStreamSource(){return{connect(){}};}createAnalyser(){return{fftSize:1024,getByteTimeDomainData(a){a.fill(sound?150:128);}};}};
 globalThis.MediaRecorder=class{static isTypeSupported(){return true;}constructor(){this.state='inactive';this.mimeType='audio/webm';}start(){this.state='recording';}stop(){this.state='inactive';this.ondataavailable({data:new Blob(['synthetic audio'])});this.onstop();}};
 globalThis.fetch=async(url,opts)=>{requests.push({url,opts});return{ok:true,json:async()=>({text:'合成語音'})};};
 const c=createVoiceInput({sid:123,inputStreamFactory:async()=>stream,onText:t=>texts.push(t),onStatus:(t,s)=>events.push(s),onError:e=>{throw e;},onListening:v=>events.push(v?'listening-start':'listening-stop')});
 return{c,texts,events,requests,stream,get stopped(){return stopped;},sound(v){sound=v;},frame(t){now=t;const old=[...frames.values()];frames.clear();old.forEach(fn=>fn());},retry(){for(const [id,x] of [...timers])if(x.ms===0){timers.delete(id);x.fn();}}};
}
test('one start keeps silence alive and does not send silent recordings',async()=>{
 const h=harness();await h.c.start();h.frame(12100);await nextTick();h.retry();await nextTick();
 assert.equal(h.c.enabled,true);assert.equal(h.requests.length,0);assert.equal(h.events.filter(x=>x==='listening-start').length,2);
 h.c.stop();assert.equal(h.c.enabled,false);assert.ok(h.stopped>0);
});
test('two turns resume without another start, then cancellation prevents a late transcript',async()=>{
 const h=harness();h.sound(true);await h.c.start();h.sound(false);h.frame(2500);await nextTick();assert.equal(h.texts.length,1);
 h.c.pause();h.sound(true);await h.c.resume();h.sound(false);h.frame(5000);await nextTick();assert.equal(h.texts.length,2);
 let resolve;globalThis.fetch=()=>new Promise(r=>{resolve=r;});h.c.pause();h.sound(true);await h.c.resume();h.sound(false);h.frame(7500);
 h.c.stop();resolve({ok:true,json:async()=>({text:'不應送出的過期逐字稿'})});await nextTick();assert.equal(h.texts.length,2);assert.equal(h.c.enabled,false);
});
test('cancelling a pending permission request stops a microphone acquired later',async()=>{
 const h=harness();let provide;const late=new Promise(r=>{provide=r;});
 const c=createVoiceInput({sid:1,inputStreamFactory:()=>late,onText:()=>assert.fail('late text'),onStatus:()=>{},onError:e=>assert.fail(e.message)});
 const start=c.start();c.stop();provide(h.stream);await start;await nextTick();assert.equal(c.enabled,false);assert.ok(h.stopped>0);
});

test('sustained speech can interrupt playback after one start; stop cancels the monitor',async()=>{
 const h=harness();await h.c.start();h.c.pause();let interruptions=0;
 h.c.watchInterrupt(()=>{interruptions++;});h.sound(true);h.frame(100);h.frame(500);
 assert.equal(interruptions,1);assert.equal(h.c.enabled,true);
 h.c.watchInterrupt(()=>{interruptions++;});h.c.stop();h.frame(1000);assert.equal(interruptions,1);
});
