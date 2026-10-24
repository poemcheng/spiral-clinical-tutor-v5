import test from 'node:test';
import assert from 'node:assert/strict';
import {branchingEvidence,recordResult} from '../../frontend/branching-ui.js';

test('teacher feedback stays scoped to its run and is escaped in learner readback',()=>{
 const run={id:'a'.repeat(32),title:'來源教案',updated:1,actor:{display_name:'治療師'},case_hash:'f'.repeat(64),summary:{outcome:'safety-remediation',choices:[{phase:'判讀',choice:'先核對',feedback:'返回來源',critical_error:true}]}};
 const data={branching_runs:[run],branching_reviews:[{id:'b'.repeat(32),run_id:run.id,teacher:'驗收教師',created:1,feedback:'<script>test</script> 請核對資料界線'},{run_id:'another',teacher:'他人',created:1,feedback:'另一輪回饋'}]};
 const learner=branchingEvidence(data),teacher=branchingEvidence(data,true);
 assert.match(learner,/&lt;script&gt;test&lt;\/script&gt;/);assert.doesNotMatch(learner,/<script>|另一輪回饋|branch-review-form/);
 assert.match(teacher,/data-expected-review="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"/);assert.match(learner,/安全分支需補強/);
});

test('missing record explanation remains visible without invented normal results',()=>{
 const html=recordResult({title:'檢查',message:'教案未提供此類紀錄；不能視為檢查正常。',excerpts:[],source_file:'<source>',source_hash:'f'.repeat(64)});
 assert.match(html,/不能視為檢查正常/);assert.match(html,/&lt;source&gt;/);assert.doesNotMatch(html,/<blockquote>/);
});
