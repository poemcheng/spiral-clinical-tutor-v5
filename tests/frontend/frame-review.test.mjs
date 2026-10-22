import test from 'node:test';
import assert from 'node:assert/strict';
import {frameObservation,frameEvidence} from '../../frontend/frame-review.js';
const note={clip_id:'fixture',seconds:1.001,frame:30,yaw:20,pitch:5,observation:'觀察交接<script>alert(1)</script>',review_status:'待教師覆核'};
test('learner sees feedback history without a teacher form and all text is escaped',()=>{
 const html=frameObservation(note,0,[{note_index:0,id:'a',teacher:'教師<img>',created:1,decision:'reviewed',feedback:'已核對<證據>'}]);
 assert.ok(html.includes('教師已檢視'));assert.ok(html.includes('&lt;script&gt;'));assert.ok(html.includes('&lt;證據&gt;'));
 assert.ok(!html.includes('<script>'));assert.ok(!html.includes('<form'));assert.ok(html.includes('舊紀錄未包含媒體雜湊'));
});
test('teacher concurrency token follows this observation, never another observation',()=>{
 const reviews=[{note_index:0,id:'first',teacher:'A',created:1,decision:'reviewed',feedback:'第一版'}, {note_index:1,id:'other',teacher:'B',created:2,decision:'reviewed',feedback:'其他觀察'}, {note_index:0,id:'latest',teacher:'A',created:3,decision:'needs_revision',feedback:'第二版'}];
 const html=frameObservation(note,0,reviews,true);
 assert.ok(html.includes('data-expected-review="latest"'));assert.ok(!html.includes('其他觀察'));assert.ok(html.includes('第一版'));assert.ok(html.includes('第二版'));
});
test('empty evidence and existing notes without reviews remain usable',()=>{
 assert.ok(frameEvidence().includes('尚無逐格觀察紀錄'));
 assert.ok(frameEvidence([note]).includes('待教師回饋'));
});
