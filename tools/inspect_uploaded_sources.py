"""Read-only attachment inspection. Writes extraction evidence, never edits originals."""
import json
import hashlib
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parent/'output'/'step1_4_sources_20261022'
OUT.mkdir(parents=True,exist_ok=True)
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
book=Path(r'C:\Users\User\Downloads\肌少症自評題庫_審題表_20261021.xlsx')
with zipfile.ZipFile(book) as archive:
    strings=[]
    if 'xl/sharedStrings.xml' in archive.namelist():
        strings=[''.join(el.itertext()) for el in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('m:si',NS)]
    rels={r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
    sheets=[]
    for s in ET.fromstring(archive.read('xl/workbook.xml')).findall('m:sheets/m:sheet',NS):
        target=rels[s.attrib['{'+NS['r']+'}id']]
        name=target.lstrip('/') if target.startswith('/') else 'xl/'+target
        rows=[]
        for row in ET.fromstring(archive.read(name)).findall('m:sheetData/m:row',NS):
            values={}
            for c in row.findall('m:c',NS):
                kind=c.attrib.get('t');value=c.find('m:v',NS)
                if kind=='inlineStr':text=''.join(c.find('m:is',NS).itertext())
                elif value is not None:text=strings[int(value.text)] if kind=='s' else value.text
                else:text=''
                if text:values[c.attrib['r']]=text
            if values:rows.append({'row':int(row.attrib['r']),'cells':values})
        sheets.append({'name':s.attrib['name'],'rows':rows})
    payload={'file':str(book),'sha256':hashlib.sha256(book.read_bytes()).hexdigest(),'sheets':sheets}
    (OUT/'workbook_cells.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'workbook':book.name,'sheets':[{'name':s['name'],'rows':len(s['rows']),'head':s['rows'][:5]} for s in sheets]},ensure_ascii=False))

from pypdf import PdfReader
pdf=Path(r'C:\Users\User\Downloads\跨職種擬真教案（依自評等級分流）.pdf')
reader=PdfReader(pdf)
pages=[p.extract_text() or '' for p in reader.pages]
(OUT/'uploaded_curriculum.txt').write_text('\n\n'.join(f'--- PAGE {i+1} ---\n{t}' for i,t in enumerate(pages)),encoding='utf-8')
print(json.dumps({'pdf':pdf.name,'pages':len(pages),'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'text':[{'page':i+1,'chars':len(t),'text':t[:2300]} for i,t in enumerate(pages)]},ensure_ascii=False))
