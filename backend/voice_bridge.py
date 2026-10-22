"""Room-scoped local TTS audio transport. Input transcription is confirmed in the UI.

No independent LLM agent: every utterance already passed the platform's case-bound
chat endpoint and is published from its saved message, with the same audit trail.
"""
import asyncio
import concurrent.futures
import hashlib
import json
import os
import socket
import threading
import wave
from .config import ROOT,RUNTIME

def settings():
 p=ROOT/'runtime/livekit-private.json'
 local=json.loads(p.read_text()) if p.exists() else {}
 return {k:os.getenv(k) or local.get(k,'') for k in ('LIVEKIT_URL','LIVEKIT_API_KEY','LIVEKIT_API_SECRET')}

def ready():
 cfg=settings()
 if not all(cfg.values()):return False
 from urllib.parse import urlparse
 parsed=urlparse(cfg['LIVEKIT_URL'])
 try:
  with socket.create_connection((parsed.hostname,parsed.port or (443 if parsed.scheme=='wss' else 80)),timeout=.5):return True
 except OSError:return False

def room_name(sid):return f"clinical-{hashlib.sha256(str(RUNTIME).encode()).hexdigest()[:8]}-{sid}"

loop=None
thread_lock=threading.Lock()
rooms={}

def event_loop():
 global loop
 with thread_lock:
  if loop is None:
   loop=asyncio.new_event_loop()
   threading.Thread(target=loop.run_forever,name='clinical-voice',daemon=True).start()
 return loop

async def _connect(sid):
 from livekit import rtc
 from .services import livekit_token
 if sid in rooms and rooms[sid]['room'].isconnected():return True
 room=rtc.Room()
 await room.connect(settings()['LIVEKIT_URL'],livekit_token(f'patient-audio-{sid}',room_name(sid)))
 source=rtc.AudioSource(24000,1)
 track=rtc.LocalAudioTrack.create_audio_track('case-bound-patient',source)
 await room.local_participant.publish_track(track,rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE))
 rooms[sid]={'room':room,'source':source,'lock':asyncio.Lock()}
 return True

def connect(sid):
 future=asyncio.run_coroutine_threadsafe(_connect(sid),event_loop())
 try:return future.result(timeout=25)
 except concurrent.futures.TimeoutError:
  future.cancel()
  raise RuntimeError('本機即時語音連線逾時。可繼續文字對話，並以訊息旁的「朗讀回覆」播放角色語音。')

async def _publish(sid,path):
 from livekit import rtc
 import numpy as np
 if sid not in rooms:return False
 state=rooms[sid]
 async with state['lock']:
  with wave.open(str(path),'rb') as wav:
   if wav.getsampwidth()!=2:raise RuntimeError('Expected PCM16')
   samples=np.frombuffer(wav.readframes(wav.getnframes()),dtype=np.int16)
   if wav.getnchannels()>1:samples=samples.reshape(-1,wav.getnchannels()).mean(axis=1)
   rate=wav.getframerate()
  count=round(len(samples)*24000/rate)
  pcm=np.interp(np.arange(count)*rate/24000,np.arange(len(samples)),samples).astype(np.int16)
  for start in range(0,len(pcm),240):
   chunk=pcm[start:start+240];frame=rtc.AudioFrame(data=chunk.tobytes(),sample_rate=24000,num_channels=1,samples_per_channel=len(chunk))
   await state['source'].capture_frame(frame)
  await state['source'].wait_for_playout()
 return True

def publish(sid,path):
 if loop is None or sid not in rooms:return None
 return asyncio.run_coroutine_threadsafe(_publish(sid,path),loop)
