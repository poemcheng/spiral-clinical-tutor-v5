"""Source-backed teaching review notes; not an expert publication approval."""
REVIEW={
 'version':'clinical-source-review-20261022-1',
 'status':'已核對來源與教學界線；臨床專家正式核定待完成',
 'items':[
  {'topic':'肌少症診斷版本','note':'原教案與題庫的診斷題依AWGS 2019作答。AWGS 2025已改為低肌肉量合併低肌力，身體功能作為結果指標；不可混用兩版診斷演算法。', 'url':'https://pubmed.ncbi.nlm.nih.gov/41188603/'},
  {'topic':'DXA與骨質評估','note':'ALMI/ASMI是肌肉量指標，不等於完整肌少症診斷。停經後女性的骨質分類通常採T分數；不得以Z分數高於−2就排除骨質疏鬆或肌少症。','url':'https://iscd.org/official-positions-2023/'},
  {'topic':'阻力與平衡活動','note':'阻力訓練需個別化、漸進並注意安全；一般成人及長者肌力活動建議每週至少2天，不能將一般建議當成個別病人的完整處方。','url':'https://www.who.int/initiatives/behealthy/physical-activity/'}],
 'general':['只使用來源教案已提供的病史與數值；資料不足需核對，不由AI補造。','職種類別限制、人工覆核與正式評量仍保留。','進階路徑改變學習任務與支持程度，不自行新增病人疾病或數值。','原教案的健保療程與院內流程需依當期規定及院方確認，不作跨院通用規則。']}

# Reviewed teaching adapters preserve the attached PDF and original catalogue verbatim.
CORRECTIONS={
 'COURSE-ICU':[
  {'match':'胃殘留','text':'依灌食階段、腸胃耐受與院內規範監測；若測量胃殘留，超過500 mL／6小時需延後腸道灌食並由團隊評估。出現腹部急症或其他不耐受警訊時，不得等待達到此數值才處理。',
   'note':'補足500 mL的6小時觀察區間，移除「只有超過數值才能暫停」的絕對敘述。',
   'url':'https://7.espen.org/files/ESPEN-Guidelines/ESPEN_practical_and_partially_revised_guideline_Clinical_nutrition_in_the_intensive_care_unit.pdf'}],
 'COURSE-PREG':[
  {'match':'產科警訊','text':'詢問腹部撞擊、出血、腹痛、收縮與胎動變化，優先評估母體並會診婦產科；依孕週、胎兒可存活性與警訊安排監測。可存活妊娠外傷後至少觀察4–6小時，異常時延長，依院內產科流程執行。',
   'note':'補足孕週與胎兒可存活性的適用條件，監測時間由產科與院內流程決定。',
   'url':'https://www.east.org/education-resources/practice-management-guidelines/details/trauma-in-pregnancy-a-systematic-review-metaanalysis-and-practice-management-guideline-from-the-east'}]}


def apply_corrections(case):
    import copy
    notes=copy.deepcopy(case['clinical_review'])
    safety_ids={'COURSE-STROKE':['D3','D4'],'COURSE-DM':['D3'],'COURSE-ASTHMA':['D3'],
                'COURSE-PEDXR':['D3','D5'],'COURSE-BEDXR':['D4']}
    for q in case['kdp']:
        if q['id'].split('-')[-1] in safety_ids.get(case['id'],[]):q['critical']=True
    if case['id']=='COURSE-BEDXR':
        for q in case['kdp']:
            if q['id'].endswith('-D5'):
                q['options'][1]['text']='未確認疑慮及後續說明對象，直接結束檢查。'
                for quiz in case['quiz']:
                    if quiz['id']==q['id']+'-Q':quiz['options'][1]=q['options'][1]['text']
        notes.setdefault('items',[]).append({'topic':'匯入選項修復','note':'檢查後溝通題的空白錯誤選項已補為平台撰寫待審選項；原始PDF不變。','url':''})
    for correction in CORRECTIONS.get(case['id'],[]):
        for q in case['kdp']:
            if correction['match'] in q['phase']:
                old=q['options'][0]['text'];new=correction['text']
                q['options'][0].update(text=new,feedback='來源指引補充：'+new)
                q['hint']=new
                for quiz in case['quiz']:
                    if quiz['id']==q['id']+'-Q':
                        quiz.update(options=[new if o==old else o for o in quiz['options']],answer=new,explain=new)
                notes.setdefault('items',[]).append({'topic':correction['match'],'note':correction['note'],'url':correction['url']})
    # Correct obvious OCR errors only in displayed teaching material.
    for q in case['kdp']:
        for o in q['options']:
            for key in ('text','feedback'):o[key]=o[key].replace('黛衣','鉛衣').replace('黛手套','鉛手套')
    for q in case['quiz']:
        for key in ('answer','explain'):q[key]=q[key].replace('黛衣','鉛衣').replace('黛手套','鉛手套')
        q['options']=[s.replace('黛衣','鉛衣').replace('黛手套','鉛手套') for s in q['options']]
    case['clinical_review']=notes
    case['clinical_review_version']=REVIEW['version']
    return case
