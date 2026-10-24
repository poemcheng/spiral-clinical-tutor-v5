"""Current-user tunnel supervisor and encrypted, independently verifiable backups."""
import datetime,hashlib,json,os,re,shutil,sqlite3,subprocess,sys,threading,time,urllib.request,urllib.error,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.encrypted_learning_backup import create_snapshot,atomic_json
from backend.config import RUNTIME,VERSION
PRIVATE_REPO='poemcheng/spiral-clinical-tutor-private-backups'
PUBLIC_REPO='poemcheng/spiral-clinical-tutor-v5'

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def settings():
    try:return json.loads((RUNTIME/'internet-settings.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}

def run_git(folder,args,key):
    # Pinned official GitHub SSH host keys; no credential prompts or token logging.
    known=RUNTIME/'internet-tools/github-known-hosts'
    if not known.is_file() or not Path(key).is_file():raise RuntimeError('GitHub repository deploy key is not configured')
    env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_SSH_COMMAND':f'ssh -i "{Path(key).as_posix()}" -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="{known.as_posix()}"'}
    result=subprocess.run(['git','-C',str(folder),*args],env=env,capture_output=True,text=True,timeout=90,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise RuntimeError('GitHub sync failed: '+result.stderr[-600:])
    return result.stdout.strip()

def ensure_repo(folder,repo,key):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    remote=f'ssh://git@ssh.github.com:443/{repo}.git'
    if not (folder/'.git').is_dir():
        subprocess.run(['git','init','-b','main',str(folder)],check=True,capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        run_git(folder,['remote','add','origin',remote],key)
        run_git(folder,['config','user.name','Clinical Tutor Backup'],key)
        run_git(folder,['config','user.email','clinical-tutor@localhost'],key)
    if run_git(folder,['remote','get-url','origin'],key)!=remote:raise RuntimeError('Unexpected backup remote')
    return folder

def private_visibility_check():
    # A publicly readable repository must never receive learning-data backups.
    req=urllib.request.Request('https://api.github.com/repos/'+PRIVATE_REPO,headers={'User-Agent':'ClinicalTutorBackup'})
    try:
        with urllib.request.urlopen(req,timeout=15) as r:json.load(r)
    except urllib.error.HTTPError as e:
        if e.code==404:return
        raise RuntimeError('Could not verify GitHub repository privacy') from e
    raise RuntimeError('Backup repository is publicly readable; upload refused')

def push_backup(snapshot,cfg):
    private_visibility_check()
    key=RUNTIME/'secrets/github-private-backup'
    repo=ensure_repo(RUNTIME/'github-private-mirror',PRIVATE_REPO,key)
    if run_git(repo,['ls-remote','origin'],key):
        run_git(repo,['fetch','origin','main'],key)
        # Only this service writes the backup branch. Reject unexpected divergence.
        try:run_git(repo,['rev-parse','--verify','HEAD'],key)
        except RuntimeError:run_git(repo,['checkout','-B','main','origin/main'],key)
        # Fast-forward accepts a new remote head or a pending local push, but
        # never rewrites a branch that actually diverged.
        run_git(repo,['merge','--ff-only','origin/main'],key)
    target=repo/'current';target.mkdir(exist_ok=True)
    for p in target.iterdir():
        if p.is_file():p.unlink()
    for p in Path(snapshot).iterdir():
        if not re.fullmatch(r'(index|part-\d{5})\.enc',p.name):raise RuntimeError('Non-encrypted file rejected')
        shutil.copyfile(p,target/p.name)
    (repo/'README.md').write_text('# Private encrypted learning backups\n\nOnly authenticated encrypted chunks are stored here. The recovery key stays on the teaching host.\n',encoding='utf-8')
    run_git(repo,['add','--','current','README.md'],key)
    if run_git(repo,['diff','--cached','--name-only'],key):run_git(repo,['commit','-m','Encrypted learning snapshot '+Path(snapshot).name],key)
    run_git(repo,['push','origin','main'],key)
    return run_git(repo,['rev-parse','HEAD'],key)

def publish_url(connection):
    key=RUNTIME/'secrets/github-public-portal'
    repo=ensure_repo(RUNTIME/'github-public-portal',PUBLIC_REPO,key)
    run_git(repo,['fetch','--depth','1','origin','main'],key)
    if (repo/'web_portal/internet.json').is_file():
        # This mirror contains only an intentionally replaceable portal checkout.
        run_git(repo,['restore','--staged','--worktree','--','web_portal/internet.json'],key)
    run_git(repo,['checkout','-B','main','origin/main'],key)
    safe={k:connection[k] for k in ('url','temporary','updated','ready')}
    atomic_json(repo/'web_portal/internet.json',safe)
    run_git(repo,['add','--','web_portal/internet.json'],key)
    if run_git(repo,['diff','--cached','--name-only'],key):
        run_git(repo,['commit','-m','Update current Internet test login endpoint'],key)
        run_git(repo,['push','origin','main'],key)

def tunnel_loop():
    exe=RUNTIME/'internet-tools/cloudflared.exe'
    while True:
        logfile=RUNTIME/'internet-tunnel-supervised.log'
        with logfile.open('a',encoding='utf-8',buffering=1) as log:
            proc=subprocess.Popen([str(exe),'tunnel','--no-autoupdate','--protocol','http2','--url','http://127.0.0.1:8705'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            connection={}
            for line in proc.stdout:
                log.write(line)
                match=re.search(r'https://[a-z0-9-]+\.trycloudflare\.com',line)
                if match and match.group(0)!=connection.get('url'):
                    connection={'url':match.group(0),'temporary':True,'ready':False,'updated':now()}
                    atomic_json(RUNTIME/'internet-connection.json',connection)
                    atomic_json(ROOT/'web_portal/internet.json',connection)
                    def publish(data):
                        for attempt in range(5):
                            try:
                                with urllib.request.urlopen(data['url']+'/health',timeout=15) as r:json.load(r)
                                data.update(ready=True,updated=now());atomic_json(RUNTIME/'internet-connection.json',data);atomic_json(ROOT/'web_portal/internet.json',data)
                                publish_url(data);return
                            except Exception as e:
                                print('Portal update pending:',str(e),flush=True);time.sleep(20)
                    threading.Thread(target=publish,args=(dict(connection),),daemon=True).start()
            connection.update(ready=False,updated=now());atomic_json(RUNTIME/'internet-connection.json',connection)
        time.sleep(10)

def backup_loop(stop=None,interval=15):
    cfg=settings();base=Path(cfg.get('backup_directory',str(RUNTIME/'encrypted-learning-backups'))).resolve();base.mkdir(parents=True,exist_ok=True)
    state={'local_interval_seconds':15,'github_interval_seconds':300,'github_repository':PRIVATE_REPO,'scope':'帳號、學習歷程、對話、教師回饋、自訂教案與個人分析／影片；共用EPA影格與原始教材由既有主機保存'}
    stamp=None;latest=None;last_cloud=0
    state_lock=threading.RLock();cloud_busy=threading.Event()
    def sync_remote(snapshot):
        nonlocal last_cloud
        try:
            commit=push_backup(snapshot,cfg)
            with state_lock:
                state['github']={'snapshot':snapshot.name,'commit':commit,'synced':now(),'verified_push':True};state.pop('github_error',None)
                last_cloud=time.time();atomic_json(RUNTIME/'backup-status.json',state)
        except Exception as e:
            with state_lock:
                state['github_error']=str(e);last_cloud=time.time()-240;atomic_json(RUNTIME/'backup-status.json',state)
        finally:cloud_busy.clear()
    while not (stop and stop.is_set()):
        try:
            db=RUNTIME/'clinical_tutor.sqlite3';wal=Path(str(db)+'-wal')
            current=tuple((p.stat().st_mtime_ns,p.stat().st_size) if p.exists() else None for p in (db,wal))
            request=RUNTIME/'backup-request';forced=request.exists()
            if current!=stamp or forced:
                dest=base/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:6])
                meta=create_snapshot(RUNTIME,dest,VERSION);latest=dest;stamp=current
                with state_lock:state['local']=meta;state.pop('local_error',None)
                request.unlink(missing_ok=True)
                print('Verified encrypted snapshot:',dest.name,flush=True)
            if latest and not cloud_busy.is_set() and (forced or time.time()-last_cloud>=300):
                cloud_busy.set();last_cloud=time.time()
                threading.Thread(target=sync_remote,args=(latest,),daemon=True).start()
            with state_lock:state['checked']=now();atomic_json(RUNTIME/'backup-status.json',state)
        except Exception as e:
            with state_lock:state['local_error']=str(e);state['checked']=now();atomic_json(RUNTIME/'backup-status.json',state)
        if stop:stop.wait(interval)
        else:time.sleep(interval)

if __name__=='__main__':
    RUNTIME.mkdir(exist_ok=True)
    log=(RUNTIME/'internet-service.log').open('a',encoding='utf-8',buffering=1);sys.stdout=sys.stderr=log
    print('Internet supervisor starting',now(),flush=True)
    atomic_json(RUNTIME/'internet-service.json',{'pid':os.getpid(),'started':now()})
    threading.Thread(target=tunnel_loop,daemon=True).start()
    backup_loop()
