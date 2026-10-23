import hashlib,json,os,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
from backend import knowledge_retrieval,neural_speech,xapi
from backend.postgres_store import translate
from tools.run_lan import certificates

class ExtendedStackTests(unittest.TestCase):
    def test_vague_worsening_is_not_an_observed_weight_or_muscle_decline(self):
        from backend.encounters import unsupported_change_claims
        case={'patient':'體重44.3kg，ALMI5.20；主訴努力三個月為什麼更差。'}
        self.assertEqual(unsupported_change_claims('她的體重與肌肉量仍有下降。',case),['肌肉量','體重'])
        self.assertEqual(unsupported_change_claims('尚未提供體重下降的前後數據，需要核對。',case),[])
        self.assertEqual(unsupported_change_claims('體重下降。',{'patient':'病歷記載體重下降。'}),[])
    def test_retrieval_is_local_and_cannot_cross_the_selected_case(self):
        a={'id':'only-a','patient':'病人近期坐站困難。判讀重點不可透露','patient_script':'我擔心跌倒。','source_file':'case-a'}
        evidence,version=knowledge_retrieval.retrieve(a,'跌倒')
        self.assertTrue(evidence);self.assertTrue(all(x['chunk_id'].startswith('only-a-') for x in evidence))
        self.assertNotIn('不可透露',''.join(x['excerpt'] for x in evidence))
        self.assertIn('local',version)

    def test_postgres_translation_retains_parameters_and_safe_json_comparisons(self):
        sql,returns=translate("SELECT json_extract(data,'$.safety_pass') passed FROM events WHERE json_extract(data,'$.review_id')=?")
        self.assertIn("data::jsonb ->> 'review_id'",sql);self.assertIn('CAST(%s AS text)',sql);self.assertFalse(returns)
        sql,returns=translate('INSERT INTO users(username,role) VALUES (?,?)')
        self.assertTrue(returns);self.assertTrue(sql.endswith('RETURNING id'))
        sql,_=translate('INSERT OR IGNORE INTO progress VALUES (?,?,?,?,?)');self.assertIn('ON CONFLICT DO NOTHING',sql)

    def test_piper_requires_a_registered_gender_language_and_model_digest(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'voice.onnx';path.write_bytes(b'model fixture')
            manifest=Path(str(path)+'.identity.json')
            with patch.dict(os.environ,{'PIPER_MALE_MODEL':str(path)}):
                manifest.write_text(json.dumps({'gender':'female','language':'zh-TW','sha256':hashlib.sha256(path.read_bytes()).hexdigest()}))
                with self.assertRaises(RuntimeError):neural_speech.identity('male')
                manifest.write_text(json.dumps({'gender':'male','language':'zh-TW','sha256':hashlib.sha256(path.read_bytes()).hexdigest()}))
                self.assertEqual(neural_speech.identity('male')[0],path)
                path.write_bytes(b'changed model')
                with self.assertRaises(RuntimeError):neural_speech.identity('male')

    def test_xapi_has_stable_ids_pseudonymous_actor_and_no_free_text(self):
        event={'id':42,'kind':'teacher_review','data':json.dumps({'score':80,'note':'private note'}),'created':1700000000}
        a=xapi.statement(event,{'id':3,'username':'private-login'},{'id':2,'profession':'RN','level':3})
        self.assertEqual(a,xapi.statement(event,{'id':3},{'id':2,'profession':'RN','level':3}));uuid.UUID(a['id'])
        self.assertEqual(a['result']['score']['raw'],80);self.assertNotIn('private',json.dumps(a))

    def test_tls_has_both_lan_ips_and_reuses_ca_without_modifying_trust(self):
        from cryptography import x509
        with tempfile.TemporaryDirectory() as folder:
            cert,key=certificates(['192.168.68.108','192.168.100.101'],Path(folder))
            ca=(Path(folder)/'clinical-tutor-ca.cer').read_bytes()
            extensions=x509.load_pem_x509_certificate(cert.read_bytes()).extensions
            values=extensions.get_extension_for_class(x509.SubjectAlternativeName).value
            self.assertEqual(len(values.get_values_for_type(x509.IPAddress)),3)
            certificates(['192.168.68.108'],Path(folder));self.assertEqual(ca,(Path(folder)/'clinical-tutor-ca.cer').read_bytes())

    def test_every_character_model_records_the_actual_reference_card(self):
        root=Path(__file__).resolve().parents[1]
        catalog=json.loads((root/'data/characters/catalog.json').read_text(encoding='utf-8'))
        for a in catalog['actors']:
            self.assertEqual(a['reference_card_sha256'],a['card_sha256'])
            self.assertTrue(a['appearance']['hair']);self.assertTrue(a['appearance']['notes'])
            self.assertEqual(a['appearance']['glasses'],a['glasses'])

if __name__=='__main__':unittest.main()
