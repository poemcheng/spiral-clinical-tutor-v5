import test from 'node:test';import assert from 'node:assert/strict';
import {lectureModuleCard} from '../../frontend/lecture-library.js';
test('remote students get inline playback and readable transcript without a generation button',()=>{
 const library={lectures:[{actor_name:'講師',actor_gender:'male',lecturer_scope:'本職任務',source_fingerprint:'a'.repeat(64),teaching_purpose:'觀察與交接',review_status:'待審',modules:[{module:0,title:'情境',duration:12,url:'/fixture.mp4',transcript:'<文字稿>'}]}]};
 const html=lectureModuleCard('來源教案',0,{library,canGenerate:false,readonly:false});
 assert.match(html,/playsinline/);assert.match(html,/可直接播放/);assert.match(html,/&lt;文字稿&gt;/);assert.doesNotMatch(html,/generate-video|autoplay/);assert.match(html,/module-done/);
});
