import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {setTimeout as pause} from 'node:timers/promises';
import test from 'node:test';
import {JSDOM, VirtualConsole} from 'jsdom';

const base=process.env.GRAPHICS_TEST_URL;
assert.ok(base,'Run via tools/check_graphics_ui.py with disposable fixtures');
const source=await readFile(new URL('../../frontend/graphics/app.js',import.meta.url),'utf8');
async function until(predicate){for(let i=0;i<150;i++){if(predicate())return;await pause(20);}throw new Error('DOM action did not reach expected state');}
async function workspace(username){
  const errors=[];const console=new VirtualConsole();console.on('jsdomError',e=>errors.push(e.message));
  const dom=new JSDOM('<div id="app"></div><div id="notice"></div>',{url:base,runScripts:'outside-only',virtualConsole:console});
  const w=dom.window;let cookie='';w.confirm=()=>true;
  async function request(path,options={}){
    let body=options.body;
    if(body instanceof w.Blob)body=await new Promise((resolve,reject)=>{const reader=new w.FileReader();reader.onload=()=>resolve(Buffer.from(reader.result));reader.onerror=reject;reader.readAsArrayBuffer(body);});
    const r=await fetch(new URL(path,base),{...options,body,headers:{...options.headers,...(cookie?{Cookie:cookie}:{})}});
    const setCookie=r.headers.get('set-cookie');if(setCookie)cookie=setCookie.split(';')[0];return r;
  }
  w.fetch=request;
  await w.eval(`(async()=>{${source}\n})()`);
  const q=s=>w.document.querySelector(s);
  function fill(selector,value){const e=q(selector);assert.ok(e,selector);e.value=value;e.dispatchEvent(new w.Event('input',{bubbles:true}));}
  function click(selector){const e=q(selector);assert.ok(e,selector);e.click();}
  function submit(selector){const form=q(selector);assert.ok(form,selector);const button=form.querySelector('button[type="submit"]');form.dispatchEvent(new w.SubmitEvent('submit',{bubbles:true,cancelable:true,submitter:button}));}
  fill('#username',username);fill('#password','Unit-test-graphics-1234');submit('#login-form');
  await until(()=>q('.sidebar'));
  return {dom,w,q,fill,click,submit,request,errors};
}

test('student completes real six-stage API flow through DOM handlers and reads teacher feedback',async()=>{
  const s=await workspace('ui-student');
  try{
    assert.equal(s.w.document.querySelectorAll('.task').length,3);
    s.click('[data-action="choose"]');await until(()=>s.q('#start-form'));
    const atStep=n=>s.q('.step.active')?.textContent.startsWith(n+'.');
    const fillResponses=text=>{for(const e of s.w.document.querySelectorAll('#work-form textarea'))s.fill('#'+e.id,text);};
    s.fill('#start-team','1');s.submit('#start-form');await until(()=>atStep(1));
    assert.equal(s.w.document.querySelectorAll('#work-form textarea').length,2);
    fillResponses('測試：希望理解尺寸依存');s.q('input[name="answer"][value="1"]').checked=true;
    s.submit('#work-form');await until(()=>atStep(2));
    fillResponses('<img src=x onerror=alert(1)>基準、對稱與約束的具體說明');
    s.fill('#hint-question','尺寸變更後孔位為什麼偏移？');s.submit('#hint-form');await until(()=>s.q('#hint-answer small'));
    assert.match(s.q('#hint-answer').textContent,/規則式/);
    s.submit('#work-form');await until(()=>atStep(3));
    fillResponses('先預測尺寸與基準關係，再於CATIA操作檢核。');
    const upload=s.q('#artifact');Object.defineProperty(upload,'files',{configurable:true,value:[new s.w.File(['ISO-10303-21; test fixture'],'ui-model.step')]});
    s.click('[data-action="upload"]');await until(()=>s.q('.evidence-list a'));
    assert.equal(s.q('#work-form textarea').value,'先預測尺寸與基準關係，再於CATIA操作檢核。');
    s.submit('#work-form');await until(()=>atStep(4));
    fillResponses('本次同儕互換與AI未使用之測試紀錄');
    s.fill('#ai_use','not_used');s.submit('#work-form');await until(()=>atStep(5));
    assert.equal(s.q('#hint-form'),null);
    fillResponses('以新零件基準與約束依存驗證，不只看外觀');s.q('input[name="answer"][value="1"]').checked=true;
    s.submit('#work-form');await until(()=>atStep(6));
    fillResponses('測試反思：先預測、後操作，用尺寸變更證據解釋。');
    s.submit('#work-form');await until(()=>!s.q('#work-form'));
    assert.equal(s.q('img'),null,'submitted user text must not become HTML');
    const rows=await (await s.request('/api/trainings')).json();const tid=rows[0].id;
    const teacher=await workspace('ui-teacher');
    try{
      teacher.click(`[data-action="open"][data-id="${tid}"]`);await until(()=>teacher.q('#review-form'));
      teacher.fill('#review-concept','3');teacher.fill('#review-evidence','依個人作答與模型證據做測試覆核');teacher.fill('#review-next','請進行不同尺寸之新案例驗證');teacher.submit('#review-form');
      await until(()=>teacher.w.document.body.textContent.includes('教師覆核紀錄'));
    }finally{teacher.dom.window.close();}
    s.click('[data-action="home"]');await until(()=>s.q('.records'));
    s.click(`[data-action="open"][data-id="${tid}"]`);await until(()=>s.w.document.body.textContent.includes('教師覆核紀錄'));
    assert.match(s.w.document.body.textContent,/請進行不同尺寸之新案例驗證/);
    const report=await(await s.request(`/api/trainings/${tid}/export`)).json();
    assert.equal(report.reviews.length,1);assert.equal(report.data.practice.transfer,1);
    assert.deepEqual(s.errors,[]);
  }finally{s.dom.window.close();}
});

test('teacher authoring form publishes a new task with hidden answer keys',async()=>{
  const t=await workspace('ui-teacher');
  try{
    t.click('[data-action="lessons"]');await until(()=>t.q('#lesson-form'));
    const fields={title:'DOM測試：參數化零件教案',weeks:'3–4',summary:'教學測試摘要：記錄對稱孔位與尺寸依存',brief:'教學條件：以自編零件練習基準、約束與尺寸變更',goals:'解釋對稱依存\n完成變更測試',perturbation:'改變長度並比較對稱孔位的更新結果'};
    for(const [name,value] of Object.entries(fields))t.fill(`[name="${name}"]`,value);
    for(const prefix of ['pre','transfer']){t.fill(`#${prefix}-question`,'是否需要驗證尺寸變更後的更新結果？');t.fill(`#${prefix}-options`,'需要\n不需要');}
    const form=t.q('#lesson-form');form.dispatchEvent(new t.w.SubmitEvent('submit',{bubbles:true,cancelable:true,submitter:form.querySelector('button[value="publish"]')}));
    await until(()=>t.w.document.body.textContent.includes('發布版本1'));
    const catalog=await(await t.request('/api/catalog')).json();const task=catalog.tasks.find(x=>x.title===fields.title);
    assert.ok(task);assert.equal(task.pre,undefined);assert.equal(task.transfer,undefined);
    assert.deepEqual(t.errors,[]);
  }finally{t.dom.window.close();}
});

test('all three CATIA tasks expose concrete specifications and preserve numbered response drafts',async()=>{
  const s=await workspace('ui-peer');
  try{
    const catalog=await(await s.request('/api/catalog')).json();
    const tasks=catalog.tasks.filter(task=>Array.isArray(task.parameters)&&task.parameters.length);
    assert.equal(tasks.length,3,'the three built-in CATIA tasks have explicit dimensional specifications');
    for(const task of tasks){
      s.click(`[data-action="choose"][data-task="${task.id}"]`);
      await until(()=>s.q('#start-form'));
      assert.equal(s.q('.spec-table tbody').rows.length,task.parameters.length);
      for(const name of task.workbenches)assert.ok(s.q('.task-spec').textContent.includes(name));
      for(const deliverable of task.deliverables)assert.ok(s.q('.task-spec').textContent.includes(deliverable));
      s.submit('#start-form');
      await until(()=>s.q('.step.active')?.textContent.startsWith('1.'));
      const tid=s.q('.page-head .kicker').textContent.match(/TRAINING (\d+)/)?.[1];
      assert.ok(tid,'training id is visible in the workspace');
      const work=await(await s.request(`/api/trainings/${tid}`)).json();
      assert.equal(work.task_id,task.id);
      assert.equal(work.step,1);
      const fields=[...s.w.document.querySelectorAll('#work-form textarea')];
      assert.equal(fields.length,2,'each opening step asks two concrete written questions');
      const expected={};
      for(const [index,field] of fields.entries()){
        const definition=work.fields.find(([id])=>id===field.id);
        assert.ok(definition,'the response control belongs to the active snapshot');
        assert.ok(field.labels[0].textContent.includes(definition[1]));
        assert.ok(field.labels[0].textContent.includes(`題目 ${index+1}`));
        assert.ok(field.placeholder.trim().length>0,'a concrete response hint is visible');
        assert.equal(field.placeholder,work.response_hints[field.id]);
        assert.equal(s.q('#'+field.getAttribute('aria-describedby')).textContent,field.placeholder);
        expected[field.id]=`${task.title}：第${index+1}題，先依尺寸、基準與CATIA操作提出具體預測。`;
        s.fill('#'+field.id,expected[field.id]);
      }
      s.click('[data-action="save"]');
      await until(()=>s.q('#save-state')?.textContent.includes(`版本 ${work.revision+1} ·`));
      const saved=await(await s.request(`/api/trainings/${tid}`)).json();
      assert.equal(saved.step,1,'saving a draft does not advance the assessment');
      for(const [id,value] of Object.entries(expected)){
        assert.equal(saved.data['1'][id],value,'the API persisted the submitted draft');
        assert.equal(s.q('#'+id).value,value,'the saved draft remains in the response control');
      }
      s.click('[data-action="home"]');
      await until(()=>s.q('.grid .task'));
    }
    assert.deepEqual(s.errors,[]);
  }finally{s.dom.window.close();}
});
