// A silent retry belongs to the current turn; only completed playback advances it.
export function listeningTurn(rounds, expected, inputSeconds=null) {
  const current=rounds.at(-1);
  if(current&&!current.playbackEnded)return {round:current,isNew:false};
  const index=rounds.length;
  if(index>=expected.length)throw Error('測試輪數異常');
  const round={turn:index+1,expected:expected[index],inputSeconds,maxOutputRms:0,playbackEnded:false};
  rounds.push(round);return {round,isNew:true};
}
