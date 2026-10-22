"""Start a loopback-only LiveKit server; credentials stay in ignored runtime/."""
import json
from pathlib import Path
import secrets
import socket
import subprocess
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1]
def free_port():
 for port in range(7880,7900):
  with socket.socket() as probe:
   try:probe.bind(('127.0.0.1',port));return port
   except OSError:continue
 raise RuntimeError('沒有可用的本機 LiveKit 信令連接埠。')

def main():
 runtime=ROOT/'runtime';runtime.mkdir(exist_ok=True)
 private=runtime/'livekit-private.json'
 if private.exists():cfg=json.loads(private.read_text())
 else:
  cfg={'LIVEKIT_URL':f'ws://127.0.0.1:{free_port()}','LIVEKIT_API_KEY':'clinical-'+secrets.token_hex(8),'LIVEKIT_API_SECRET':secrets.token_urlsafe(36)}
  private.write_text(json.dumps(cfg),encoding='utf-8')
 port=urlparse(cfg['LIVEKIT_URL']).port
 try:
  with socket.create_connection(('127.0.0.1',port),timeout=.5):print(f'LiveKit already listening on loopback:{port}');return
 except OSError:pass
 config=runtime/'livekit.yaml'
 config.write_text(f'port: {port}\nbind_addresses: [127.0.0.1]\nrtc:\n  tcp_port: 0\n  port_range_start: 7882\n  port_range_end: 7982\n  use_external_ip: false\n  enable_loopback_candidate: true\n  node_ip: 127.0.0.1\n  ips:\n    includes: [127.0.0.0/8]\nkeys:\n  '+cfg['LIVEKIT_API_KEY']+': '+cfg['LIVEKIT_API_SECRET']+'\n',encoding='utf-8')
 with (runtime/'livekit.log').open('ab') as log:
  p=subprocess.Popen([str(ROOT/'tools/livekit/livekit-server.exe'),'--config',str(config)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 print('LiveKit started, PID '+str(p.pid)+'; private credentials remain in runtime/.')
if __name__=='__main__':main()
