"""Administrator-owned account limits and private SMTP configuration."""
import json,os,re,secrets,smtplib,ssl,time
from pathlib import Path
from .config import RUNTIME
from .store import encode,password_hash,verify_password
from fastapi import Depends,HTTPException
from pydantic import BaseModel,Field

def get(store,key,default):
    row=store.one('SELECT value FROM app_settings WHERE key=?',(key,))
    return json.loads(row['value']) if row else default

def put(store,key,value):
    with store.tx() as c:
        c.execute('DELETE FROM app_settings WHERE key=?',(key,))
        c.execute('INSERT INTO app_settings VALUES (?,?)',(key,encode(value)))

def password_policy(store):return get(store,'password_policy',{'minimum':4,'maximum':6})

def validate_password(store,password):
    policy=password_policy(store)
    if not policy['minimum']<=len(password)<=policy['maximum']:
        raise HTTPException(400,f"密碼長度須為{policy['minimum']}至{policy['maximum']}碼。")

def cipher():
    from cryptography.fernet import Fernet
    path=RUNTIME/'secrets/smtp.key';path.parent.mkdir(exist_ok=True)
    if not path.exists():
        try:
            with path.open('xb') as f:f.write(Fernet.generate_key())
        except FileExistsError:pass
    return Fernet(path.read_bytes())

def smtp_config(store,private=False):
    data=get(store,'smtp',{'host':'','port':587,'security':'starttls','username':'','sender':'','password_encrypted':''})
    if private:
        data['password']=cipher().decrypt(data['password_encrypted'].encode()).decode() if data.get('password_encrypted') else os.getenv('SMTP_PASSWORD','')
    else:data['password_configured']=bool(data.pop('password_encrypted','') or os.getenv('SMTP_PASSWORD'))
    data['ready']=bool(data.get('host') and data.get('sender') and (data.get('password') if private else data.get('password_configured')))
    return data

class PasswordPolicy(BaseModel):
    minimum:int=Field(ge=4,le=64)
    maximum:int=Field(ge=4,le=128)

class OwnPassword(BaseModel):
    current_password:str=Field(min_length=1,max_length=256)
    new_password:str=Field(min_length=4,max_length=128)

class SMTPBody(BaseModel):
    host:str=Field(max_length=253)
    port:int=Field(ge=1,le=65535)
    security:str='starttls'
    username:str=Field(max_length=254)
    sender:str=Field(max_length=254)
    password:str|None=Field(default=None,max_length=1024)

def install(app,store,current_user,administrator):
    @app.get('/api/admin/settings')
    def settings(user=Depends(administrator)):return {'password_policy':password_policy(store),'smtp':smtp_config(store)}
    @app.patch('/api/admin/settings/password-policy')
    def update_policy(body:PasswordPolicy,user=Depends(administrator)):
        if body.minimum>body.maximum:raise HTTPException(400,'最小長度不可大於最大長度。')
        put(store,'password_policy',body.model_dump())
        with store.tx() as c:store.event(c,user['id'],None,'password_policy_updated',body.model_dump())
        return body.model_dump()
    @app.post('/api/auth/password')
    def own_password(body:OwnPassword,user=Depends(current_user)):
        validate_password(store,body.new_password)
        old=store.one('SELECT password_hash FROM users WHERE id=?',(user['id'],))
        if not verify_password(body.current_password,old['password_hash']):raise HTTPException(400,'目前密碼不正確。')
        with store.tx() as c:
            c.execute('UPDATE users SET password_hash=? WHERE id=?',(password_hash(body.new_password),user['id']))
            c.execute('UPDATE logins SET expires=0 WHERE user_id=?',(user['id'],))
            store.event(c,user['id'],None,'own_password_changed',{})
        return {'saved':True,'login_required':True}
    @app.put('/api/admin/settings/smtp')
    def configure_smtp(body:SMTPBody,user=Depends(administrator)):
        if body.security not in ('starttls','ssl'):raise HTTPException(400,'寄信連線須使用STARTTLS或SSL。')
        if not re.fullmatch(r'[a-zA-Z0-9.-]+',body.host) or not valid_email(body.sender):raise HTTPException(400,'請填寫有效SMTP主機與寄件地址。')
        old=get(store,'smtp',{});data=body.model_dump(exclude={'password'})
        data['password_encrypted']=cipher().encrypt(body.password.encode()).decode() if body.password else old.get('password_encrypted','')
        put(store,'smtp',data)
        return smtp_config(store)

def valid_email(address):return bool(re.fullmatch(r'[^\s@<>\r\n]+@[^\s@<>\r\n]+\.[^\s@<>\r\n]+',address)) and len(address)<=254

def send_pdf(store,address,pdf,filename,subject):
    if not valid_email(address):raise HTTPException(400,'請輸入有效電子信箱。')
    config=smtp_config(store,True)
    if not config['ready']:raise HTTPException(503,'寄件服務尚未設定；請管理員先完成SMTP設定。PDF仍可直接預覽及下載。')
    from email.message import EmailMessage
    msg=EmailMessage();msg['Subject']=subject;msg['From']=config['sender'];msg['To']=address
    msg.set_content('您的訓練報告如附件。報告區分自評、客觀練習與教師核定，請依報告中的待評項目及教師建議持續學習。')
    msg.add_attachment(pdf,maintype='application',subtype='pdf',filename=filename)
    try:
        context=ssl.create_default_context()
        client=smtplib.SMTP_SSL(config['host'],config['port'],timeout=25,context=context) if config['security']=='ssl' else smtplib.SMTP(config['host'],config['port'],timeout=25)
        with client:
            if config['security']=='starttls':client.starttls(context=context)
            client.login(config['username'],config['password']);refused=client.send_message(msg)
            if refused:raise smtplib.SMTPRecipientsRefused(refused)
    except (OSError,smtplib.SMTPException):raise HTTPException(502,'SMTP未接受寄件，請核對寄件設定或收件地址後再試。')
    return {'accepted_by_smtp':True,'recipient':address,'note':'寄件伺服器已接受；最終投遞仍依收件系統。'}
