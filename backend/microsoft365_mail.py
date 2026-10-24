"""Microsoft 365 Graph application mail: credentials stay on the local host."""
import base64,re
from urllib.parse import quote
import httpx
from fastapi import HTTPException
from pydantic import BaseModel,Field
from .workspace_settings import get,put,cipher,valid_email

GUID=r'[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}'
class Microsoft365Body(BaseModel):
    tenant_id:str=Field(max_length=64)
    client_id:str=Field(max_length=64)
    sender:str=Field(max_length=254)
    client_secret:str|None=Field(default=None,max_length=4096)

def config(store,private=False):
    data=get(store,'microsoft365_mail',{'tenant_id':'','client_id':'','sender':'','secret_encrypted':''})
    encrypted=data.pop('secret_encrypted','')
    if private:data['client_secret']=cipher().decrypt(encrypted.encode()).decode() if encrypted else ''
    data['secret_configured']=bool(encrypted)
    data['ready']=bool(data.get('tenant_id') and data.get('client_id') and data.get('sender') and encrypted)
    return data

def configure(store,body):
    if not re.fullmatch(GUID,body.tenant_id) or not re.fullmatch(GUID,body.client_id) or not valid_email(body.sender):
        raise HTTPException(400,'請填寫有效Tenant ID、Client ID與寄件信箱。')
    old=get(store,'microsoft365_mail',{});data=body.model_dump(exclude={'client_secret'})
    data['secret_encrypted']=cipher().encrypt(body.client_secret.encode()).decode() if body.client_secret else old.get('secret_encrypted','')
    put(store,'microsoft365_mail',data);put(store,'mail_provider','microsoft365')
    return config(store)

def send_pdf(store,address,pdf,filename,subject):
    c=config(store,True)
    if not c['ready']:raise HTTPException(503,'Microsoft 365寄件尚待設定：請由院校IT提供寄件信箱、Tenant ID、Client ID及應用程式授權。PDF仍可預覽與下載。')
    if len(pdf)>3*1024*1024:raise HTTPException(413,'此報告超過直接郵件附件大小，請先下載PDF。')
    try:
        token=httpx.post(f"https://login.microsoftonline.com/{c['tenant_id']}/oauth2/v2.0/token",data={
            'client_id':c['client_id'],'client_secret':c['client_secret'],
            'scope':'https://graph.microsoft.com/.default','grant_type':'client_credentials'},timeout=25)
        if token.status_code!=200:raise HTTPException(502,'Microsoft 365授權未成功，請院校IT核對應用程式設定。')
        access=token.json().get('access_token')
        if not access:raise HTTPException(502,'Microsoft 365未提供有效寄件授權。')
        result=httpx.post(f"https://graph.microsoft.com/v1.0/users/{quote(c['sender'],safe='')}/sendMail",headers={'Authorization':'Bearer '+access},json={
            'message':{'subject':subject,'body':{'contentType':'Text','content':'您的完整訓練報告如附件，請依教師回饋持續學習。'},
                       'toRecipients':[{'emailAddress':{'address':address}}],
                       'attachments':[{'@odata.type':'#microsoft.graph.fileAttachment','name':filename,'contentType':'application/pdf','contentBytes':base64.b64encode(pdf).decode()}]},
            'saveToSentItems':True},timeout=30)
        if result.status_code!=202:raise HTTPException(502,'Microsoft 365未接受寄件，請院校IT核對Mail.Send權限及寄件信箱範圍。')
    except (httpx.HTTPError,ValueError):raise HTTPException(502,'Microsoft 365寄件連線失敗，請稍後重試。')
    return {'accepted_by_service':True,'provider':'microsoft365','recipient':address,'note':'Microsoft 365已接受寄件；最終投遞仍依收件系統。'}
