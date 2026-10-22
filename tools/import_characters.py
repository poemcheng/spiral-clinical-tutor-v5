"""Copy supplied role cards without editing pixels and build a versioned actor catalog."""
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT/'data/characters'
ROLES = [
 ('chen-md','陳醫師','MD','clinician','male','#f5f7fc','#394251',True,'老年醫學／復健科醫師','病史與功能評估；判讀風險與安排轉介；整合復健、營養與照護計畫','沉穩、專業、具安撫性，以白話解釋資訊','您好，我先了解您最近的狀況。'),
 ('lin-rn','林護理師','RN','clinician','female','#f6f8fd','#332c28',False,'護理師','生命徵象與跌倒風險評估；症狀觀察與衛教；回報異常並協調後續處置','親切、細心、善於安撫，用清楚易懂的方式說明','最近有沒有頭暈、無力或容易跌倒？'),
 ('wang-pt','王物理治療師','PT','clinician','male','#233752','#302b26',False,'物理治療師','坐站、步態與平衡評估；肌力與移動能力訓練；跌倒預防與居家運動建議','積極鼓勵、動作示範清楚，重視安全與功能改善','請先站穩，我會在旁邊保護您。'),
 ('zhang-ot','張職能治療師','OT','clinician','female','#eef2f9','#332c28',False,'職能治療師','ADL與IADL評估；手功能與認知訓練；輔具與居家環境建議','溫和、務實、以任務導向引導，重視生活情境','我們看看哪些活動對您最困難。'),
 ('huang-dt','黃營養師','DT','clinician','female','#fafbfe','#46332c',False,'營養師','飲食史與營養風險評估；蛋白質與熱量需求分析；制定可執行的飲食建議','耐心、生活化，將專業轉為白話','最近三餐吃得怎麼樣？'),
 ('li-rph','李藥師','RPH','clinician','male','#f9fbfe','#302c28',True,'藥師','藥物盤點與服藥紀錄；交互作用與副作用評估；服藥依從性與安全衛教','謹慎、清楚、重視安全，耐心解釋用藥重點','您平常有固定服用哪些藥物？'),
 ('he-sw','何社工師','SW','support','female','#d2b9a2','#3b2c26',False,'社工師／個案管理師','家庭支持與照顧壓力評估；長照與社福資源連結；出院與追蹤照護協調','關懷、耐心、擅長傾聽，協助整合外部資源','家裡平常主要是誰在照顧您？'),
 ('auntie-lin','林阿姨',None,'patient','female','#d5c1ad','#a19b94',True,'高齡肌少症風險病患','辨識肌少症線索；完成篩檢並提出轉介建議','客氣保守、不主動抱怨，需要溫和引導','最近比較沒力，走一下就累。'),
 ('mr-chen','陳先生',None,'patient','male','#bfd3e8','#9b9791',False,'術後復健病患','疼痛溝通；安全移動；分階段復健指導','焦慮但願意配合，說明安全性後較放心','我一動就會痛。'),
 ('mr-wang','王先生',None,'caregiver','male','#26364d','#34312f',True,'家屬／主要照顧者','補充病史與居家資訊；表達照顧壓力與支持需求；配合訓練與追蹤','關心病人，但在工作與照護之間拉扯','需要怎麼安排會比較安全？'),
]

def main():
 DEST.mkdir(parents=True,exist_ok=True)
 source=Path.home()/'Downloads'
 cards=[]
 for i,r in enumerate(ROLES,1):
  aid,name,profession,kind,gender,outfit,hair,glasses,title,tasks,style,quote=r
  match=list(source.glob(f'ChatGPT 圖像 2026年10月22日 上午12_51_*-{i}.png'))
  if len(match)!=1:raise RuntimeError(f'角色卡 {i} 來源不唯一或不存在')
  target=DEST/f'{aid}.png';shutil.copyfile(match[0],target)
  cards.append(dict(id=aid,name=name,profession=profession,kind=kind,gender=gender,title=title,
   tasks=tasks,style=style,quote=quote,outfit=outfit,hair=hair,glasses=glasses,
   card_file=target.name,model_file=aid+'.vrm',source_file=match[0].name,
   card_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
   usage='使用者提供之角色參考；原圖完整保留，3D為依造型特徵製作之風格化模型，非真人掃描。'))
 (DEST/'catalog.json').write_text(json.dumps(dict(version='characters-20261022-1',actors=cards),ensure_ascii=False,indent=2),encoding='utf-8')
 backup=ROOT.parent/'output/角色整合修改前_20261022.sqlite3';backup.parent.mkdir(exist_ok=True)
 if not backup.exists():
  with sqlite3.connect(ROOT/'runtime/clinical_tutor.sqlite3') as src,sqlite3.connect(backup) as dst:src.backup(dst)
 print(f'Imported {len(cards)} unchanged cards; backup {backup}')

if __name__=='__main__':main()
