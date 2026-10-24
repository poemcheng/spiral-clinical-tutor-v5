"""Private, self-contained teaching reports with actual original/overlay images."""
from pathlib import Path
import base64,hashlib,html,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend import epa_library
OUT=epa_library.LIB/'reports'
esc=lambda x:html.escape(str(x if x is not None else ''))
LABELS={'visible_action':'可見動作與觀察線索','dialogue_function':'對話功能 非逐字稿','action_dialogue_relation':'動作與對話關聯','category':'動作分類','epa_focus':'EPA觀察與安全重點','purpose':'教學目的','limitation':'判讀限制與替代解釋'}
POSE={'subject_posture':'主體與主要姿勢','head_neck':'頭頸','trunk':'軀幹','upper_limbs':'上肢','lower_limbs':'下肢','joints_classification':'關節與互動分類'}
STYLE='''body{font-family:"Microsoft JhengHei",sans-serif;color:#173d49;background:#edf3f4;margin:0;line-height:1.7}main{max-width:1080px;background:white;margin:auto;padding:36px}h1,h2,h3{color:#172e35;line-height:1.45}p,dd{overflow-wrap:anywhere}.source{font-size:13px;color:#526770}dl{margin:8px 0}dt{font-weight:700}dd{margin:0 0 12px}.images{display:grid;grid-template-columns:1fr 1fr;gap:14px}.images img{width:100%;height:auto}figure{margin:0}figcaption{font-size:13px}.keyframe{margin:32px 0;padding-top:20px;border-top:1px solid #bdced2;break-before:page}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border:1px solid #cbd8dc;padding:8px;text-align:left}th{background:#e8eff1}a{color:#12677b}.segment{margin-bottom:28px;border-bottom:1px solid #dce5e7;padding-bottom:16px}@media(max-width:650px){main{padding:18px}.images{grid-template-columns:1fr}}@media print{body{background:white}main{padding:0}h2,h3{break-after:avoid}figure,table{break-inside:avoid}.keyframe{break-before:page}@page{margin:16mm}}'''
def document(title,body):return f'<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><style>{STYLE}</style><main>{body}</main></html>'
def fields(s):return '<dl>'+''.join(f'<dt>{label}</dt><dd>{esc(s[k])}</dd>' for k,label in LABELS.items() if s.get(k))+'</dl>'
def embed(path):return 'data:image/jpeg;base64,'+base64.b64encode(path.read_bytes()).decode()
def clock(s):return f'{int(s)//60:02}:{int(s)%60:02}'
def export():
    OUT.mkdir(exist_ok=True);manifest={};links=[]
    for item in epa_library.catalog()['analyses']:
        clip_id=item['clip_id'];r=epa_library.report(clip_id)
        body=f'<h1>{esc(r["title"])} EPA影格與行為教學解析</h1><p>本報告依使用者提供的EPA分析範例，將原始影像、模型骨架與段落教學註記分開整理，供累積學習Level 4查閱。全片{r["frame_count"]:,}格均已解碼與分析；下方{len(r["keyframes"])}張代表格僅作導覽，其他影格可在平台逐一查閱。</p><p>{esc(r["notice"])}</p><p>模型偵測到人體的影格為{r["detection_frames"]:,}格；此數字不是動作完成次數、正確率或能力分數。</p><p class="source">版本 {esc(r["version"])} · 原片SHA256 {esc(r["source_sha256"])}<br>模型 {esc(r["model"])} · SHA256 {esc(r["model_sha256"])}<br>視角 {esc(json.dumps(r["view"],ensure_ascii=False))}</p><p>{esc(r["dialogue_status"])} {esc(r["competency_codes_note"])}</p><p class="source">{esc(r["annotation_status"])}</p><h2>段落層級動作與對話關聯</h2>'
        for s in r['segments']:body+=f'<section class="segment"><h3>{esc(s["id"])} {clock(s["start"])}至{clock(s["end"])} {esc(s["title"])}</h3><p class="source">{esc(s.get("evidence_type"))}。這是段落脈絡，不宣稱每張圖都完成所列行為。</p>{fields(s)}</section>'
        body+='<h2>關鍵影格與頭頸軀幹肢段解析</h2>'
        for k in r['keyframes']:
            f=epa_library.frame(clip_id,k['frame']);raw=epa_library.image_path(clip_id,k['frame'],False);overlay=epa_library.image_path(clip_id,k['frame'],True)
            body+=f'<section class="keyframe"><h3>{esc(k["id"])} {clock(f["seconds"])} 第{f["frame"]}格 {esc(k.get("title",k.get("visible_action","代表格")))}</h3><div class="images"><figure><img src="{embed(raw)}" alt="原始影格"><figcaption>原始影格 · {f["seconds"]:.3f}秒</figcaption></figure><figure><img src="{embed(overlay)}" alt="模型骨架疊圖"><figcaption>同一格模型估計 · 非臨床關節量測</figcaption></figure></div>'
            body+=fields(f['annotation']) if f.get('annotation') else '<p>此格未提供人工事件註記，請核對前後畫面；不自動補造對話功能。</p>'
            q=(f.get('reference_keyframe') or {}).get('qualitative_pose')
            if q:body+='<h4>來源人工姿勢註記 非精確量測</h4><dl>'+''.join(f'<dt>{POSE.get(key,esc(key))}</dt><dd>{esc(value)}</dd>' for key,value in q.items())+'</dl><p class="source">人工估計角度與視線說明不是本格模型量測，也不代表已核定互動成效。</p>'
            if not f['poses']:body+='<p>本格沒有可靠人體骨架；不補造頭頸、軀幹、上下肢角度。</p>'
            for p in f['poses']:
                body+=f'<h4>候選骨架P{p["track_id"]} 可見關節{p["visible_joints"]}／33</h4><p>軌跡不代表真實身分或職類；頭頸與視線需核對原圖，不由骨架判定理解或情緒。</p><table><tr><th>區域</th><th>可見影像特徵</th><th>估計值</th></tr>'
                for label,key,region in [('左肘','left_elbow','上肢'),('右肘','right_elbow','上肢'),('左膝','left_knee','下肢'),('右膝','right_knee','下肢'),('軀幹偏斜','torso_tilt','軀幹')]:
                    value=p['metrics'].get(key);text='遮擋或未達可見門檻' if value is None else f'{value}°二維投影';body+=f'<tr><td>{region}</td><td>{label}</td><td>{text}</td></tr>'
                body+='</table><p>動作提示：'+esc('、'.join(p['actions']) or '未達提示條件')+'</p>'
                for v in p['interpretations']:body+=f'<p><b>{esc(v["possible"])}</b><br>依據 {esc(v["basis"])}<br>其他解釋 {esc(v["alternative"])}<br>核對方式 {esc(v["verify"])}</p>'
            body+='</section>'
        body+='<h2>來源與核對限制</h2><p>'+esc(r['limitation'])+'</p>'+''.join(f'<p class="source">{esc(s.get("file",s.get("title")))} · {esc(s.get("sha256",""))}</p>' for s in r['annotation_sources'])
        file=OUT/f'{clip_id}.html';file.write_text(document(r['title'],body),encoding='utf8');raw=file.read_bytes();manifest[clip_id]={'file':file.name,'sha256':hashlib.sha256(raw).hexdigest(),'source_sha256':r['source_sha256'],'analysis_id':r['id'],'bytes':len(raw)}
        (OUT/f'{clip_id}.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
        links.append(f'<tr><td><a href="{esc(file.name)}">{esc(r["title"])}</a></td><td>{r["frame_count"]:,}</td><td>{len(r["segments"])}</td><td>{len(r["keyframes"])}</td><td>{"一般影片" if r["projection"]=="flat" else "360固定視角"}</td></tr>')
    text='<h1>EPA影片逐格分析報告總覽</h1><p>本機私有教學影像與解析，累積學習Level 4開放。共'+str(len(manifest))+'部影片，原始錄影、每張影格與報告未上傳公開GitHub。</p><p>原片與骨架逐格計算，代表格用於報告導覽。對話是功能性摘要，人工視覺註記與模型數值分開；不能用單張圖認定理解、信賴或EPA能力。</p><table><tr><th>影片與報告</th><th>全片分析影格</th><th>段落</th><th>代表格</th><th>形式</th></tr>'+''.join(links)+'</table>'
    (OUT/'index.html').write_text(document('EPA影片逐格分析報告總覽',text),encoding='utf8');(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'reports':len(manifest),'frames':sum(x['frame_count'] for x in epa_library.catalog()['analyses']),'index':str(OUT/'index.html')},ensure_ascii=False))
if __name__=='__main__':export()
