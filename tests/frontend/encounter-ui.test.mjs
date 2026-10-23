import test from 'node:test';
import assert from 'node:assert/strict';
import {interactionStage,conversationState} from '../../frontend/encounter-ui.js';
test('face-to-face stage keeps input controls, context and a continuing closing proposal',()=>{
 const actor={id:'wang-pt',name:'王治療師',kind:'clinician',title:'物理治療師'},entry={target:'PT',actor_id:'wang-pt',title:'交接<test>',task:'核對資料',state:'active'};
 const html=interactionStage({id:1,profession:'RT',level:3,data:{case:{title:'合成測試',patient:'無真實病歷'}}},{encounter:entry,encounter_plan:{entries:[entry]},difficulty:{label:'理由追問',behavior:'追問依據'},resources:{},trust:50},{interaction:actor},{ollama:{ready:true,model:'synthetic'}},'');
 for(const id of ['avatar','chat-form','chat-text','chatlog','current-reply','reply-audio','voice-status'])assert.ok(html.includes(`id="${id}"`));
 assert.ok(html.includes('交接&lt;test&gt;'));assert.ok(!html.includes('交接<test>'));
 assert.equal(conversationState({conversation:{phase:'closing'}}).closed,false);
 assert.equal(conversationState({conversation:{phase:'closed'}}).closed,true);
});
