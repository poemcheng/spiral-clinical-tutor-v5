"""3D anatomy and service diagnostics must be real assets, never learner evidence."""
import hashlib
import json
from pathlib import Path
import struct
from types import SimpleNamespace
from unittest.mock import patch
import unittest
import wave
from fastapi.testclient import TestClient
from backend import server,characters
import test_uploaded_workflow as fixtures


class RiggedAssets(unittest.TestCase):
    def test_reference_hairstyles_are_closed_skinned_volumes(self):
        for actor in characters.ACTORS.values():
            blob=(characters.ROOT/'data/characters'/actor['realistic_model_file']).read_bytes()
            g=json.loads(blob[20:20+struct.unpack_from('<I',blob,12)[0]])
            hair=next((m for m in g['meshes'] if m['name'].startswith('Card hairstyle closed 3D volume')),None)
            self.assertIsNotNone(hair,actor['id'])
            primitive=hair['primitives'][0];self.assertIn('JOINTS_0',primitive['attributes'])
            bounds=g['accessors'][primitive['attributes']['POSITION']]
            self.assertGreater(bounds['max'][2]-bounds['min'][2],.04,actor['id'])
            rear=next(m for m in g['meshes'] if m['name']=='Reference fitted rounded rear hair')
            rear_primitive=rear['primitives'][0];self.assertIn('JOINTS_0',rear_primitive['attributes'])
            rear_bounds=g['accessors'][rear_primitive['attributes']['POSITION']]
            self.assertGreater(rear_bounds['max'][2]-rear_bounds['min'][2],.04,actor['id'])

    def test_all_cast_members_have_deep_skinned_geometry_and_facial_shapes(self):
        catalog=json.loads((characters.ROOT/'data/characters/catalog.json').read_text(encoding='utf-8'))
        for actor in catalog['actors']:
            with self.subTest(actor=actor['id']):
                path=characters.ROOT/'data/characters'/actor['realistic_model_file']
                blob=path.read_bytes();self.assertEqual(hashlib.sha256(blob).hexdigest(),actor['realistic_model_sha256'])
                self.assertEqual(blob[:4],b'glTF');size=struct.unpack_from('<I',blob,12)[0];g=json.loads(blob[20:20+size])
                self.assertGreaterEqual(len(g['skins'][0]['joints']),100)
                body=next(m for m in g['meshes'] if m['name'].startswith('base'))
                primitive=body['primitives'][0];attributes=primitive['attributes']
                self.assertIn('JOINTS_0',attributes);self.assertIn('WEIGHTS_0',attributes)
                bounds=g['accessors'][attributes['POSITION']]
                self.assertGreater(bounds['max'][2]-bounds['min'][2],.25)
                self.assertIn('jawOpen',body['extras']['targetNames'])
                self.assertIn('viseme_aa',body['extras']['targetNames'])
                self.assertGreater(len(g['images']),5)
                self.assertEqual(g['materials'][primitive['material']]['alphaMode'],'OPAQUE')


class VoiceDiagnosticTests(unittest.TestCase):
    setUp=fixtures.UploadedWorkflowTests.setUp
    tearDown=fixtures.UploadedWorkflowTests.tearDown
    start=fixtures.UploadedWorkflowTests.start
    interaction=fixtures.UploadedWorkflowTests.interaction

    def test_physical_microphone_mp4_diagnostic_is_owned_and_not_formal_learning(self):
        sid,_=self.interaction('RT');url=f'/api/sessions/{sid}/voice-diagnostic/microphone-transcribe'
        with patch.object(server.speech_input,'transcribe',return_value={'text':'真人測試句','seconds':2,'model':'fixture','local':True}):
            response=self.client.post(url,content=b'mp4 fixture',headers={'Content-Type':'audio/mp4'})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(self.faculty.post(url,content=b'x',headers={'Content-Type':'audio/mp4'}).status_code,403)
            with TestClient(server.app) as anonymous:self.assertEqual(anonymous.post(url,content=b'x',headers={'Content-Type':'audio/mp4'}).status_code,401)
        event=json.loads(self.db.one("SELECT data FROM events WHERE session_id=? AND kind='diagnostic_speech_transcribed'",(sid,))['data'])
        self.assertEqual(event['input_source'],'physical-microphone');self.assertFalse(event['recording_retained'])
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM messages WHERE session_id=?',(sid,))['n'],0)
        self.assertEqual(json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])['decisions'],{})

    def test_two_real_service_turns_are_isolated_from_formal_learning(self):
        sid,_=self.interaction('RT');test_id='d'*32
        before=self.db.one('SELECT COUNT(*) n FROM messages WHERE session_id=?',(sid,))['n']
        def speak(text,target,gender):
            target.parent.mkdir(parents=True,exist_ok=True)
            with wave.open(str(target),'wb') as w:w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(b'\0'*320)
        result=SimpleNamespace(ok=True,text='測試服務回覆，資料缺口需要確認。',model='synthetic-test')
        with patch.object(server,'RUNTIME',Path(self.tmp.name)),patch.object(server.virtual_video,'speech',side_effect=speak),patch.object(server,'patient_reply',return_value=(result,{})) as reply:
            url=f'/api/sessions/{sid}/voice-diagnostic'
            self.assertEqual(self.client.get(url+'/input/3').status_code,404)
            self.assertEqual(self.client.get(url+'/input/1').status_code,200)
            self.assertEqual(self.faculty.post(url+'/reply',json={'text':'測試','test_id':test_id}).status_code,403)
            with TestClient(server.app) as anonymous:self.assertEqual(anonymous.get(url+'/input/1').status_code,401)
            for turn in (1,2):
                r=self.client.post(url+'/reply',json={'text':'請核對資料。','test_id':test_id})
                self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['turn'],turn)
                self.assertTrue(r.json()['diagnostic']);self.assertEqual(self.client.get(r.json()['audio_url']).status_code,200)
            self.assertEqual(reply.call_count,2)
            self.assertEqual(self.client.post(url+'/reply',json={'text':'第三輪','test_id':test_id}).status_code,409)
            self.assertEqual(self.client.get(url+'/output/'+'e'*32+'/1').status_code,404)
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM messages WHERE session_id=?',(sid,))['n'],before)
        self.assertEqual(json.loads(self.db.one('SELECT data FROM sessions WHERE id=?',(sid,))['data'])['decisions'],{})

    def test_diagnostic_transcription_uses_same_decoder_with_explicit_source(self):
        sid,_=self.interaction('RT')
        with patch.object(server.speech_input,'transcribe',return_value={'text':'測試音源','seconds':2,'model':'fixture','local':True}) as decoder:
            r=self.client.post(f'/api/sessions/{sid}/voice-diagnostic/transcribe',content=b'test',headers={'Content-Type':'audio/webm'})
            self.assertEqual(r.status_code,200,r.text);decoder.assert_called_once_with(b'test')
        e=json.loads(self.db.one("SELECT data FROM events WHERE session_id=? AND kind='diagnostic_speech_transcribed'",(sid,))['data'])
        self.assertEqual(e['input_source'],'controlled-test-audio');self.assertFalse(e['recording_retained'])
