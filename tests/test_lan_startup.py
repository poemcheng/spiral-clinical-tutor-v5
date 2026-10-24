"""An already-running local voice server must be upgraded when LAN is requested."""
import contextlib,io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tools import start_livekit

class LanVoiceStartupTests(unittest.TestCase):
    def run_existing(self,address):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);runtime=root/'runtime';runtime.mkdir()
            config={'LIVEKIT_URL':'ws://127.0.0.1:7880','LIVEKIT_API_KEY':'fixture-key','LIVEKIT_API_SECRET':'fixture-secret'}
            (runtime/'livekit-private.json').write_text(json.dumps(config))
            (runtime/'livekit.yaml').write_text(f'bind_addresses: [{"0.0.0.0" if address!="127.0.0.1" else address}]\n  node_ip: {address}\n')
            with patch.object(start_livekit,'ROOT',root),patch.object(sys,'argv',['start_livekit.py','--lan-address','192.168.68.108']),patch.object(start_livekit.socket,'create_connection',return_value=contextlib.nullcontext()),patch.object(start_livekit,'stop_server') as stop,patch.object(start_livekit,'start_background',return_value=123) as start,contextlib.redirect_stdout(io.StringIO()):
                start_livekit.main()
            self.assertEqual(json.loads((runtime/'livekit-private.json').read_text()),config)
            return stop.call_count,start.call_count,(runtime/'livekit.yaml').read_text()

    def test_lan_request_upgrades_existing_loopback_server_and_preserves_credentials(self):
        stopped,started,config=self.run_existing('127.0.0.1')
        self.assertEqual((stopped,started),(1,1));self.assertIn('bind_addresses: [0.0.0.0]',config);self.assertIn('node_ip: 192.168.68.108',config)

    def test_matching_lan_server_is_reused(self):
        stopped,started,_=self.run_existing('192.168.68.108')
        self.assertEqual((stopped,started),(0,0))
