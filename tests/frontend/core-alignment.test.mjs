import test from 'node:test';
import assert from 'node:assert/strict';
import {competencyRadar} from '../../frontend/visuals.js';
import {teamKnowledgePanel} from '../../frontend/learning-levels.js';

test('missing core domains are unassessed, not zero-score points, and labels wrap safely',()=>{
 const p={indicators:[{id:'a',name:'營養專業知識'},{id:'b',name:'人際關係及溝通技巧'},{id:'c',name:'<img>專業素養'}]};
 const html=competencyRadar({a:80,b:null},'test',p);
 assert.equal((html.match(/<circle /g)||[]).length,1);
 assert.match(html,/未評估/);assert.match(html,/viewBox="0 0 520 430"/);assert.match(html,/&lt;img&gt;/);assert.ok(!html.includes('<img>'));
 assert.ok(!html.includes('0.0 / 5'));
});
test('locked Level 2 team guide exposes no cards; unlocked guide has role and handoff knowledge',()=>{
 assert.equal(teamKnowledgePanel({unlocked:false}), '');
 const html=teamKnowledgePanel({unlocked:true,note:'獨立解鎖',source_file:'指南.png',version_note:'版本核對',roles:[{label:'營養',focus:'飲食',is_own:true,knowledge:['攝食評估'],core_task:'個別化',provide:'份量',request:'功能',core_competencies:['營養照護能力']}],references:[]});
 assert.match(html,/我的職種/);assert.match(html,/提供團隊的資訊/);assert.match(html,/營養照護能力/);assert.match(html,/原圖尚未安裝/);
});
