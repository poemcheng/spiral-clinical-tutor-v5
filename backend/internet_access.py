"""Internet capability selection and administrator-only deployment status."""
import ipaddress,json,socket,time
from .config import RUNTIME
from fastapi import Depends,Request

def external(request):
    host=(request.url.hostname or '').lower()
    if host in ('localhost',socket.gethostname().lower(),'testserver'):return False
    try:return not (ipaddress.ip_address(host).is_private or ipaddress.ip_address(host).is_loopback)
    except ValueError:return True

def read_state(name):
    try:return json.loads((RUNTIME/name).read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}

def install(app,administrator):
    @app.get('/api/admin/deployment')
    def deployment(user=Depends(administrator)):
        connection=read_state('internet-connection.json');backup=read_state('backup-status.json')
        return {'internet':{k:connection.get(k) for k in ('url','temporary','updated','ready')},'backup':backup,
                'host_must_stay_online':True,'voice_transport':'authenticated-http-audio'}

    @app.post('/api/admin/deployment/backup')
    def queue_backup(user=Depends(administrator)):
        (RUNTIME/'backup-request').write_text(str(time.time()),encoding='ascii')
        return {'queued':True,'message':'已排入加密備份；完成後請重新整理狀態。'}
