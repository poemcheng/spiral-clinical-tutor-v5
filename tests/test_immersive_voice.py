"""Behavior checks for local speech, authorized media and explicit demo grants."""
import json
from pathlib import Path
from unittest.mock import patch
import unittest
from fastapi.testclient import TestClient
from backend import server,progression
from tools.create_demo_learner import create
import test_uploaded_workflow as fixtures

class ImmersiveVoiceTests(unittest.TestCase):
    setUp=fixtures.UploadedWorkflowTests.setUp
    tearDown=fixtures.UploadedWorkflowTests.tearDown
    start=fixtures.UploadedWorkflowTests.start
    interaction=fixtures.UploadedWorkflowTests.interaction

    def test_demo_unlocks_every_profession_topic_without_fabricated_evidence(self):
        uid=create(self.db,'demo-all','Synthetic-Demo-Only-2026!')
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM attempts WHERE user_id=?',(uid,))['n'],0)
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM sessions WHERE user_id=?',(uid,))['n'],0)
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM reviews WHERE teacher_id=?',(uid,))['n'],0)
        for prof in ['MD','RN','RT','DT','PT','OT','RPH','RSP','ST','AUD','CP','MLS']:
            for topic in ['肌少症','懷孕婦女外傷','體驗情境']:
                self.assertEqual(progression.level_state(self.db,uid,prof,topic),5)
                plan=progression.plan(self.db,uid,prof,topic,2)
                self.assertEqual(plan['self_level'],2)
                self.assertEqual(plan['video_count'],3)
                self.assertTrue(all(p['unlocked'] for p in plan['paths']))
                self.assertEqual(plan['completed_practices'],0)
                self.assertIsNone(plan['mastery'])
        with self.assertRaises(ValueError):create(self.db,'demo-all','Would-Reset-Existing!')

    def test_transcription_is_owned_active_and_does_not_create_chat_or_keep_audio(self):
        sid,_=self.interaction('RT')
        result={'text':'請核對本輪已提供的資訊。','seconds':2.1,'model':'synthetic-test','local':True}
        before=self.db.one('SELECT COUNT(*) n FROM messages WHERE session_id=?',(sid,))['n']
        with patch.object(server.speech_input,'transcribe',return_value=result) as recognize:
            response=self.client.post(f'/api/sessions/{sid}/transcribe',content=b'Synthetic audio fixture',headers={'Content-Type':'audio/webm;codecs=opus'})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['text'],result['text']);recognize.assert_called_once()
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM messages WHERE session_id=?',(sid,))['n'],before)
        event=self.db.one("SELECT data FROM events WHERE kind='speech_transcribed' AND session_id=?",(sid,))
        self.assertFalse(json.loads(event['data'])['recording_retained'])
        self.assertEqual(self.faculty.post(f'/api/sessions/{sid}/transcribe',content=b'x',headers={'Content-Type':'audio/wav'}).status_code,403)
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/transcribe',content=b'x',headers={'Content-Type':'text/plain'}).status_code,415)
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/transcribe',content=b'x'*(server.speech_input.MAX_BYTES+1),headers={'Content-Type':'audio/wav'}).status_code,413)
        with TestClient(server.app) as other:
            self.assertEqual(other.post(f'/api/sessions/{sid}/transcribe',content=b'x',headers={'Content-Type':'audio/wav'}).status_code,401)
        with self.db.tx() as c:c.execute("UPDATE sessions SET status='completed' WHERE id=?",(sid,))
        self.assertEqual(self.client.post(f'/api/sessions/{sid}/transcribe',content=b'x',headers={'Content-Type':'audio/wav'}).status_code,409)

    def test_recognition_failure_is_actionable_and_never_changes_decisions(self):
        sid,_=self.interaction('RT')
        for error,status in [(ValueError('錄音無法解碼'),400),(RuntimeError('本機模型尚未安裝'),503),(BlockingIOError('辨識中'),429)]:
            with patch.object(server.speech_input,'transcribe',side_effect=error):
                r=self.client.post(f'/api/sessions/{sid}/transcribe',content=b'fixture',headers={'Content-Type':'audio/wav'})
                self.assertEqual(r.status_code,status);self.assertIn(str(error),r.text)
        self.assertEqual(json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])['decisions'],{})

    def test_interactive_lesson_assets_require_owned_session_and_fixed_names(self):
        sid,_=self.interaction('RT');key='a'*20
        folder=Path(self.tmp.name)/'virtual_lessons'/key;folder.mkdir(parents=True)
        (folder/'immersive.html').write_text('<h1>Synthetic 3D lesson fixture</h1>')
        with self.db.tx() as c:
            payload=json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data']);payload['generated_videos']={'0':{'key':key}};self.db.save(c,sid,payload)
        with patch.object(server,'RUNTIME',Path(self.tmp.name)):
            url=f'/api/sessions/{sid}/generated-lesson/0/immersive.html'
            self.assertEqual(self.client.get(url).status_code,200)
            self.assertEqual(self.faculty.get(url).status_code,200)
            self.assertEqual(self.client.get(f'/api/sessions/{sid}/generated-lesson/0/manifest.json').status_code,404)
            self.assertEqual(self.client.get(f'/api/sessions/{sid}/generated-lesson/99/immersive.html').status_code,404)
            with TestClient(server.app) as anonymous:self.assertEqual(anonymous.get(url).status_code,401)

    def test_local_decoder_rejects_invalid_audio_and_releases_lock(self):
        from backend import speech_input
        if not speech_input.status()['ready']:self.skipTest('Local Whisper model is an optional installed runtime asset')
        with self.assertRaises(ValueError):speech_input.transcribe(b'not an audio recording')
        self.assertFalse(speech_input._lock.locked())
