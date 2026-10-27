import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import {setTimeout as pause} from 'node:timers/promises';
import {JSDOM, VirtualConsole} from 'jsdom';

const site = new URL('../../web_portal/catia/', import.meta.url);
const [html, dataScript, source] = await Promise.all(['index.html', 'learning-data.js', 'app.js'].map(name => readFile(new URL(name, site), 'utf8')));
const storageKey = 'catia-public-learning-v1';

function workspace(hash = '#overview', saved = null, failStorage = false) {
  const errors = [];
  const console = new VirtualConsole();
  console.on('jsdomError', error => errors.push(error.message));
  const dom = new JSDOM(html, {url: 'https://poemcheng.github.io/spiral-clinical-tutor-v5/catia/' + hash,
    runScripts: 'outside-only', virtualConsole: console});
  const w = dom.window;
  w.scrollTo = () => {};
  w.confirm = () => true;
  w.print = () => {};
  let exported;
  w.URL.createObjectURL = blob => {exported = blob; return 'blob:test';};
  w.URL.revokeObjectURL = () => {};
  w.HTMLAnchorElement.prototype.click = () => {};
  if (saved) w.localStorage.setItem(storageKey, saved);
  if (failStorage) Object.defineProperty(w, 'localStorage', {value: {
    getItem() {throw new Error('storage disabled');},
    setItem() {throw new Error('storage disabled');},
  }});
  w.eval(dataScript);
  w.eval(source);
  const q = selector => w.document.querySelector(selector);
  const navigate = hash => {w.history.replaceState(null, '', hash); w.dispatchEvent(new w.HashChangeEvent('hashchange'));};
  const input = (selector, value) => {const field=q(selector); assert.ok(field, selector); field.value=value; field.dispatchEvent(new w.Event('input',{bubbles:true}));};
  const change = (selector, checked = true) => {const field=q(selector); assert.ok(field, selector); field.checked=checked; field.dispatchEvent(new w.Event('change',{bubbles:true}));};
  const state = () => JSON.parse(w.localStorage.getItem(storageKey));
  const importProgress = async value => {
    const text=typeof value==='string'?value:JSON.stringify(value);
    Object.defineProperty(q('#import-file'),'files',{configurable:true,value:[{size:text.length,text:async()=>text}]});
    q('#import-file').dispatchEvent(new w.Event('change',{bubbles:true}));
    await pause(20);
  };
  const download = () => new Promise((resolve,reject)=>{
    q('[data-action="export"]').click();
    const reader=new w.FileReader();reader.onload=()=>resolve(JSON.parse(reader.result));reader.onerror=reject;reader.readAsText(exported);
  });
  return {dom,w,q,navigate,input,change,state,importProgress,download,errors,data:w.CATIA_LEARNING_DATA};
}

test('three stages, nine practical lessons and both quiz groups render under GitHub project path',()=>{
  const s=workspace();
  try {
    assert.equal(s.data.lessons.length,9);
    for(const stage of s.data.stages) {
      s.navigate('#assignment/'+stage.id);
      assert.equal(s.w.document.querySelectorAll('[data-answer]').length,12);
      assert.equal(s.w.document.querySelectorAll('fieldset').length,2);
      assert.ok(s.q('table'));
    }
    for(const lesson of s.data.lessons) {
      s.navigate('#lesson/'+lesson.id);
      assert.equal(s.w.document.querySelectorAll('[data-check]').length,lesson.steps.length);
      assert.equal(s.w.document.querySelectorAll('fieldset').length,2);
      for(const step of lesson.steps) assert.ok(s.q('#main').textContent.includes(step.checkpoint));
    }
    assert.deepEqual(s.errors,[]);
  } finally {s.dom.window.close();}
});

test('answers persist across reload, remain escaped, and export with learner and practice progress',async()=>{
  const s=workspace();let restored;
  try {
    const stage=s.data.stages[0],qid=stage.prompts['1'][0].id;
    s.navigate('#assignment/'+stage.id);
    const text='<img src=x onerror=alert(1)>孔位與基準的測試作答';
    s.input(`[data-answer="${qid}"]`,text);
    s.w.dispatchEvent(new s.w.Event('pagehide'));
    const lesson=s.data.lessons[0];
    s.navigate('#lesson/'+lesson.id);
    s.change(`[data-check="${lesson.id}::0"]`);
    s.change(`[data-lesson-complete="${lesson.id}"]`);
    const quiz=lesson.quiz[0];
    s.change(`[data-quiz-id="${quiz.id}"][value="${quiz.answer}"]`);
    assert.ok(s.q('.quiz-feedback.correct').textContent.includes(quiz.explanation));
    s.navigate('#progress');s.input('#learner-name','測試學員');
    const exported=await s.download();
    assert.equal(exported.answers[qid],text);
    assert.equal(exported.learner,'測試學員');
    assert.equal(exported.checks[`${lesson.id}::0`],true);
    assert.equal(exported.completed[lesson.id],true);
    assert.equal(exported.quizzes[quiz.id],quiz.answer);
    restored=workspace('#assignment/'+stage.id,s.w.localStorage.getItem(storageKey));
    assert.equal(restored.q(`[data-answer="${qid}"]`).value,text);
    assert.equal(restored.q('img'),null);
    assert.deepEqual(s.errors,[]);
  } finally {s.dom.window.close();restored?.dom.window.close();}
});

test('imports merge valid stage quizzes and reject corrupt or unknown records without losing answers',async()=>{
  const s=workspace('#progress');
  try {
    const stage=s.data.stages[1],qid=stage.prompts['1'][0].id,quiz=stage.quizzes[0];
    const initial=s.state();
    await s.importProgress({...initial,learner:'匯入測試',answers:{[qid]:'24與23.6的間隙計算'},quizzes:{[quiz.id]:quiz.answer}});
    assert.equal(s.state().answers[qid],'24與23.6的間隙計算');
    assert.equal(s.state().quizzes[quiz.id],quiz.answer);
    const before=s.w.localStorage.getItem(storageKey);
    await s.importProgress('{invalid-json');
    assert.equal(s.w.localStorage.getItem(storageKey),before);
    assert.ok(s.q('#notice').textContent.includes('JSON'));
    await s.importProgress({...s.state(),answers:{unknown_question:'不能覆寫'}});
    assert.equal(s.w.localStorage.getItem(storageKey),before);
    assert.ok(s.q('#notice').textContent.includes('未知題目'));
    await s.importProgress({...s.state(),quizzes:{[quiz.id]:true}});
    assert.equal(s.w.localStorage.getItem(storageKey),before);
    assert.deepEqual(s.errors,[]);
  } finally {s.dom.window.close();}
});

test('blocked local storage reports failure and still permits a usable download',async()=>{
  const s=workspace('#overview',null,true);
  try {
    assert.ok(s.q('#save-status').classList.contains('save-error'));
    const stage=s.data.stages[0],qid=stage.prompts['1'][0].id;
    s.navigate('#assignment/'+stage.id);s.input(`[data-answer="${qid}"]`,'儲存失敗時仍可匯出');
    const exported=await s.download();
    assert.equal(exported.answers[qid],'儲存失敗時仍可匯出');
    assert.ok(s.q('#save-status').classList.contains('save-error'));
    assert.deepEqual(s.errors,[]);
  } finally {s.dom.window.close();}
});

test('unreadable older records are preserved before the first replacement autosave',()=>{
  const original='{"format":"older-course","answers":{"old-question":"保留這份舊答案"}}';
  const s=workspace('#overview',original);
  try {
    assert.equal(s.w.localStorage.getItem(storageKey),original);
    const stage=s.data.stages[0],qid=stage.prompts['1'][0].id;
    s.navigate('#assignment/'+stage.id);s.input(`[data-answer="${qid}"]`,'新版作答');
    s.w.dispatchEvent(new s.w.Event('pagehide'));
    assert.equal(s.state().answers[qid],'新版作答');
    assert.equal(s.w.localStorage.getItem(storageKey+'.recovery'),original);
  } finally {s.dom.window.close();}
});
