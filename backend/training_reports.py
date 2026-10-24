"""Evidence-based Chinese PDF training reports and explicit SMTP delivery."""
import datetime,hashlib,io,json,os,threading,time,functools
from pathlib import Path
from xml.sax.saxutils import escape
from fastapi import Depends,HTTPException,Response
from pydantic import BaseModel,Field
from .config import ROOT,RUNTIME,VERSION
from .competencies import profile
FONT_LOCK=threading.Lock()
RENDER_LOCK=threading.Lock()

@functools.lru_cache(maxsize=16)
def cached_pdf(serialized):return build_pdf(json.loads(serialized))

def pdf_bytes(evidence):return cached_pdf(json.dumps(evidence,ensure_ascii=False,sort_keys=True))

def page_image(raw,number):
    import pypdfium2 as pdfium
    with RENDER_LOCK:
        document=pdfium.PdfDocument(raw)
        try:
            if not 1<=number<=len(document):raise HTTPException(404,'報告頁碼超出範圍。')
            page=document[number-1]
            try:
                bitmap=page.render(scale=1.5)
                try:
                    image=bitmap.to_pil();out=io.BytesIO();image.convert('RGB').save(out,format='JPEG',quality=88);return out.getvalue()
                finally:bitmap.close()
            finally:page.close()
        finally:document.close()

def font_name():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    with FONT_LOCK:
        if 'TutorCJK' in pdfmetrics.getRegisteredFontNames():return 'TutorCJK'
        candidates=[Path(os.getenv('REPORT_CJK_FONT','')),ROOT/'data/report-fonts/NotoSansTC-Regular.ttf',Path('C:/Windows/Fonts/msjh.ttc')]
        for p in candidates:
            if p.is_file():
                try:pdfmetrics.registerFont(TTFont('TutorCJK',str(p),subfontIndex=0));return 'TutorCJK'
                except Exception:continue
        if 'MSung-Light' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(UnicodeCIDFont('MSung-Light'))
        return 'MSung-Light'

def report_data(store,row):
    data=row['payload'];owner=store.one('SELECT username,display_name FROM users WHERE id=?',(row['user_id'],))
    attempt=store.one('SELECT scores,snapshot,completed FROM attempts WHERE id=? AND user_id=?',(data.get('assessment_attempt_id'),row['user_id']))
    scores=json.loads(attempt['scores']) if attempt and attempt['scores'] else {}
    reviews=store.all('SELECT r.*,u.display_name teacher FROM reviews r JOIN users u ON u.id=r.teacher_id WHERE session_id=? ORDER BY r.id',(row['id'],))
    messages=store.all('SELECT role,content,source,metadata,created FROM messages WHERE session_id=? ORDER BY id',(row['id'],))
    return {'id':row['id'],'owner':owner,'profession':row['profession'],'topic':row['topic'],'self_level':row['level'],'learning_level':data.get('adaptive_plan',{}).get('learning_level'),'created':row['created'],'updated':row['updated'],'status':row['status'],'case':data.get('case_snapshot',{}),'case_hash':data.get('case_hash',''),'scores':scores,'result':data.get('result',{}),'reviews':reviews,'messages':messages,'data':data}

def build_pdf(evidence):
    from reportlab.lib import colors
    from reportlab.lib.styles import StyleSheet1,ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,KeepTogether
    from reportlab.graphics.shapes import Drawing,String,Line,Polygon,Circle
    import math
    font=font_name();stream=io.BytesIO();styles=StyleSheet1()
    for name,size,leading,color in [('body',10,17,'#243B46'),('small',8,13,'#526975'),('title',23,33,'#123F4B'),('section',15,24,'#087B7C'),('sub',11,19,'#123F4B')]:styles.add(ParagraphStyle(name,fontName=font,fontSize=size,leading=leading,textColor=colors.HexColor(color),wordWrap='CJK',spaceAfter=8))
    def para(text,style='body'):return Paragraph(escape(str(text or '未提供')).replace('\n','<br/>'),styles[style])
    story=[];e=evidence;scores=e['scores'];result=e['result'];case=e['case'];reviews=e['reviews'];data=e['data'];p=profile(e['profession'])
    def section(title):story.extend([Spacer(1,10),para(title,'section')])
    def table(rows,widths=None):
        obj=Table([[para(v,'small' if i==0 else 'body') for v in r] for i,r in enumerate(rows)],colWidths=widths,repeatRows=1,hAlign='LEFT',splitInRow=1)
        obj.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E5F0F1')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#8BAFB5')),('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#DAE5E8')),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]));story.append(obj)
    def value(v):return '待評／無資料' if v is None else str(v)+' / 100'
    story.extend([para('完整訓練成果報告','title'),para('CLINICAL LEARNING  |  迴旋梯智鏈','small'),para(f"報告編號 CT-{e['id']:06d}   平台 v{VERSION}   {'已完成訓練' if e['status']=='completed' else '訓練尚未完成'}",'small'),para('訓練開始 '+datetime.datetime.fromtimestamp(e['created']).strftime('%Y-%m-%d %H:%M')+'   最後更新 '+datetime.datetime.fromtimestamp(e['updated']).strftime('%Y-%m-%d %H:%M'),'small')])
    table([['學員／職種','訓練情境／教案'],[e['owner']['display_name']+'（'+e['owner']['username']+'）\n'+p['label'],e['topic']+'\n'+case.get('title','尚未選定教案')],['自評分流等級','累積學習等級'],['Level '+str(e['self_level']),'Level '+str(e['learning_level'] or '未提供')]], [250,261])
    section('01  自評與訓練成績分開呈現')
    summary=scores.get('summary',{});self_mean=summary.get('self_mean');pre=summary.get('objective_auto_percent')
    if self_mean is None and scores.get('self_dimensions'):self_mean=round(sum(scores['self_dimensions'].values())/len(scores['self_dimensions']),1)
    teacher=reviews[-1] if reviews else None
    table([['評量項目','結果','說明'],['訓練前自評',value(self_mean),'學員自陳，不等同客觀成績'],['客觀前測',value(pre),'簡答與待評項目不補零分'],['關鍵決策',value(result.get('decision_score')),'依本輪教案決策規準'],['訓練後測',value(result.get('quiz_score')),'依本輪測驗題'],['客觀訓練綜合',value(result.get('objective_score')),result.get('formula','訓練尚未完成')],['教師整體覆核',value(teacher['score'] if teacher else None),'正式教學覆核另存，不與自評混算']], [105,115,291])
    story.append(para('前測與後測題本不一定相同，分數並列供反思，不直接視為等值測驗進步幅度。平台學習等級及教師教學回饋不等同院方EPA信賴授權。','small'))
    section('02  職種核心能力與可評證據')
    indicators=p['indicators'];comp=scores.get('competency_scores',{});dims=scores.get('self_dimensions',{});rows=[['核心能力','訓練前自評','訓練後證據']]
    decisions=data.get('decisions',{}).values();quiz=data.get('quiz_result',[])
    for ind in indicators:
        v=comp.get(ind['id']);v=v if v is not None else dims.get(ind['dimension']);dim=ind['dimension'];records=[r for r in decisions if r.get('dimension')==dim];qs=[r for r in quiz if r.get('dimension')==dim]
        bits=[]
        if records:bits.append('決策 '+str(round(sum(r.get('score',0) for r in records)/sum(r.get('max_score',1) for r in records)*100,1))+'分')
        if qs:bits.append('後測 '+str(round(sum(bool(r['correct']) for r in qs)/len(qs)*100,1))+'分')
        rows.append([ind['name'],value(v),'；'.join(bits) or '本輪無此構面可比量化題；參閱對話與教師回饋'])
    table(rows,[128,110,273])
    # Radar contains measured self-report only; unassessed post-training axes are not invented.
    vals=[comp.get(i['id'],dims.get(i['dimension'])) for i in indicators]
    if vals and all(v is not None for v in vals):
        w=Drawing(500,245);cx,cy,r=250,125,85;n=len(vals)
        for ring in (.2,.4,.6,.8,1):w.add(Polygon(sum(([cx+r*ring*math.sin(2*math.pi*i/n),cy+r*ring*math.cos(2*math.pi*i/n)] for i in range(n)),[]),strokeColor=colors.HexColor('#D4E1E5'),fillColor=None,strokeWidth=.6))
        points=[]
        for i,(v,ind) in enumerate(zip(vals,indicators)):
            a=2*math.pi*i/n;x,y=cx+r*math.sin(a),cy+r*math.cos(a);w.add(Line(cx,cy,x,y,strokeColor=colors.HexColor('#D4E1E5')));points.extend([cx+r*float(v)/100*math.sin(a),cy+r*float(v)/100*math.cos(a)]);w.add(String(cx+110*math.sin(a),cy+110*math.cos(a),ind['name'],fontName=font,fontSize=7,textAnchor='middle'))
        w.add(Polygon(points,strokeColor=colors.HexColor('#00898B'),fillColor=colors.Color(0,.54,.55,.16),strokeWidth=1.5));story.append(w);story.append(para('雷達圖呈現訓練前職種自評，未將未評核能力畫成零分，也未冒充訓練後能力雷達。','small'))
    section('03  互動、交接與EPA學習證據')
    story.append(para(f"互動訊息 {len(e['messages'])} 筆；EPA／逐格觀察 {len(data.get('frame_notes',[]))} 筆；教師逐格回饋 {len(data.get('frame_note_reviews',[]))} 筆。"))
    for index,note in enumerate(data.get('frame_notes',[]),1):
        snap=note.get('analysis_snapshot') or {};story.extend([para(f"影格觀察 {index} · {note.get('seconds',0):.3f}秒",'sub'),para(note.get('observation'))])
        annotation=snap.get('epa_annotation') or {}
        if annotation:story.append(para('教學目的：'+annotation.get('purpose','未註記')))
    for review in data.get('frame_note_reviews',[]):story.append(para('教師逐格建議：'+review.get('feedback','')))
    sbar=data.get('sbar',{}).get('answers',{})
    if sbar:table([['SBAR交接','學員內容']]+[[k,str(sbar[k])] for k in ('S','B','A','R') if sbar.get(k)],[85,426])
    section('04  教師回饋與後續學習')
    if not teacher:story.append(para('本輪尚待教師整體覆核。請完成待評項目、核對資訊缺口，再與教師討論下一步。'))
    for review in reviews:story.extend([para(review['teacher']+' · '+datetime.datetime.fromtimestamp(review['created']).strftime('%Y-%m-%d %H:%M'),'sub'),para(f"覆核結果 {review['decision']} · 整體分數 {review['score']} · 核定教學等級 {review['level']}"),para(review['note'])])
    story.append(para('建議依教師指出的缺口，回看原片前後語音與影格，說明可見證據、替代解釋及跨職類分工，再安排下一輪練習。'))
    section('附錄 A  訓練對話紀錄')
    if not e['messages']:story.append(para('本輪尚無訓練對話。'))
    for i,m in enumerate(e['messages'],1):story.extend([para(f"{i:03} · {'學員' if m['role']=='user' else '虛擬角色'} · {datetime.datetime.fromtimestamp(m['created']).strftime('%H:%M:%S')}",'sub'),para(m['content'])])
    section('附錄 B  來源與版本')
    story.extend([para('教案來源：'+str(case.get('source_file','未提供'))),para('教案快照：'+e['case_hash'],'small'),para('評量構面來源：'+p['source_file']+'；名稱與順序依職種對應。','small'),para('本報告包含個人學習資料，請僅提供本人或獲授權的教學人員。','small')])
    def page(canvas,doc):
        canvas.setStrokeColor(colors.HexColor('#C6DADD'));canvas.line(42,39,553,39);canvas.setFont(font,8);canvas.setFillColor(colors.HexColor('#526975'));canvas.drawString(42,26,'迴旋梯智鏈 · 個人學習報告');canvas.drawRightString(553,26,f"CT-{e['id']:06d}  |  {doc.page}")
    doc=SimpleDocTemplate(stream,pagesize=(595.28,841.89),rightMargin=42,leftMargin=42,topMargin=42,bottomMargin=54,title='完整訓練成果報告',author='迴旋梯智鏈')
    doc.build(story,onFirstPage=page,onLaterPages=page);return stream.getvalue()

class EmailReport(BaseModel):
    email:str=Field(min_length=3,max_length=254)
    consent:bool=False

def install(app,store,owned_session,current_user):
    def evidence(sid,user):
        row=owned_session(sid,user,require_checkin=False)
        if row['status']!='completed':raise HTTPException(409,'完成訓練後才能產生完整成果報告。')
        return report_data(store,row)
    @app.get('/api/sessions/{sid}/report.pdf')
    def report(sid:int,download:bool=False,user=Depends(current_user)):
        e=evidence(sid,user);raw=pdf_bytes(e)
        return Response(raw,media_type='application/pdf',headers={'Content-Disposition':f"{'attachment' if download else 'inline'}; filename=training-{sid}.pdf",'Cache-Control':'no-store'})
    @app.get('/api/sessions/{sid}/report/summary')
    def summary(sid:int,user=Depends(current_user)):
        e=evidence(sid,user)
        return {'id':sid,'student':e['owner']['display_name'],'title':e['case'].get('title',e['topic']),'self_score':e['scores'].get('summary',{}).get('self_mean'),'objective_score':e['result'].get('objective_score'),'teacher_score':e['reviews'][-1]['score'] if e['reviews'] else None,'teacher_pending':not e['reviews']}
    @app.get('/api/sessions/{sid}/report/pages')
    def pages(sid:int,user=Depends(current_user)):
        from pypdf import PdfReader
        raw=pdf_bytes(evidence(sid,user));return {'count':len(PdfReader(io.BytesIO(raw)).pages),'pdf_sha256':hashlib.sha256(raw).hexdigest()}
    @app.get('/api/sessions/{sid}/report/page/{number}.jpg')
    def image(sid:int,number:int,user=Depends(current_user)):
        return Response(page_image(pdf_bytes(evidence(sid,user)),number),media_type='image/jpeg',headers={'Cache-Control':'no-store'})
    @app.post('/api/sessions/{sid}/report/email')
    def email(sid:int,body:EmailReport,user=Depends(current_user)):
        if not body.consent:raise HTTPException(400,'請先確認將本次學習報告寄至所填信箱。')
        from .workspace_settings import send_pdf
        e=evidence(sid,user);raw=pdf_bytes(e);sent=send_pdf(store,body.email,raw,f'training-{sid}.pdf','迴旋梯智鏈 - 您的完整訓練報告')
        with store.tx() as c:store.event(c,user['id'],sid,'report_email_accepted',{'recipient':body.email,'pdf_sha256':hashlib.sha256(raw).hexdigest()})
        return sent
