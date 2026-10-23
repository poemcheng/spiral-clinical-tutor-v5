"""LiveKit Agents: local Whisper + the audited case chat route + gendered TTS.

No independent medical prompt, no API key in the browser, no agent-side recording.
"""
import asyncio,io,json,secrets,time,wave
from . import voice_bridge
active={}
preparation_error=''

def available():
    import importlib.util
    try:return bool(importlib.util.find_spec('livekit.agents') and importlib.util.find_spec('livekit.plugins.silero'))
    except ModuleNotFoundError:return False

def prepare():
    # LiveKit requires plugin registration on the process main thread.
    # FastAPI route handlers run in worker threads, so register during import.
    if available():
        import importlib
        importlib.import_module('livekit.plugins.silero')

async def close(sid):
    state=active.pop(sid,None)
    if state:
        await state['session'].aclose()
        if state['room'].isconnected():await state['room'].disconnect()

async def launch(sid,user,identity):
    from livekit import rtc
    from livekit.agents import Agent,AgentSession,stt,llm,room_io,DEFAULT_API_CONNECT_OPTIONS
    from livekit.plugins import silero
    from . import server,speech_input,virtual_video,characters
    from .config import RUNTIME
    if sid in active:await close(sid)
    class Whisper(stt.STT):
        def __init__(self):super().__init__(capabilities=stt.STTCapabilities(streaming=False,interim_results=False))
        async def _recognize_impl(self,buffer,*,language=None,conn_options=None):
            frames=buffer if isinstance(buffer,list) else [buffer];memory=io.BytesIO()
            with wave.open(memory,'wb') as wav:
                wav.setnchannels(frames[0].num_channels);wav.setsampwidth(2);wav.setframerate(frames[0].sample_rate)
                for frame in frames:wav.writeframes(bytes(frame.data))
            result=await asyncio.to_thread(speech_input.transcribe,memory.getvalue())
            return stt.SpeechEvent(type=stt.SpeechEventType.FINAL_TRANSCRIPT,alternatives=[stt.SpeechData(language='zh',text=result['text'])])
    room=rtc.Room();await room.connect(voice_bridge.settings()['LIVEKIT_URL'],server.livekit_token('agent-'+identity,voice_bridge.room_name(sid)))
    state={'gender':characters.selected(server.owned_session(sid,user))['gender']}
    class AuditedLLM(llm.LLM):
        @property
        def model(self):return server.llm.model
        @property
        def provider(self):return 'platform-audited-ollama'
        def chat(self,*,chat_ctx,tools=None,conn_options=DEFAULT_API_CONNECT_OPTIONS,**kwargs):
            return AuditedStream(self,chat_ctx=chat_ctx,tools=tools or [],conn_options=conn_options)
    class AuditedStream(llm.LLMStream):
        async def _run(self):
            valid=server.store.one('SELECT id FROM logins WHERE id=? AND user_id=? AND expires>?',(user['login_id'],user['id'],time.time()))
            if not valid:return
            text=next((item.text_content for item in reversed(self._chat_ctx.items) if getattr(item,'role',None)=='user' and getattr(item,'text_content',None)),'')
            if not text:return
            response=await asyncio.to_thread(server.chat,sid,server.ChatBody(text=text,mode='ai',request_id='agent-'+secrets.token_hex(16)),user)
            await room.local_participant.publish_data(json.dumps({'type':'clinical-reply',**response},ensure_ascii=False).encode(),reliable=True,topic='clinical-agent',destination_identities=[identity])
            if not response.get('ok'):return
            state['gender']=response['metadata']['actor']['gender']
            self._event_ch.send_nowait(llm.ChatChunk(id=response['metadata']['request_id'],delta=llm.ChoiceDelta(role='assistant',content=response['text'])))
            if response.get('conversation',{}).get('phase')=='closed':session.input.set_audio_enabled(False)
    class CaseAgent(Agent):
        def __init__(self):super().__init__(instructions='依本輪已保存教案與角色交談；正式回覆一律經平台情境引擎。')
        async def tts_node(self,text,model_settings):
            chunks=[]
            async for chunk in text:chunks.append(chunk)
            if not chunks:return
            path=RUNTIME/'speech'/('agent-'+str(sid)+'-'+secrets.token_hex(8)+'.wav')
            try:
                await asyncio.to_thread(virtual_video.speech,''.join(chunks),path,state['gender'])
                with wave.open(str(path),'rb') as wav:
                    rate=wav.getframerate();channels=wav.getnchannels();size=max(1,rate//50)
                    while data:=wav.readframes(size):yield rtc.AudioFrame(data=data,sample_rate=rate,num_channels=channels,samples_per_channel=len(data)//(2*channels))
            finally:
                for file in (path,path.with_suffix('.txt'),path.with_suffix('.wav.voice.json')):file.unlink(missing_ok=True)
    session=AgentSession(stt=Whisper(),llm=AuditedLLM(),vad=silero.VAD.load(),allow_interruptions=True,min_endpointing_delay=.65,max_endpointing_delay=2.2)
    @session.on('user_state_changed')
    def user_state(event):
        if event.new_state=='speaking' and session.agent_state=='speaking':
            with server.store.tx() as c:server.store.event(c,user['id'],sid,'voice_agent_interrupted',{'transport':'LiveKit Agents','actor_audio_interrupted':True})
    await session.start(CaseAgent(),room=room,room_options=room_io.RoomOptions(participant_identity=identity,text_input=False),record=False)
    active[sid]={'session':session,'room':room,'identity':identity,'user_id':user['id']}
    return True

def start(sid,user,identity):
    future=asyncio.run_coroutine_threadsafe(launch(sid,user,identity),voice_bridge.event_loop())
    try:return future.result(timeout=45)
    except Exception:
        future.cancel();raise

def stop(sid):
    return asyncio.run_coroutine_threadsafe(close(sid),voice_bridge.event_loop()).result(timeout=15)
