import {competencyPanel} from '/static/v5.js?v=5.6.1-r2';
let env, accounts=[],accountPolicy={minimum:4,maximum:6};
export function configureStage1(dependencies){env=dependencies;}
const roleNames={admin:'管理員',student:'學員',teacher:'教師'};
const date=t=>new Date(t*1000).toLocaleString();
export async function adminOverview(){
  const {api,cleanup,shell,heading,esc}=env;cleanup();
  const [users,cat,settings]=await Promise.all([api('/api/admin/users'),api('/api/catalog'),api('/api/admin/settings')]);accounts=users;accountPolicy=settings.password_policy;
  shell(heading('管理員工作台','建立學員與教師帳號，檢視 12 職種題庫及教材建置狀態。')+`
    <p><a class="button secondary" href="/static/admin-settings.html">密碼長度、管理員密碼與寄件設定</a></p><div class="grid3"><div class="card stat">${env.icon('people',23)}<small>階段一開放職種</small><strong>${cat.combinations.length}<small> 職種</small></strong></div><div class="card stat">${env.icon('book',23)}<small>肌少症既有教案</small><strong>${cat.combinations.filter(c=>c.training_available).length}<small> 職種</small></strong></div><div class="card stat">${env.icon('shield',23)}<small>帳號數</small><strong>${users.length}</strong></div></div>
    <div class="card" id="account-editor"><h2>建立學員／教師帳號</h2><form id="account-create-form"><div class="grid2">
    <label>帳號<input name="username" required maxlength="80" autocomplete="off"></label><label>姓名／顯示名稱<input name="display_name" required maxlength="80"></label>
    <label>身分<select name="role"><option value="student">學員</option><option value="teacher">教師</option></select></label><label>初始密碼（${accountPolicy.minimum}至${accountPolicy.maximum}碼）<input name="password" type="password" required minlength="${accountPolicy.minimum}" maxlength="${accountPolicy.maximum}" autocomplete="new-password"></label></div><div class="actions"><button type="submit">建立帳號</button></div></form></div>
    <div class="card scrolltable"><h2>帳號管理</h2><table><thead><tr><th>帳號</th><th>姓名</th><th>身分</th><th>狀態</th><th></th></tr></thead><tbody>${users.map(u=>`<tr><td>${esc(u.username)}</td><td>${esc(u.display_name)}</td><td>${roleNames[u.role]}</td><td>${u.enabled?'啟用':'停用'}</td><td>${u.role==='admin'?'<small>系統管理員</small>':`<button class="secondary" data-action="admin-edit" data-uid="${u.id}">編輯／重設密碼</button>`}</td></tr>`).join('')}</tbody></table></div>
    <div class="card"><div class="heading"><h2>12 職種與肌少症內容</h2><button data-action="admin-preview">預覽職種 × Level 自評</button></div><p class="muted">12 職種皆可進行階段一自評。既有 5 職種接續教案；其餘 7 職種保存自評結果，後續教案待建置。</p><div class="scrolltable"><table><thead><tr><th>職種</th><th>階段一</th><th>後續教案</th></tr></thead><tbody>${cat.combinations.map(c=>`<tr><td>${esc(c.profession_label)} <small>${c.profession}</small></td><td>Level 1–5 分層題組<br><small>平台草稿，待職類審核</small></td><td>${esc(c.content_status)}<br><small>${c.case_count} 個適用案例</small></td></tr>`).join('')}</tbody></table></div></div>`);
}
function editAccount(uid){
  const {esc}=env,u=accounts.find(u=>u.id===uid);if(!u||u.role==='admin')return;
  document.querySelector('#account-editor').innerHTML=`<h2>編輯帳號：${esc(u.username)}</h2><form id="account-update-form" data-uid="${uid}"><div class="grid2"><label>姓名<input name="display_name" value="${esc(u.display_name)}" maxlength="80" required></label><label>身分<select name="role"><option value="student" ${u.role==='student'?'selected':''}>學員</option><option value="teacher" ${u.role==='teacher'?'selected':''}>教師</option></select></label><label>狀態<select name="enabled"><option value="1" ${u.enabled?'selected':''}>啟用</option><option value="0" ${!u.enabled?'selected':''}>停用</option></select></label><label>新密碼（留空保留原密碼）<input name="password" type="password" minlength="${accountPolicy.minimum}" maxlength="${accountPolicy.maximum}" autocomplete="new-password"></label></div><p class="muted">保存後，此帳號須重新登入；學習紀錄繼續保留。</p><div class="actions"><button type="button" class="secondary" data-action="admin-cancel">取消</button><button type="submit">保存帳號設定</button></div></form>`;
  document.querySelector('#account-editor').scrollIntoView({behavior:'smooth'});
}
export async function adminPreview(){
  const {api,cleanup,shell,heading,esc}=env;cleanup();const cat=await api('/api/catalog');
  shell(heading('階段一題組預覽','切換職種及 Level 比較實際題目；預覽不建立學員紀錄或更改訓練等級。')+`<div class="card"><form id="question-preview-form"><div class="grid2"><label>職種<select name="profession">${cat.combinations.map(c=>`<option value="${c.profession}">${esc(c.profession_label)} ${c.profession}</option>`).join('')}</select></label><label>Level<select name="level">${[1,2,3,4,5].map(n=>`<option value="${n}">Level ${n}</option>`).join('')}</select></label></div><div class="actions"><button type="submit">載入題組</button></div></form></div><div id="question-preview-result"><div class="note">請選擇職種及 Level 後載入題組。</div></div>`);
}
export function assessmentTable(rows,faculty=false){
  const {esc,labels}=env;
  return `<div class="card scrolltable"><h2>階段一自評紀錄</h2><table><thead><tr>${faculty?'<th>學員</th>':''}<th>職種</th><th>Level</th><th>狀態</th><th>建立時間</th><th></th></tr></thead><tbody>${rows.map(a=>`<tr>${faculty?`<td>${esc(a.display_name)}<br><small>${esc(a.username)}</small></td>`:''}<td>${esc(labels[a.profession])}</td><td>${a.level}</td><td>${a.completed?'已完成':'草稿'}</td><td>${date(a.created)}</td><td><button class="secondary" data-action="assessment-detail" data-aid="${a.id}">查看自評</button></td></tr>`).join('')}</tbody></table>${!rows.length?'<p class="empty">尚無自評紀錄</p>':''}</div>`;
}
export async function assessmentDetail(aid){
  const {api,state,cleanup,shell,heading,esc,labels}=env;cleanup();state.session=null;
  const teacher=state.user.role==='teacher';const a=await api(`/api/${teacher?'teacher/':''}assessments/${aid}`),s=a.snapshot;
  shell(heading(a.completed?'階段一自評已完成':'階段一自評草稿',`${teacher?a.display_name+' · ':''}${labels[a.profession]} · Level ${a.level}`,`<span class="badge">${a.completed?'結果已保存':'尚未提交'}</span>`)+`
    <div class="note">${a.completed?'自評分流決定案例難度；累積使用與正確性獨立解鎖教案資訊，教師正式核定另存。':'尚未提交的作答以草稿保存。'}${s.training_available===false?'<br>此職種肌少症後續教案待建置，目前完成範圍為階段一。':''}</div>
    ${a.completed?`<div class="grid3"><div class="card stat"><small>本次自評分數</small><strong>${a.scores.summary?.self_mean??'—'}<small> / 100</small></strong></div><div class="card stat"><small>自評分流</small><strong>Level ${a.scores.level_result?.self_level??'歷史版本'}</strong></div><div class="card stat"><small>目前累積學習Level</small><strong>${a.current_learning_level??'歷史版本未分流'}</strong></div></div>`:''}<div class="card competency-card"><div class="section-title"><span class="section-icon">${env.icon('chart',22)}</span><div><h2>職種核心指標自陳表現</h2><p class="muted">看見當下的自陳表現，找到下一步練習方向。</p></div></div><div class="competency-layout">${a.completed?competencyPanel(a.scores):''}<div class="competency-bars">${Object.entries(a.scores.self_dimensions||{}).map(([d,v])=>`<div class="dimbar"><span>${esc(env.dims[d]||d)}</span><progress value="${v}" max="100"></progress><b>${v/20}/5</b></div>`).join('')||'<p>提交後呈現結果。</p>'}<p class="source">1–5 自陳量尺；不是臨床能力認證或客觀測驗總分。</p></div>${(a.scores.calibration||[]).length?`<div class="card"><h2>自評與客觀題比對</h2>${a.scores.calibration.map(r=>`<div class="dimbar"><span>${esc(env.dims[r.dimension]||r.dimension)}</span><small>自評 ${r.self} · 客觀 ${r.objective}</small><b>${r.flag==='overconfident'?'自評可能高估':r.flag==='underconfident'?'自評較低':'大致一致'}</b></div>`).join('')}<p class="source">客觀分只計自動評分的單選題，簡答待教師評閱；比對結果用於安排學習，不是能力認證。</p></div>`:''}</div></div>
    <div class="card"><h2>本次題目與作答</h2><p class="source">${esc(s.form_title)}<br>${esc(s.form_version)} · ${esc(s.source_file)}<br>參照：${esc(s.reference_source_file||s.source_file)}<br>${esc(s.source_status)}<br>快照 ${esc(s.content_hash)}</p>${s.items.map(q=>`<div class="question"><small>${esc(q.dimension_name)} · ${esc(q.item_id)}</small><p>${esc(q.prompt)}</p><b>自評 ${a.answers.answers?.[q.item_id]??'未填'} / 5</b></div>`).join('')}</div>
    <div class="card"><h2>客觀前測另存</h2><p>${esc(s.objective_status||'既有前測題本')}</p>${s.objectives.map(q=>`<div class="question"><p>${esc(q.prompt)}</p><p>作答：${esc(a.answers.objective_answers?.[q.item_id]||'未填')}</p><small>${(a.item_reviews||[]).some(r=>r.item_id===q.item_id)?'教師已評閱（原始自動計分紀錄另存）':a.scores.objective_records?.find(r=>r.item_id===q.item_id)?.status==='pending_teacher'?'開放題待教師評閱':'客觀題另行計分'}</small>${(a.item_reviews||[]).filter(r=>r.item_id===q.item_id).map(r=>`<p class="note">教師 ${esc(r.teacher)}：${r.score}/${r.max_score} 分・${esc(r.note)}</p>`).join('')}${teacher?`<p class="source">參考答案／規準：${esc(q.answer||JSON.stringify(q.rubric||q.expected_keywords||''))}</p>${q.item_type!=='single_choice'&&a.completed?`<form class="item-review-form" data-aid="${a.id}" data-item="${esc(q.item_id)}"><input type="hidden" name="expected_review_id" value="${(a.item_reviews||[]).filter(r=>r.item_id===q.item_id).at(-1)?.id||0}"><label>教師評閱（0–${q.max_score} 分）<select name="score">${Array.from({length:q.max_score+1},(_,i)=>`<option value="${i}">${i} 分</option>`).join('')}</select></label><label>評分依據與回饋<textarea name="note" required minlength="5" maxlength="2000"></textarea></label><button>保存開放題評閱</button></form>`:''}`:''}</div>`).join('')}</div>
    <div class="actions"><button data-action="home">${teacher?'回教師總覽':'回職種首頁'}</button></div>`,teacher?0:1);
}
export async function handleStage1Submit(form){
  const {api,toast,esc}=env,f=new FormData(form);
  if(form.classList.contains('item-review-form')){await api(`/api/teacher/assessments/${form.dataset.aid}/review`,'POST',{item_id:form.dataset.item,score:Number(f.get('score')),note:f.get('note'),expected_review_id:Number(f.get('expected_review_id'))});toast('教師評閱已保存，原始作答與等級不變');await assessmentDetail(Number(form.dataset.aid));return true;}
  if(form.id==='account-create-form'){
    await api('/api/admin/users','POST',Object.fromEntries(f));toast('帳號已建立');await adminOverview();return true;
  }
  if(form.id==='account-update-form'){
    const body={display_name:f.get('display_name'),role:f.get('role'),enabled:f.get('enabled')==='1'};
    if(f.get('password'))body.password=f.get('password');
    await api('/api/admin/users/'+form.dataset.uid,'PATCH',body);toast('帳號設定已保存');await adminOverview();return true;
  }
  if(form.id==='question-preview-form'){
    const s=await api(`/api/admin/question-preview?profession=${encodeURIComponent(f.get('profession'))}&level=${f.get('level')}`);
    document.querySelector('#question-preview-result').innerHTML=`<div class="card"><h2>${esc(s.form_title)}</h2><p>${esc(s.context)}</p><p class="source">${esc(s.form_version)} · ${esc(s.source_status)}</p>${s.items.map(q=>`<div class="question"><small>${esc(q.dimension_name)} · ${esc(q.item_id)}</small><p>${esc(q.prompt)}</p></div>`).join('')}<div class="note">肌少症五職種依上傳題庫各職種設定題數抽取，其他職種抽取六構面題組；下次登入優先避開上一輪題目。有限題庫輪替仍可能在後續登入重遇較早題目。</div></div>`;return true;
  }
  return false;
}
export async function handleStage1Action(action,b){
  if(action==='admin-edit')editAccount(Number(b.dataset.uid));
  if(action==='admin-preview')await adminPreview();
  if(action==='admin-cancel')await adminOverview();
  if(action==='assessment-detail')await assessmentDetail(Number(b.dataset.aid));
}
