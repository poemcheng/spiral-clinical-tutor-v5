"""Portable H5P practice content; formal decisions remain server graded."""
import hashlib
import html
import json
from . import characters
from .config import ROOT

def content(row):
    case=row['payload']['case_snapshot'];a=characters.selected(row)
    question=f"<p>{html.escape(case['title'])}｜Level {row['level']}｜與{html.escape(a['name'])}互動</p><p>當對話需要的資料不在本輪教案中，最合適的處理方式是？</p>"
    result={'question':question,'answers':[
        {'text':'<div>清楚記錄資料缺口，向適當團隊成員核對，依教師核定規準再決策。</div>','correct':True,'tipsAndFeedback':{'chosenFeedback':'辨識不確定性並保存來源，讓教師可追溯判斷。'}},
        {'text':'<div>自行補上檢驗數值，讓對話完整。</div>','correct':False,'tipsAndFeedback':{'chosenFeedback':'不可把推測當成病例事實。'}},
        {'text':'<div>把虛擬人的任何回覆直接當成正式評分。</div>','correct':False,'tipsAndFeedback':{'chosenFeedback':'AI模擬與正式教師評量分開保存。'}}],
      'behaviour':{'enableRetry':True,'enableSolutionsButton':True,'enableCheckButton':True,'type':'single','singlePoint':True,'randomAnswers':True,'showSolutionsRequiresInput':True,'confirmCheckDialog':False,'confirmRetryDialog':False,'autoCheck':False,'passPercentage':100,'showScorePoints':True},
      'UI':{'checkAnswerButton':'檢查答案','submitAnswerButton':'提交','showSolutionButton':'顯示解答','tryAgainButton':'再練習','tipsLabel':'提示','scoreBarLabel':'練習得分 :num / :total','tipAvailable':'有提示','feedbackAvailable':'有回饋','readFeedback':'閱讀回饋','wrongAnswer':'請再確認','correctAnswer':'正確','shouldCheck':'此選項應勾選','shouldNotCheck':'此選項不應勾選','noInput':'請先選擇答案','a11yCheck':'檢查答案','a11yShowSolution':'顯示解答','a11yRetry':'再練習'},
      'overallFeedback':[{'from':0,'to':99,'feedback':'請回到教案與角色職責，確認資料來源。'},{'from':100,'to':100,'feedback':'已完成資料界線練習；正式決策仍在平台作答。'}]}
    version=hashlib.sha256(json.dumps([result,a['id'],a['version'],row['payload']['case_hash']],sort_keys=True).encode()).hexdigest()
    return result,version

def manifest():
    libs=json.loads((ROOT/'frontend/vendor/h5p-libraries/provenance.json').read_text())
    return {'title':'案例資料與角色界線練習','language':'zh-tw','mainLibrary':'H5P.MultiChoice','embedTypes':['iframe'],
      'preloadedDependencies':[{'machineName':name,'majorVersion':d['majorVersion'],'minorVersion':d['minorVersion']} for name,d in libs.items()]}
