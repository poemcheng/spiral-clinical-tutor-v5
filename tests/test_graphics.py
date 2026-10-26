"""Isolated domain acceptance tests. No clinical DB, model server or real students."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient
from backend.graphics_server import create_app
from backend.graphics_curriculum import DIMENSIONS, TASKS, FIELDS


class GraphicsAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app(Path(self.tmp.name) / 'graphics.sqlite3', bootstrap=False)
        self.store = self.app.state.store
        self.clients = {}
        self.ids = {}
        for name, role in [('student', 'student'), ('peer', 'student'), ('outsider', 'student'), ('teacher', 'teacher'), ('admin', 'admin')]:
            self.ids[name] = self.store.create_user(name, 'Test-password-1234', role, name)
            client = TestClient(self.app)
            result = client.post('/api/auth/login', json={'username': name, 'password': 'Test-password-1234'})
            self.assertEqual(result.status_code, 200)
            self.clients[name] = client
        self.student, self.teacher, self.admin = [self.clients[n] for n in ('student', 'teacher', 'admin')]
        self.team = self.teacher.post('/api/teams', json={'name': '測試小組', 'members': [self.ids['student'], self.ids['peer']]}).json()['id']

    def tearDown(self):
        for client in self.clients.values():
            client.close()
        self.store.conn.close()
        self.tmp.cleanup()

    def start(self, task='part-bracket', team=True):
        result = self.student.post('/api/trainings', json={'task_id': task, 'team_id': self.team if team else None, 'support_level': 3})
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def advance(self, work, **overrides):
        step = work['step']
        values = {f[0]: '具體測試紀錄：基準約束、尺寸變更與驗證結果' for f in FIELDS[step]}
        if step == 1:
            values.update(self={d['id']: 3 for d in DIMENSIONS}, answer=1)
        if step == 4:
            values['ai_use'] = 'not_used'
        if step == 5:
            values['answer'] = 1
        values.update(overrides)
        result = self.student.post(f"/api/trainings/{work['id']}/work", json={'revision': work['revision'], 'advance': True, 'values': values})
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def to_step(self, target=4):
        work = self.start()
        while work['step'] < target:
            if work['step'] == 3:
                self.upload(work)
            work = self.advance(work)
        return work

    def upload(self, work):
        result = self.student.post(f"/api/trainings/{work['id']}/artifacts?filename=model.step", content=b'ISO-10303-21; teaching fixture')
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def test_complete_student_teacher_export_and_relogin(self):
        work = self.to_step(6)
        self.assertEqual(work['data']['practice'], {'pre': 1, 'transfer': 1})
        work = self.advance(work)
        self.assertEqual(work['status'], 'submitted')
        review = {'scores': {'procedure': 2, 'concept': 3, 'collaboration': None, 'reflection': 2},
                  'evidence': '依model.step與個人設計意圖說明覆核', 'next_action': '下一輪更換基準並測試尺寸依存',
                  'decision': 'revise', 'approved_level': 2}
        response = self.teacher.post(f"/api/trainings/{work['id']}/reviews", json=review)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['reviews'][0]['data']['scores']['collaboration'], None)
        self.student.post('/api/auth/logout')
        self.assertEqual(self.student.get('/api/me').status_code, 401)
        self.student.post('/api/auth/login', json={'username': 'student', 'password': 'Test-password-1234'})
        report = self.student.get(f"/api/trainings/{work['id']}/export").json()
        self.assertEqual(report['status'], 'revise')
        self.assertEqual(report['data']['1']['self']['concept'], 3)
        self.assertTrue(any(e['kind'] == 'teacher_reviewed' for e in report['events']))
        self.assertIn('snapshot', self.store.one('SELECT * FROM graphics_trainings WHERE id=?', (work['id'],)))
        reopened = create_app(Path(self.tmp.name) / 'graphics.sqlite3', bootstrap=False)
        self.assertEqual(reopened.state.store.one('SELECT status FROM graphics_trainings WHERE id=?', (work['id'],))['status'], 'revise')
        reopened.state.store.conn.close()

    def test_no_keys_in_catalog_or_public_snapshot(self):
        result = self.student.get('/api/catalog').json()
        self.assertNotIn('pre', result['tasks'][0])
        work = self.start()
        self.assertNotIn('answer', work['question'])
        self.assertNotIn('transfer', work['task'])
        self.assertEqual(self.student.get(f"/api/trainings/{work['id']}/export").status_code, 409)

    def test_owner_isolation_and_administrator_not_teacher(self):
        work = self.start()
        for name in ('peer', 'outsider', 'admin'):
            self.assertEqual(self.clients[name].get(f"/api/trainings/{work['id']}").status_code, 404)
        self.assertEqual(self.admin.get('/api/trainings').json(), [])
        self.assertEqual(self.student.get('/api/users').status_code, 403)
        self.assertEqual(self.student.get('/api/lessons').status_code, 403)
        self.assertEqual(self.teacher.get(f"/api/trainings/{work['id']}").status_code, 200)

    def test_invalid_team_and_roles(self):
        self.assertEqual(self.clients['outsider'].post('/api/trainings', json={'task_id': 'part-bracket', 'team_id': self.team}).status_code, 403)
        self.assertEqual(self.admin.post('/api/trainings', json={'task_id': 'part-bracket'}).status_code, 403)
        self.assertEqual(self.teacher.post('/api/teams', json={'name': '重複', 'members': [self.ids['student']]*2}).status_code, 400)
        self.assertEqual(self.student.post('/api/users', json={'username': 'test', 'password': 'long-password', 'display_name': 'test', 'role': 'teacher'}).status_code, 403)

    def test_revision_conflict_and_required_fields(self):
        work = self.start()
        url = f"/api/trainings/{work['id']}/work"
        draft = {'revision': 0, 'values': {'baseline_reason': '先保存草稿'}}
        self.assertEqual(self.student.post(url, json=draft).status_code, 200)
        self.assertEqual(self.student.post(url, json=draft).status_code, 409)
        self.assertEqual(self.student.post(url, json={'revision': 1, 'advance': True, 'values': {}}).status_code, 400)
        self.assertEqual(self.student.post(url, json={'revision': 1, 'values': {'approved_level': 5}}).status_code, 400)

    def test_bool_is_not_a_score(self):
        work = self.start()
        result = self.student.post(f"/api/trainings/{work['id']}/work", json={'revision': 0, 'values': {'answer': True}})
        self.assertEqual(result.status_code, 400)
        self.assertEqual(self.student.post('/api/trainings', json={'task_id': 'part-bracket', 'support_level': True}).status_code, 422)

    def test_upload_access_signature_hash_and_sharing_projection(self):
        work = self.to_step(3)
        file = self.upload(work)
        self.assertEqual(self.clients['peer'].get(f"/api/artifacts/{file['id']}").status_code, 404)
        self.assertEqual(self.student.post(f"/api/trainings/{work['id']}/artifacts?filename=evil.html", content=b'html').status_code, 400)
        self.assertEqual(self.student.post(f"/api/trainings/{work['id']}/artifacts?filename=fake.png", content=b'not png').status_code, 400)
        work = self.advance(work)
        self.student.post(f"/api/trainings/{work['id']}/share", json={'shared': True})
        peers = self.clients['peer'].get(f'/api/teams/{self.team}/work').json()
        self.assertEqual(len(peers), 1)
        self.assertNotIn('self', peers[0]['work'])
        self.assertNotIn('reviews', peers[0])
        self.assertEqual(self.clients['peer'].get(f"/api/artifacts/{file['id']}").status_code, 200)
        self.assertEqual(self.clients['outsider'].get(f'/api/teams/{self.team}/work').status_code, 404)
        self.student.post(f"/api/trainings/{work['id']}/share", json={'shared': False})
        self.assertEqual(self.clients['peer'].get(f"/api/artifacts/{file['id']}").status_code, 404)
        stored = self.store.one('SELECT storage_key FROM graphics_artifacts WHERE id=?', (file['id'],))
        (self.app.state.home / 'artifacts' / stored['storage_key']).write_bytes(b'tampered')
        self.assertEqual(self.student.get(f"/api/artifacts/{file['id']}").status_code, 409)

    def test_no_ai_during_baseline_and_transfer(self):
        work = self.start()
        payload = {'question': '請幫我寫答案', 'level': 2}
        self.assertEqual(self.student.post(f"/api/trainings/{work['id']}/hint", json=payload).status_code, 409)
        work = self.advance(work)
        result = self.student.post(f"/api/trainings/{work['id']}/hint", json=payload)
        self.assertEqual(result.status_code, 200)
        self.assertIn('規則式', result.json()['source'])
        unchanged = self.student.get(f"/api/trainings/{work['id']}").json()
        self.assertEqual(unchanged['status'], 'active')
        self.assertEqual(unchanged['reviews'], [])
        while work['step'] < 5:
            if work['step'] == 3:
                self.upload(work)
            work = self.advance(work)
        self.assertEqual(self.student.post(f"/api/trainings/{work['id']}/hint", json=payload).status_code, 409)
        self.assertNotIn('practice', work['data'])

    def test_evidence_required_and_submitted_work_frozen(self):
        work = self.to_step(3)
        values = {f[0]: '說明' for f in FIELDS[3]}
        self.assertEqual(self.student.post(f"/api/trainings/{work['id']}/work", json={'revision': work['revision'], 'advance': True, 'values': values}).status_code, 400)
        self.upload(work)
        while work['status'] == 'active':
            work = self.advance(work)
        self.assertEqual(self.student.post(f"/api/trainings/{work['id']}/work", json={'revision': work['revision'], 'values': {}}).status_code, 409)
        self.assertEqual(self.student.post(f"/api/trainings/{work['id']}/artifacts?filename=x.txt", content=b'test').status_code, 409)

    def test_teacher_only_review_and_append_only_history(self):
        work = self.to_step(6)
        work = self.advance(work)
        payload = {'scores': {d['id']: 2 for d in DIMENSIONS}, 'evidence': '依據學生個人證據', 'next_action': '請做不同尺寸的遷移測試', 'decision': 'approved', 'approved_level': 3}
        for name in ('student', 'admin'):
            self.assertEqual(self.clients[name].post(f"/api/trainings/{work['id']}/reviews", json=payload).status_code, 403)
        for decision in ('revise', 'approved'):
            payload['decision'] = decision
            result = self.teacher.post(f"/api/trainings/{work['id']}/reviews", json=payload)
            self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.json()['reviews']), 2)

    def test_role_rotation_and_individual_mode(self):
        first = self.start()
        second = self.start('assembly-slider')
        self.assertNotEqual(first['role'], second['role'])
        solo = self.start(team=False)
        self.assertIn('個人練習', solo['role'])

    def test_teacher_lessons_publish_version_and_snapshot_retention(self):
        task = {k: copy.deepcopy(v) for k, v in TASKS[0].items() if k not in ('id', 'source_ids')}
        body = {'revision': 0, 'publish': False, 'task': task}
        created = self.teacher.post('/api/lessons', json=body).json()
        self.assertNotIn(created['id'], [t['id'] for t in self.student.get('/api/catalog').json()['tasks']])
        self.assertEqual(self.student.post('/api/trainings', json={'task_id': created['id']}).status_code, 404)
        body.update(revision=1, publish=True)
        self.assertEqual(self.teacher.put('/api/lessons/'+created['id'], json=body).status_code, 200)
        work = self.start(created['id'])
        old_hash = work['spec_hash']
        body['revision'] = 2
        body['task']['title'] = '新修訂課程：穩健設計與變更驗證'
        self.assertEqual(self.teacher.put('/api/lessons/'+created['id'], json=body).status_code, 200)
        existing = self.student.get(f"/api/trainings/{work['id']}").json()
        self.assertEqual(existing['spec_hash'], old_hash)
        self.assertNotEqual(self.start(created['id'])['spec_hash'], old_hash)
        self.assertEqual(self.teacher.put('/api/lessons/'+created['id'], json=body).status_code, 409)
        self.assertEqual(self.admin.get('/api/lessons').status_code, 403)

    def test_password_change_revokes_all_logins(self):
        second = TestClient(self.app)
        second.post('/api/auth/login', json={'username': 'student', 'password': 'Test-password-1234'})
        result = self.student.post('/api/auth/password', json={'current_password': 'Test-password-1234', 'password': 'New-password-1234'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(second.get('/api/me').status_code, 401)
        self.assertEqual(self.student.get('/api/me').status_code, 401)
        second.close()

    def test_same_origin_and_static_app(self):
        self.assertEqual(self.student.post('/api/trainings', json={'task_id': 'part-bracket'}, headers={'Origin': 'https://evil.example'}).status_code, 403)
        response = self.student.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('電腦圖學', response.text)
        self.assertIn("script-src 'self'", response.headers['content-security-policy'])
        self.assertEqual(self.student.get('/static/app.js').status_code, 200)
        self.assertEqual(self.student.get('/static/style.css').status_code, 200)
        self.assertEqual(self.store.all('SELECT * FROM sessions'), [])


if __name__ == '__main__':
    unittest.main()
