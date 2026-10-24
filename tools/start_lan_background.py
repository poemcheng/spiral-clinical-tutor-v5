"""Hidden current-user sign-in launcher; the host itself is launched independently."""
from pathlib import Path
import subprocess,datetime
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    target=ROOT/'runtime/lan-startup.log';target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('a',encoding='utf-8') as log:
        log.write('\nSTART '+datetime.datetime.now(datetime.timezone.utc).isoformat()+'\n');log.flush()
        result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'tools/start_lan.ps1')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode==0 and (ROOT/'runtime/internet-settings.json').exists():
            import json
            if json.loads((ROOT/'runtime/internet-settings.json').read_text()).get('enabled'):
                subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'tools/start_internet.ps1')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    raise SystemExit(result.returncode)
