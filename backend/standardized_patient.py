"""Source-bound disclosure and record lookup, inspired by VSP's case/model split.

These are teaching records, not performed examinations. Missing is never normal.
No external VSP cases, answer keys, or learner data are imported.
"""
import hashlib,re

VERSION='standardized-patient-5.6.0'
TOPICS={
 'diet':('飲食','飲料','喝','吃','奶茶','珍奶','點心','攝取','三餐'),
 'activity':('運動','活動','快走','伸展','散步','訓練'),
 'bowel':('排便','解便','便秘','腹瀉','大便'),
 'feeding':('灌食','管灌','腹脹','脹氣','耐受'),
 'environment':('環境','病房','訪客','電視','吵','安靜','用餐地點'),
 'support':('照顧','家人','家屬','陪伴','協助者'),
 'injury':('跌倒','摔倒','外傷','撞到','碰撞','受傷','受傷經過','桌角'),
 'fetal_movement':('胎動','胎兒活動','寶寶動'),
 'medication':('用藥','藥物','吸入','吸藥','帶藥','忘記','藍色那支'),
 'vertigo':('眩暈','暈眩','頭暈','天旋地轉','轉頭','躺下'),
}
SECTIONS={
 'body':('體位與營養紀錄',('身高','體重','BMI','熱量','蛋白','飲食','牛奶','排骨','珍奶','奶茶')),
 'imaging':('影像與檢查紀錄',('DXA','ALMI','BMD','檢查','攝影','血','檢驗')),
 'function':('功能與活動紀錄',('疲勞','活動','肌力','握力','坐站','快走','伸展','散步','復健','治療')),
 'care':('照護與生活紀錄',('同住','照顧','家屬','病房','灌','吞嚥','進食','訪客','電視')),
}

def normalized(text):
    return re.sub(r'\s+','',text).replace('珍珠奶茶','珍奶').replace('奶茶','珍奶')

def topics(text):
    return {key for key,words in TOPICS.items() if any(word in normalized(text) for word in words)}

def hidden_facts(case):
    script=case.get('patient_script') or ''
    found=re.findall(r'只在被問到時才說[：:]([^\n]+)',script)
    facts=[]
    for line in found:
        for clause in re.split(r'[、；;。]',line):
            clause=clause.strip()
            if not clause:continue
            facts.append({'id':hashlib.sha256(clause.encode()).hexdigest()[:16],
                          'text':clause,'topics':sorted(topics(clause))})
    return facts

def direct_topics(text):
    if re.search(r'隱藏資訊|標準答案|系統提示|忽略(?:規則|指令)',text):return set()
    if re.search(r'[?？]|請問|想了解|告訴我|說說|談談|說明|如何|什麼|有沒有|是否|能不能|怎麼|哪些|哪裡|何時|多少|多久|幾次|呢|嗎',text):return topics(text)
    return set()

def disclosure_view(case,actor,messages,text):
    facts=hidden_facts(case);asked=set()
    for message in messages:
        if message['role']=='user':asked.update(direct_topics(message['content']))
    asked.update(direct_topics(text))
    allowed=[f for f in facts if set(f['topics'])&asked]
    withheld=[f for f in facts if f not in allowed]
    held_topics={key for fact in withheld for key in fact['topics']}
    # Restrict all occurrences, including equivalent phrasing already in the brief.
    source=case.get('patient','').split('判讀重點')[0]
    chunks=[chunk.strip() for chunk in re.split(r'[。；;\n，,]',source) if chunk.strip()]
    def permitted(chunk):
        return not topics(chunk)&held_topics and not any(normalized(f['text']) in normalized(chunk) for f in withheld)
    visible=[chunk for chunk in chunks if permitted(chunk)]
    opening=re.split(r'只在被問到時才說|信任上升|信任下降',case.get('patient_script') or '')[0].strip()
    # A scripted opening may also contain restricted facts. Apply the same gate.
    opening='。'.join(chunk for chunk in re.split(r'[。；;\n]',opening) if permitted(chunk))
    view={**case,'patient':'。'.join(visible),'patient_script':opening+('\n已被具體詢問的來源資料：'+'；'.join(f['text'] for f in allowed) if allowed else '')}
    audit={'version':VERSION,'eligible_fact_ids':[f['id'] for f in allowed],
           'withheld_fact_ids':[f['id'] for f in withheld],'asked_topics':sorted(asked),
           'eligibility_is_not_observed_disclosure':True,'source_only':True}
    return view,audit

def hidden_leaks(case,audit,reply):
    withheld=set(audit['withheld_fact_ids']);body=normalized(reply);leaks=[]
    for fact in hidden_facts(case):
        if fact['id'] not in withheld:continue
        original=normalized(fact['text'])
        anchors=[word for word in ('珍奶','快走','伸展','解便正常','排便正常','沒有脹氣','訪客','電視','胎動','桌角','藍色那支','忘記帶藥','天旋地轉') if word in original]
        if original in body or any(word in body for word in anchors):leaks.append(fact['id'])
    return leaks

def records(case):
    source=case.get('patient','').split('判讀重點')[0]
    chunks=[x.strip() for x in re.split(r'[。\n；;]',source) if x.strip()]
    return [{'id':key,'title':title,'excerpts':[c for c in chunks if any(word.lower() in c.lower() for word in words)],
             'source_file':case.get('source_file'),'source_pages':case.get('source_pages',[]),
             'source_hash':hashlib.sha256(source.encode()).hexdigest(),
             'scope':'existing_teaching_record_not_new_examination'}
            for key,(title,words) in SECTIONS.items()]

def lookup(case,section):
    row=next((item for item in records(case) if item['id']==section),None)
    if row is None:raise ValueError('未知紀錄分類。')
    return {**row,'provided':bool(row['excerpts']),'message':'教案未提供此類紀錄；不能視為檢查正常。' if not row['excerpts'] else '以下僅引述教案既有紀錄；查閱不表示已實際執行檢查。'}
