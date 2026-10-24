import test from 'node:test';
import assert from 'node:assert/strict';
import {listeningTurn} from '../../frontend/voice-diagnostic-state.js';

test('silent microphone retries stay on the same prompt',()=>{
 const rounds=[],expected=['first','second'];const first=listeningTurn(rounds,expected).round;
 for(let retry=0;retry<5;retry++){
  const result=listeningTurn(rounds,expected);assert.equal(result.round,first);assert.equal(result.isNew,false);
 }
 assert.equal(rounds.length,1);assert.equal(first.expected,'first');
});

test('a new diagnostic turn requires completed role playback',()=>{
 const rounds=[],expected=['first','second'];const first=listeningTurn(rounds,expected,4).round;
 first.recognition={text:'first'};first.reply={text:'reply'};
 assert.equal(listeningTurn(rounds,expected).isNew,false);
 first.playbackEnded=true;const second=listeningTurn(rounds,expected,5).round;
 assert.equal(second.turn,2);assert.equal(second.inputSeconds,5);assert.equal(second.expected,'second');
 second.playbackEnded=true;assert.throws(()=>listeningTurn(rounds,expected),/測試輪數異常/);
});
