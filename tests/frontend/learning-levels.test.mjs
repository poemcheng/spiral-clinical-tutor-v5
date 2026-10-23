import test from 'node:test';
import assert from 'node:assert/strict';
import {curriculumPanel,stepExplanation,teachingForFrame} from '../../frontend/learning-levels.js';
test('locked tiers do not render invented lessons and lower tiers remain readable',()=>{
 const lesson={id:'c-L1',title:'基礎',purpose:'目的',knowledge:['知識'],observe:['觀測'],question:'問題',sources:[{title:'來源',location:'任務'}],review_status:'草稿'};
 const r={learning_level:2,lesson_levels:[{level:1,title:'單職類',unlocked:true,lesson_count:1,lessons:[lesson]},{level:2,title:'跨域',unlocked:true,lesson_count:1,lessons:[{...lesson,id:'c-L2'}]},{level:3,title:'影片',unlocked:false,lesson_count:2}]};
 const html=curriculumPanel(r,1);assert.match(html,/c-L1/);assert.match(html,/c-L2/);assert.equal((html.match(/class="lesson-note-form"/g)||[]).length,2);assert.match(html,/尚未解鎖/);
});
test('per-frame purpose uses source step mapping even when pose has no detection',()=>{
 const step={id:'sitstand',title:'<img>',purpose:'坐站目的',explanation:'解說',observe:['逐格'],pitfall:'未觀測不推測',scope:'段落脈絡',review_status:'待核定',sources:[]};
 const f={frame:3,poses:[],teaching_step_id:'sitstand'};const s=teachingForFrame({teaching_steps:[step]},f);assert.equal(s,step);assert.match(stepExplanation(s),/坐站目的/);assert.ok(!stepExplanation(s).includes('<img>'));assert.equal(teachingForFrame({teaching_steps:[]},f),undefined);assert.match(stepExplanation(null),/不能自動指定/);
});
