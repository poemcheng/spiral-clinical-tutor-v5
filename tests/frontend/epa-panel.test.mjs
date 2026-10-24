import test from 'node:test';
import assert from 'node:assert/strict';
import {epaLibraryPanel} from '../../frontend/epa-panel.js';
import {epaAnnotation,bodyRegionSummary} from '../../frontend/epa-content.js';
test('EPA panel requires earned unlock and separates frame coverage from intent claims',()=>{
 assert.equal(epaLibraryPanel({unlocked:false,analyses:[{clip_id:'secret'}]},1),'');
 const h=epaLibraryPanel({unlocked:true,analyses:[{clip_id:'a',title:'<script>',frame_count:14843,projection:'flat'}]},1);
 assert.match(h,/Level 4/);assert.match(h,/14,843/);assert.ok(!h.includes('<script>'));assert.match(h,/&lt;script&gt;/);
});
test('reference annotations escape text and missing body joints cannot become measured facts',()=>{
 const h=epaAnnotation({title:'test',dialogue_function:'<img onerror=x>',visible_action:'<script>'},{qualitative_pose:{trunk:'人工約略估計'}});
 assert.ok(!h.includes('<img onerror'));assert.match(h,/非精確量測/);assert.match(h,/非逐字稿/);
 assert.match(bodyRegionSummary([]),/沒有可靠/);assert.match(bodyRegionSummary([{track_id:1,metrics:{left_elbow:null}}]),/遮擋/);
});
