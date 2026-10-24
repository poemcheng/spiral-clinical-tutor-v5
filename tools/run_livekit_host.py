"""Independent hidden voice host. Never prints private LiveKit configuration."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    with (ROOT/'runtime/livekit.log').open('ab') as log:
        child=subprocess.Popen([str(ROOT/'tools/livekit/livekit-server.exe'),'--config',str(ROOT/'runtime/livekit.yaml')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        raise SystemExit(child.wait())
