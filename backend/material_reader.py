"""Read-only, inline source documents with a fixed allowlist and role checks."""
import functools,zipfile
import xml.etree.ElementTree as ET
from fastapi import Depends,HTTPException
from .config import ROOT
NAMES={'curriculum':'跨職種擬真教案（依自評等級分流）.pdf','questions':'肌少症自評題庫_審題表_20261021.xlsx','core-competencies':'核心能力.docx'}

@functools.lru_cache(maxsize=12)
def extract(path,size,mtime):
    from pathlib import Path
    p=Path(path)
    if p.suffix=='.pdf':
        from pypdf import PdfReader
        return [{'number':i+1,'text':page.extract_text() or '本頁無可擷取文字，請切換原始PDF畫面。'} for i,page in enumerate(PdfReader(p).pages)]
    with zipfile.ZipFile(p) as z:
        if p.suffix=='.docx':
            tree=ET.fromstring(z.read('word/document.xml'));ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            text='\n'.join(''.join(t.text or '' for t in x.findall('.//w:t',ns)) for x in tree.findall('.//w:p',ns));return [{'number':1,'text':text}]
        ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'};strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():strings=[''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        pages=[]
        for name in sorted(x for x in z.namelist() if x.startswith('xl/worksheets/sheet') and x.endswith('.xml')):
            lines=[]
            for row in ET.fromstring(z.read(name)).findall('.//s:row',ns):
                cells=[]
                for c in row.findall('s:c',ns):
                    v=c.find('s:v',ns);text=v.text if v is not None else ''.join(c.find('s:is',ns).itertext()) if c.find('s:is',ns) is not None else ''
                    if c.attrib.get('t')=='s' and text:text=strings[int(text)]
                    cells.append(text or '')
                lines.append(' ｜ '.join(cells))
            pages.append({'number':len(pages)+1,'text':'\n'.join(lines)})
        return pages

def install(app,current_user):
    @app.get('/api/materials/{kind}/read')
    def read(kind:str,user=Depends(current_user)):
        if kind not in NAMES:raise HTTPException(404,'未知教材。')
        if kind=='questions' and user['role'] not in ('teacher','admin'):raise HTTPException(403,'題庫答案限教師與管理員。')
        p=ROOT/'data/sources'/NAMES[kind]
        if not p.is_file():raise HTTPException(404,'原始教材未安裝，請聯絡教材管理者。')
        st=p.stat();return {'title':NAMES[kind],'kind':kind,'pages':extract(str(p),st.st_size,st.st_mtime_ns),'pdf_url':'/api/materials/'+kind if p.suffix=='.pdf' else None}
