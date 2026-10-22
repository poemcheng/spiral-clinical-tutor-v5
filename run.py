import os
import json
import threading
import time
import urllib.request
import uuid
import webbrowser
import uvicorn


def probe_server(url):
    try:
        with urllib.request.urlopen(url+'/health',timeout=1) as response:
            result=json.load(response)
        return result if result.get('product')=='clinical-tutor' else None
    except Exception:return None


def login_url(url,health):
    # A different URL per invocation forces navigation, including an already-open browser.
    entry=health.get('login_entry')
    path='/login' if entry=='/login' else '/'
    return url+path+'?launch='+uuid.uuid4().hex


def open_login_when_ready(url,timeout=30):
    from backend.config import RUNTIME
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        health=probe_server(url)
        if health:
            target=login_url(url,health)
            print('Opening sign-in page: '+target,flush=True)
            # No tokens or passwords; record the exact launch entry for troubleshooting.
            with (RUNTIME/'launcher.log').open('a',encoding='utf-8') as log:
                log.write(json.dumps({'time':time.time(),'url':target,'server_version':health.get('version')})+'\n')
            opened=webbrowser.open(target,new=2,autoraise=True)
            if not opened:print('Open this sign-in URL manually: '+target,flush=True)
            return target
        time.sleep(.2)
    print('The platform did not become ready; inspect the server error above.',flush=True)
    return None


def main():
    from backend.config import ROOT
    host=os.getenv('PLATFORM_HOST','127.0.0.1');port=int(os.getenv('PLATFORM_PORT','8705'))
    url=f'http://127.0.0.1:{port}'
    if probe_server(url):
        print('Platform is already running: '+url)
        if os.getenv('OPEN_PLATFORM_BROWSER')=='1':open_login_when_ready(url)
    else:
        if not os.getenv('LIVEKIT_URL') and os.getenv('DISABLE_LOCAL_VOICE','0')!='1' and (ROOT/'tools/livekit/livekit-server.exe').exists():
            try:
                from tools.start_livekit import main as start_local_voice
                start_local_voice()
            except Exception as e:print('Local voice is unavailable: '+str(e))
        from backend.store import Store
        bootstrap=Store()
        bootstrap.bootstrap_admin()
        bootstrap.conn.close()
        if os.getenv('OPEN_PLATFORM_BROWSER')=='1':
            threading.Thread(target=open_login_when_ready,args=(url,),daemon=True).start()
        uvicorn.run('backend.server:app',host=host,port=port)


if __name__=='__main__':main()
