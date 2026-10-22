import test from 'node:test';
import assert from 'node:assert/strict';
import {actionSegments,poseMeasurements,poseSnapshot} from '../../frontend/pose-panel.js';
test('motion index keeps person tracks separate and excludes isolated jitter',()=>{
 const frames=[0,1,2,3].map(i=>({seconds:i/30,poses:[{track_id:1,actions:i===3?[]:['左肘彎曲']},{track_id:2,actions:i===1?['右手高於肩部']:[]}]}));
 assert.deepEqual(actionSegments(frames),[{track:1,action:'左肘彎曲',start:0,end:2/30,count:3}]);
});
test('no detections have no fabricated measurements; hypotheses and alternatives escape HTML',()=>{
 assert.match(poseMeasurements([]),/未偵測/);
 const html=poseMeasurements([{track_id:1,visible_joints:12,tracking:'局部',actions:[],metrics:{left_elbow:null},interpretations:[{possible:'<script>',basis:'<img>',alternative:'遮擋',verify:'核對'}]}]);
 assert.ok(!html.includes('<script>'));assert.match(html,/遮擋／無法量測/);assert.match(html,/其他解釋/);
});
