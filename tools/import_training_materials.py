"""Deterministic, read-only import of the user-provided workbook and PDF.

Run with the document runtime (pypdf/pdfplumber). Never executes workbook formulas
or treats document prose as application instructions.
"""
import copy
import hashlib
import json
import logging
from pathlib import Path
import re
import shutil
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pypdf import PdfReader
import pdfplumber

logging.getLogger('pdfminer').setLevel(logging.ERROR)
ROOT=Path(__file__).resolve().parents[1]
DOWNLOADS=Path.home()/'Downloads'
XLSX=DOWNLOADS/'肌少症自評題庫_審題表_20261021.xlsx'
PDF=DOWNLOADS/'跨職種擬真教案（依自評等級分流）.pdf'
DEST=ROOT/'data'/'sources';DEST.mkdir(parents=True,exist_ok=True)
if not XLSX.exists():XLSX=DEST/XLSX.name
if not PDF.exists():PDF=DEST/PDF.name
norm=lambda s:unicodedata.normalize('NFKC',str(s or '')).strip()
compact=lambda s:re.sub(r'\s+','',norm(s))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
ROLE={'營養師':'DT','物理治療師':'PT','醫事放射師':'RT','醫師':'MD','護理師':'RN',
      '語言治療師':'ST','聽力師':'AUD','藥師':'RPH','醫事檢驗師':'MLS','臨床心理師':'CP','呼吸治療師':'RSP','職能治療師':'OT'}
META=[
 ('SARC','肌少症','肌少症全人照護',['DT','PT','RT','MD','RN'],'肌少症運動處方之全人照護.mp4'),
 ('STROKE','中風復健合併吞嚥困難','中風復健合併吞嚥困難',['DT','ST','PT','RN','MD'],'中風復健病人合併吞嚥困難之跨團隊營養照護.mp4'),
 ('DEM','失智症／吞嚥困難','失智症合併吞嚥困難',['ST','PT','DT','AUD','RN'],None),
 ('ICU','重症營養照護','重症病人營養照護',['DT','RN','MD','RPH'],'重症病人營養照護與醫護溝通.mp4'),
 ('DM','第一型糖尿病旅遊飲食焦慮','第一型糖尿病旅遊飲食焦慮',['DT','RPH','MD','RN'],'門診焦慮型糖尿病病人-旅遊飲食調整原則及跨領域營養照護.mp4'),
 ('ASTHMA','氣喘用藥順從性不佳','氣喘用藥順從性不佳',['MLS','CP','RPH','MD','RN'],None),
 ('PREG','懷孕婦女外傷','懷孕婦女外傷',['RSP','OT','RT','RN','MD'],None),
 ('BEDXR','床邊孕婦 X 光檢查','床邊孕婦 X 光檢查',['RT','RN','MD'],None),
 ('PEDXR','兒童 X 光溝通與風險判斷','兒童 X 光溝通與風險判斷',['RT','RN','MD'],None),
]


def workbook_rows(path):
    ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as z:
        strings=[''.join(si.itertext()) for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',ns)] if 'xl/sharedStrings.xml' in z.namelist() else []
        rel={r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        sheets={}
        for sheet in ET.fromstring(z.read('xl/workbook.xml')).findall('m:sheets/m:sheet',ns):
            target=rel[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
            target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            rows=[]
            for row in ET.fromstring(z.read(target)).findall('m:sheetData/m:row',ns):
                values={}
                for c in row.findall('m:c',ns):
                    v=c.find('m:v',ns);kind=c.attrib.get('t')
                    text=''.join(c.find('m:is',ns).itertext()) if kind=='inlineStr' else strings[int(v.text)] if kind=='s' and v is not None else v.text if v is not None else ''
                    values[re.sub(r'\d','',c.attrib['r'])]=text or ''
                if values:rows.append((int(row.attrib['r']),values))
            sheets[sheet.attrib['name']]=rows
        return sheets


def import_workbook():
    bank=json.loads((ROOT/'data/item_banks/sarcopenia_item_bank_v1.json').read_text(encoding='utf-8'))
    items={q['item_id']:q for p in bank['professions'].values() for level in p['levels'].values() for kind in ['self','objective'] for q in level[kind]}
    seen=set();reviews={}
    for sheet,rows in workbook_rows(XLSX).items():
        code=sheet.split(' ')[0]
        if code not in bank['professions']:continue
        for row,cols in rows[1:]:
            item_id=cols.get('A','')
            if item_id not in items:raise ValueError(f'題號無法對應：{sheet}!A{row} {item_id}')
            if item_id in seen:raise ValueError('重複題號：'+item_id)
            seen.add(item_id);q=items[item_id]
            if int(cols['B'])!=q['level']:raise ValueError('Level 與題號不符：'+item_id)
            q['prompt']=cols['G']
            q['dimension_name']=cols['D'];q['native_code']=cols['E'];q['native_name']=cols['F']
            if q.get('item_type','self_rating')=='single_choice':
                options=[cols[c] for c in 'HIJK']
                answer=cols.get('L','').strip()
                q['answer']=options[ord(answer)-65] if answer in 'ABCD' and len(answer)==1 else answer
                if len(set(options))!=4 or q['answer'] not in options:raise ValueError('選項／答案不符：'+item_id)
                q['options']=options;q['explanation']=cols.get('M','')
            elif q.get('item_type','self_rating')=='short_answer':
                rubric=cols.get('M','');q['rubric_source_text']=rubric
                matches=list(re.finditer(r'([012])\s*分\s*[:：]',rubric))
                q['rubric']={m.group(1):rubric[m.end():matches[i+1].start() if i+1<len(matches) else len(rubric)].strip() for i,m in enumerate(matches)}
                if set(q['rubric'])!={'0','1','2'}:raise ValueError('簡答評分規準無法解析：'+item_id)
            status=cols.get('O','').strip()
            q['review_status']='刪除' if status=='刪除' else '通過' if status=='通過' and cols.get('Q') and cols.get('R') else '需人工確認修改' if status=='修改後通過' else '待審'
            q['review_record']={'result':status,'suggestion':cols.get('P',''),'reviewer':cols.get('Q',''),'date':cols.get('R','')}
            q['attachment_source']={'file':XLSX.name,'sheet':sheet,'row':row,'sha256':sha(XLSX)}
            if cols.get('N'):q['source_text']=cols['N']
            reviews[q['review_status']]=reviews.get(q['review_status'],0)+1
    if len(seen)!=1250:raise ValueError(f'題庫不完整：{len(seen)} / 1250')
    bank['version']='sarc-xlsx-20261022-v2';bank['attachment_source']={'file':XLSX.name,'sha256':sha(XLSX),'items':len(seen),'review_counts':reviews}
    bank['review_policy']='試辦使用待審草稿；刪除及修改未確認題不抽取，修改建議保留待人工確認。'
    bank['content_hash']=hashlib.sha256(json.dumps(bank,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    (ROOT/'data/item_banks/sarcopenia_item_bank_uploaded.json').write_text(json.dumps(bank,ensure_ascii=False,indent=2),encoding='utf-8')
    return bank['attachment_source']


def section(text,start,end=None):
    if start not in text:return ''
    value=text.split(start,1)[1]
    return value.split(end,1)[0].strip() if end and end in value else value.strip()


def import_pdf():
    reader=PdfReader(PDF);pages=[norm(p.extract_text()) for p in reader.pages]
    starts=[]
    for number,text in enumerate(pages,1):
        for match in re.finditer(r'教案([一二三四五六七八九])[:：]',text):starts.append((number,match.start(),text[match.start():].splitlines()[0]))
    starts=starts[:9]
    if len(starts)!=9:raise ValueError('教案標題數量不符：'+str(starts))
    courses=[]
    for i,(code,topic,title,roles,video) in enumerate(META):
        start=starts[i];end=starts[i+1] if i<8 else (37,len(pages[36]),'')
        texts=pages[start[0]-1:end[0]]
        if start[0]==end[0]:text=pages[start[0]-1][start[1]:end[1]]
        else:text='\n'.join([texts[0][start[1]:],*texts[1:-1],texts[-1][:end[1]]])
        text=re.sub(r'跨職種擬真教案[^\n]*|Page \d+ of 38','',text)
        courses.append({'id':'COURSE-'+code,'topic':topic,'title':title,'professions':roles,'video_file':video,
            'source_file':PDF.name,'source_sha256':sha(PDF),'source_pages':[start[0],end[0]],'source_text':text,
            'summary':text.splitlines()[1].strip() if len(text.splitlines())>1 else title,
            'patient':section(text,'病例情境','各職種任務'),'goals_text':section(text,'學習目標','病例情境'),
            'roles':{},'levels':{},'rubric_rows':{},'decisions':[],
            'review_status':'待臨床教師審核','original_source_available':i in (0,1,3,4)})
    clean_pages=[]
    with pdfplumber.open(PDF) as pdf:
        current=-1
        for number,page in enumerate(pdf.pages,1):
            boxes=[t.bbox for t in page.find_tables()]
            clean=page.filter(lambda obj:not any(obj.get('x0',-1)>=b[0]-1 and obj.get('x1',0)<=b[2]+1 and obj.get('top',-1)>=b[1]-1 and obj.get('bottom',0)<=b[3]+1 for b in boxes))
            clean_pages.append(norm(clean.extract_text() or ''))
            headings=page.search(r'教案[一二三四五六七八九⼀⼆⼋][:：]') or []
            # Page search may miss compatibility ideographs. Use source page and table geometry as fallback.
            markers=[]
            for heading in headings:
                title=norm(heading['text']);idx='一二三四五六七八九'.find(title[2])
                if idx>=0 and number<38:markers.append((heading['top'],idx))
            for table in page.find_tables():
                data=table.extract()
                for n,row in enumerate(data):
                    cells=[norm(c) for c in row if c is not None]
                    if not cells:continue
                    top=table.rows[n].bbox[1]
                    eligible=[(y,idx) for y,idx in markers if y<=top]
                    idx=max(eligible)[1] if eligible else current
                    if idx<0:continue
                    c=courses[idx];first=compact(cells[0])
                    if first in ROLE and len(cells)>=3:
                        c['roles'][ROLE[first]]={'task':cells[1].replace('\n',''),'mapped_items':cells[2].replace('\n',''),'page':number}
                    elif re.fullmatch(r'L[1-5]',first) and len(cells)>=4:
                        c['levels'][first[1]]={'patient_behavior':cells[1].replace('\n',''),'support':cells[2].replace('\n',''),'learner_task':cells[3].replace('\n',''),'page':number}
                    elif re.fullmatch('[1-9]',first) and len(cells)>=3 and len(cells[1])<100:
                        c['rubric_rows'][first]={'title':cells[1].replace('\n',''),'standard':cells[2].replace('\n',''),'page':number}
            if markers:current=max(markers)[1]
        # Visual source inspection artifacts (read-only rendering).
        review=ROOT.parent/'output/step1_4_sources_20261022'
        review.mkdir(parents=True,exist_ok=True)
        for n in (3,5):pdf.pages[n].to_image(resolution=110).save(str(review/f'pdf_page_{n+1}.png'))
    for c in courses:
        decision_text=section(c['source_text'],'關鍵決策點','標準化病人劇本要點')
        for match in re.finditer(r'(?:^|\n)\s*(\d+)\s*[.．]\s*(.+?)(?=(?:\n\s*\d+\s*[.．])|\Z)',decision_text,re.S):
            raw=match.group(2);heading=raw.splitlines()[0].strip()
            good=section(raw,'最佳做法:','常見錯誤:') or section(raw,'最佳做法：','常見錯誤：')
            bad=section(raw,'常見錯誤:') or section(raw,'常見錯誤：')
            good=re.sub(r'\s+',' ',good).strip();bad=re.sub(r'\s+',' ',bad).strip()
            bad=re.split(r'職種\s+任務|等\s*級\s|項目\s+內容',bad)[0].strip()
            if not good:continue
            c['decisions'].append({'id':c['id']+'-D'+match.group(1),'title':heading,'correct':good,'incorrect':bad,
                'critical':any(term in (good+bad) for term in ['嗆','低血糖','血氧','胎動','異常事件','病史與傷勢','照野','站遠','再餵食','只憑','安全','防護'])})
        c['rubric']=list(c.pop('rubric_rows').values())
        c['debriefing']=section(c['source_text'],'Debriefing','參考指引')[-3000:]
        c['patient_script']=section(c['source_text'],'標準化病人劇本要點','評分表')
        missing=set(c['professions'])-set(c['roles'])
        if missing:raise ValueError(f'{c["id"]} 缺職種任務：{missing}')
        if len(c['levels'])!=5:raise ValueError(f'{c["id"]} 缺分級版本：{c["levels"].keys()}')
        if len(c['decisions'])<3:raise ValueError(f'{c["id"]} 決策擷取不完整：{len(c["decisions"])}')
    payload={'version':'uploaded-curriculum-20261022-v1','source':PDF.name,'sha256':sha(PDF),'courses':courses,
        'level_policy':'教師核定 Level 為訓練分級；自評只推薦弱項任務。新學員 Level 1，不依自評直接跳級。'}
    (ROOT/'data/course_catalog.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    return [{'id':c['id'],'roles':len(c['roles']),'levels':len(c['levels']),'decisions':len(c['decisions']),'rubric':len(c['rubric'])} for c in courses]


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--workbook',type=Path);parser.add_argument('--curriculum',type=Path);args=parser.parse_args()
    if args.workbook:XLSX=args.workbook.resolve()
    if args.curriculum:PDF=args.curriculum.resolve()
    question_audit=import_workbook();course_audit=import_pdf()
    for file in (XLSX,PDF):
        if file.resolve()!=(DEST/file.name).resolve():shutil.copyfile(file,DEST/file.name)
    audit={'questions':question_audit,'courses':course_audit,'combinations':sum(c['roles'] for c in course_audit)}
    (ROOT/'data/sources/import_manifest.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(audit,ensure_ascii=False))


