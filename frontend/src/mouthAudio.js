import {WLipSyncEngine} from 'three-vrm-lip-sync';

// Use the package's MFCC engine for anatomical GLB rigs as well as VRM.
// The caller owns playback; this graph is analysis-only and cannot double audio.
export async function createMouthAudio(context,source){
 const engine=await WLipSyncEngine.create(context,{gain:1.15,smoothness:.065});
 source.connect(engine.input);
 const silent=context.createGain();silent.gain.value=0;engine.input.connect(silent);silent.connect(context.destination);
 return {get weights(){return engine.weights;},get volume(){return engine.volume;},dispose(){try{source.disconnect(engine.input);}catch{}engine.dispose();silent.disconnect();}};
}
