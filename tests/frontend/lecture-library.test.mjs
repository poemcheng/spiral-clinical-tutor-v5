import test from 'node:test';import assert from 'node:assert/strict';
import {lectureModuleCard,lectureModule} from '../../frontend/lecture-library.js';
import {characterPanel} from '../../frontend/characters.js';
test('remote students get inline playback and readable transcript without a generation button',()=>{
 const library={lectures:[{actor_name:'講師',actor_gender:'male',lecturer_scope:'本職任務',source_fingerprint:'a'.repeat(64),teaching_purpose:'觀察與交接',review_status:'待審',modules:[{module:0,title:'情境',duration:12,url:'/fixture.mp4',transcript:'<文字稿>'}]}]};
 const html=lectureModuleCard('來源教案',0,{library,canGenerate:false,readonly:false});
 assert.match(html,/playsinline/);assert.match(html,/可直接播放/);assert.match(html,/&lt;文字稿&gt;/);assert.doesNotMatch(html,/generate-video|autoplay/);assert.match(html,/module-done/);
});
test('missing publication explains the actual cause and escapes source messages',()=>{
 const html=lectureModule({status:'not_published',message:'此教案未發布 <script>'},0);
 assert.match(html,/此教案未發布 &lt;script&gt;/);assert.doesNotMatch(html,/此講師的已發布影片尚未安裝/);
});
test('an empty installed lecturer list does not offer every unavailable lecturer',()=>{
 const actor={id:'a',name:'講師',kind:'clinician',gender:'male'};
 const html=characterPanel({lecturer:actor,catalog:{actors:[actor]},published_actors:[]},'lecturer');
 assert.match(html,/0 位/);assert.doesNotMatch(html,/data-action="select-actor"/);
});
