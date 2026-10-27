'use strict';
(() => {
  const data = window.CATIA_LEARNING_DATA;
  const root = document.querySelector('#main');
  if (!data || !Array.isArray(data.stages) || !Array.isArray(data.lessons)) {
    root.innerHTML = '<section class="container"><h1>教材尚未載入</h1><p>請重新整理頁面。若仍無法載入，請向老師提供這個網址。</p></section>';
    return;
  }
  const STORAGE_KEY = 'catia-public-learning-v1';
  const MAX_IMPORT = 2 * 1024 * 1024;
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const stages = new Map(data.stages.map(stage => [stage.id, stage]));
  const lessons = new Map(data.lessons.map(lesson => [lesson.id, lesson]));
  const questions = new Map();
  const quizQuestions = new Map();
  const checkKeys = new Set();
  for (const stage of data.stages) {
    for (const prompts of Object.values(stage.prompts || {})) for (const question of prompts) questions.set(question.id, question);
    for (const quiz of stage.quizzes || []) quizQuestions.set(quiz.id, quiz);
  }
  for (const lesson of data.lessons) {
    lesson.steps.forEach((_, index) => checkKeys.add(`${lesson.id}::${index}`));
    for (const quiz of lesson.quiz || []) quizQuestions.set(quiz.id, quiz);
  }
  const blank = () => ({format:'catia-learning-progress', schema_version:1, course_version:data.version, learner:'', answers:{}, checks:{}, quizzes:{}, completed:{}, updated_at:null});
  const isRecord = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  function validateProgress(value) {
    if (!isRecord(value) || value.format !== 'catia-learning-progress' || value.schema_version !== 1) throw new Error('這不是支援的 CATIA 學習紀錄檔。');
    if (typeof value.course_version !== 'string' || value.course_version.length > 100) throw new Error('教材版本欄位不正確。');
    if (typeof value.learner !== 'string' || value.learner.length > 80) throw new Error('姓名／學號欄位不得超過80字。');
    const clean = blank();
    clean.learner = value.learner;
    for (const name of ['answers','checks','quizzes','completed']) if (!isRecord(value[name])) throw new Error('學習紀錄缺少必要欄位。');
    for (const [id, answer] of Object.entries(value.answers)) {
      if (!questions.has(id) || typeof answer !== 'string' || answer.length > 6000) throw new Error('作答包含未知題目或超過6000字的內容。');
      clean.answers[id] = answer;
    }
    for (const [id, checked] of Object.entries(value.checks)) {
      if (!checkKeys.has(id) || typeof checked !== 'boolean') throw new Error('實作步驟紀錄不符目前教材。');
      clean.checks[id] = checked;
    }
    for (const [id, selected] of Object.entries(value.quizzes)) {
      const quiz = quizQuestions.get(id);
      if (!quiz || !Number.isInteger(selected) || selected < 0 || selected >= quiz.options.length) throw new Error('練習選項不正確。');
      clean.quizzes[id] = selected;
    }
    for (const [id, completed] of Object.entries(value.completed)) {
      if (!lessons.has(id) || typeof completed !== 'boolean') throw new Error('課程進度不符目前教材。');
      clean.completed[id] = completed;
    }
    clean.updated_at = typeof value.updated_at === 'string' && value.updated_at.length < 100 ? value.updated_at : null;
    return clean;
  }
  let progress = blank();
  let unreadableRecord = null;
  let storageError = false;
  let unsavedChanges = false;
  let search = '';
  let stageFilter = 'all';
  let saveTimer;
  let toastTimer;
  function toast(message, error = false) {
    const notice = document.querySelector('#notice');
    notice.textContent = message;
    notice.className = error ? 'visible error' : 'visible';
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {notice.className = '';}, 6500);
  }
  function setSaveStatus(message, failed = false) {
    const status = document.querySelector('#save-status');
    status.textContent = message;
    status.classList.toggle('save-error', failed);
  }
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {progress = validateProgress(JSON.parse(saved));}
      catch(error) {unreadableRecord = saved; throw error;}
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(progress));
    setSaveStatus(progress.updated_at ? '已載入這台裝置的紀錄' : '可在此裝置保存');
  } catch {
    storageError = true;
    setSaveStatus('無法保存；請匯出備份', true);
    toast('瀏覽器無法讀取或寫入學習紀錄。本次內容仍可使用，離開前請匯出備份；原有儲存內容未被刪除。', true);
  }
  function persist() {
    clearTimeout(saveTimer);
    progress.updated_at = new Date().toISOString();
    try {
      if (unreadableRecord !== null) {
        const baseKey = `${STORAGE_KEY}.recovery`;
        const previous = localStorage.getItem(baseKey);
        const backupKey = previous === null || previous === unreadableRecord ? baseKey : `${baseKey}.${Date.now()}`;
        localStorage.setItem(backupKey, unreadableRecord);
        unreadableRecord = null;
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(progress));
      storageError = false;
      unsavedChanges = false;
      setSaveStatus('已儲存在此瀏覽器');
      return true;
    } catch {
      storageError = true;
      unsavedChanges = true;
      setSaveStatus('保存失敗；請立即匯出', true);
      toast('瀏覽器儲存空間不足或禁止儲存。內容暫留本頁，請立即匯出學習紀錄。', true);
      return false;
    }
  }
  function queueSave() {
    clearTimeout(saveTimer);
    unsavedChanges = true;
    setSaveStatus('正在儲存…');
    saveTimer = setTimeout(persist, 350);
  }
  const doneLessons = () => data.lessons.filter(lesson => progress.completed[lesson.id]).length;
  const answered = stage => Object.values(stage ? stage.prompts : Object.fromEntries(data.stages.flatMap(s => Object.entries(s.prompts).map(([key, value]) => [`${s.id}:${key}`, value])))).flat().filter(question => (progress.answers[question.id] || '').trim()).length;
  function list(items, ordered = false) {
    const tag = ordered ? 'ol' : 'ul';
    return `<${tag}>${items.map(item => `<li>${escape(item)}</li>`).join('')}</${tag}>`;
  }
  const stageName = id => stages.get(id)?.title || id;
  function diagram(index = 0) {
    const common = 'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"';
    const art = [
      '<path d="M48 126l101-54 112 56-103 55zM48 126v20l110 57 103-56v-19M158 183v20M149 72V34l112 56v38M149 34l-18 10v39"/><ellipse cx="109" cy="127" rx="13" ry="7"/><ellipse cx="192" cy="139" rx="13" ry="7"/><ellipse cx="202" cy="86" rx="9" ry="14"/><path d="M63 177l24 13m-16-1l-8-12 15 1M273 145v-42m-5 7l5-7 5 7" stroke-dasharray="4 4"/>',
      '<path d="M35 128l154-80 83 43-152 81zM35 128v20l85 44 152-80V91M120 172v20M48 121l75 39 137-72M55 118v-25l72 37v25M55 93l132-67 72 37v25M187 26v22M127 130l132-67"/><path d="M128 101l53-28 43 23-52 28zM128 101v34l44 23 52-29V96M172 124v34" stroke="#e89569" stroke-width="2"/><path d="M42 188l68 35m-12-12l12 12-15-1"/>',
      '<path d="M39 145l135-70 101 52-134 71zM39 145v15l102 53 134-71v-15M141 198v15M78 129l82-43 67 35-82 43zM78 129v15l67 35 82-43v-15M145 164v15"/><ellipse cx="125" cy="105" rx="8" ry="4"/><path d="M117 105v47m16-47v47" stroke="#e89569" stroke-width="2"/><ellipse cx="125" cy="152" rx="8" ry="4"/><ellipse cx="189" cy="112" rx="8" ry="4"/><path d="M181 112v47m16-47v47" stroke="#e89569" stroke-width="2"/><ellipse cx="189" cy="159" rx="8" ry="4"/><path d="M86 64l85-45 54 28m-129 8l-10 9 15-1m113-22l11 6-16 1" stroke-dasharray="4 4"/>',
    ];
    return `<svg class="model-diagram" viewBox="0 0 320 240" role="img" aria-label="${['L 型支架','U 型導軌與滑塊','雙定位銷治具'][index]}概念示意"><g ${common}>${art[index]}</g></svg>`;
  }
  function overview() {
    const count = doneLessons();
    return `<section class="hero"><div class="container hero-grid"><div><p class="eyebrow light">THINK · BUILD · EXPLAIN</p><span class="tag dark">CATIA V5 · 免費學習工作室</span><h1>做得出來，<br>也說得出<span>為什麼。</span></h1><p class="hero-copy">從一張草圖到一份能交接的設計。<br>學會零件建模、組合約束與工程圖，讓每一次操作都有依據。</p><div class="button-row"><a class="button accent" href="#lessons">開始知識與實作 <span aria-hidden="true">→</span></a><a class="button ghost" href="#progress">繼續我的學習</a></div><p class="hero-note">無須登入 · 逐步操作 · 具體題目 · 可匯出作答</p></div><div class="hero-art">${diagram(0)}<span class="drawing-label">SKETCH → FEATURE → DESIGN INTENT</span><span class="art-caption">概念示意，實際尺寸以任務規格為準</span><div class="dimension d1">L = 80 → 100</div><div class="dimension d2">知其然 ／ 知其所以然</div></div></div></section>
    <section class="container intro-section"><div class="section-heading"><div><p class="eyebrow">YOUR LEARNING PATH</p><h2>三個階段，把操作連成能力。</h2></div><p>9堂知識與實作 · 18週學習路線<br>36題任務問答 · 每一步都有驗證</p></div><div class="stage-grid">${data.stages.map((stage, index) => `<article class="stage-card"><div class="card-number">0${index + 1}<span>第 ${escape(stage.weeks)} 週</span></div><div class="stage-art">${diagram(index)}</div><p class="eyebrow">STAGE 0${index + 1}</p><h3>${escape(stage.title)}</h3><p>${escape(stage.summary)}</p><div class="stage-tags">${stage.workbenches.map(workbench => `<span>${escape(workbench)}</span>`).join('')}</div><a class="text-link" href="#assignment/${encodeURIComponent(stage.id)}">查看任務與作答 <span aria-hidden="true">→</span></a></article>`).join('')}</div></section>
    <section class="container"><div class="learning-strip"><div><p class="eyebrow">A SMALL STEP, EVERY TIME</p><h2>先學一個原理，<br>再完成一次可檢查的操作。</h2></div><ol class="process"><li><span>01</span><strong>理解</strong><p>認識基準、特徵與約束</p></li><li><span>02</span><strong>實作</strong><p>在 CATIA 逐步建立模型</p></li><li><span>03</span><strong>驗證</strong><p>量測、變更，再說明理由</p></li></ol></div></section>
    <section class="container section-bottom"><div class="progress-banner"><div><p class="eyebrow">YOUR STUDIO</p><h2>已完成 ${count}／${data.lessons.length} 堂知識課</h2><p>作答 ${answered()}／${questions.size} 題。每次進步，都有紀錄。</p></div><a class="button" href="#lessons">${count ? '繼續學習' : '從第一堂開始'} →</a></div></section>`;
  }
  function lessonCards() {
    const term = search.trim().toLocaleLowerCase();
    const filtered = data.lessons.filter(lesson => (stageFilter === 'all' || lesson.stage_id === stageFilter) && (!term || [lesson.title,...lesson.objectives,...lesson.knowledge.map(k => k.title+' '+k.body)].join(' ').toLocaleLowerCase().includes(term)));
    return filtered.length ? filtered.map((lesson, index) => `<article class="lesson-card"><div class="lesson-meta"><span class="tag">${escape(stageName(lesson.stage_id))}</span><span>${lesson.duration_minutes} 分鐘</span></div><span class="lesson-index">${String(data.lessons.indexOf(lesson)+1).padStart(2,'0')}</span><h2>${escape(lesson.title)}</h2><p>${escape(lesson.objectives[0] || '')}</p><div class="lesson-bottom"><span class="completion ${progress.completed[lesson.id]?'done':''}">${progress.completed[lesson.id]?'✓ 已完成':'○ 尚未完成'}</span><a class="text-link" href="#lesson/${encodeURIComponent(lesson.id)}">進入課程 →</a></div></article>`).join('') : '<p class="empty">找不到符合的課程。請換個關鍵字，或選擇其他階段。</p>';
  }
  function lessonsPage() {
    return `<section class="container page-header"><p class="eyebrow">KNOWLEDGE & HANDS-ON</p><h1>知識與實作</h1><p>每堂課先讀原理，再開啟 CATIA 操作。完成後，用檢核點確認結果。</p><div class="filter-bar"><label class="search-field"><span>搜尋課程</span><input id="lesson-search" type="search" placeholder="搜尋草圖、孔、約束、工程圖…" value="${escape(search)}"></label><label><span>學習階段</span><select id="stage-filter"><option value="all">全部階段</option>${data.stages.map(stage => `<option value="${escape(stage.id)}" ${stageFilter===stage.id?'selected':''}>${escape(stage.title)}</option>`).join('')}</select></label></div><div id="lesson-results" class="lesson-grid">${lessonCards()}</div></section>`;
  }
  function quizHTML(quiz, index) {
    const selected = progress.quizzes[quiz.id];
    const checked = Number.isInteger(selected);
    const correct = selected === quiz.answer;
    return `<fieldset class="practice-question" data-quiz="${escape(quiz.id)}"><legend>練習 ${index + 1}｜${escape(quiz.question)}</legend>${quiz.options.map((option, optionIndex) => `<label class="choice"><input type="radio" name="quiz-${escape(quiz.id)}" data-quiz-id="${escape(quiz.id)}" value="${optionIndex}" ${selected===optionIndex?'checked':''}><span>${escape(option)}</span></label>`).join('')}<div class="quiz-feedback ${checked?(correct?'correct':'retry'):''}" aria-live="polite">${checked?`<strong>${correct?'✓ 判斷正確':'再想一想'}</strong><p>${escape(quiz.explanation)}</p>`:'選擇答案後，查看解釋並回到模型驗證。'}</div></fieldset>`;
  }
  function lessonPage(id) {
    const lesson = lessons.get(id);
    if (!lesson) return notFound();
    const index = data.lessons.indexOf(lesson);
    return `<section class="container page-header"><a class="back-link" href="#lessons">← 知識與實作</a><div class="lesson-hero"><div><p class="eyebrow">LESSON ${String(index+1).padStart(2,'0')} · ${lesson.duration_minutes} MIN</p><h1>${escape(lesson.title)}</h1><p>${escape(stageName(lesson.stage_id))}</p></div><label class="lesson-complete"><input type="checkbox" data-lesson-complete="${escape(lesson.id)}" ${progress.completed[id]?'checked':''}><span>我已完成本課並檢查結果</span></label></div><div class="content-layout"><article class="lesson-content"><section class="content-card"><p class="eyebrow">LEARNING GOALS</p><h2>這堂課，你會學會</h2>${list(lesson.objectives)}</section><section class="content-card"><p class="eyebrow">UNDERSTAND THE WHY</p><h2>先理解，再操作</h2>${lesson.knowledge.map(part => `<div class="knowledge-block"><h3>${escape(part.title)}</h3><p>${escape(part.body)}</p></div>`).join('')}</section><section class="content-card" id="hands-on"><p class="eyebrow">YOUR TURN</p><h2>打開 CATIA，跟著做</h2><p class="muted">勾選表示你已實際操作並核對結果。截圖或模型請自行保存，最後與作答紀錄一起交給老師。</p><ol class="hands-on">${lesson.steps.map((step, stepIndex) => `<li><div class="step-heading"><span class="step-number">${String(stepIndex+1).padStart(2,'0')}</span><h3>${escape(step.title)}</h3><label class="step-check"><input type="checkbox" data-check="${escape(lesson.id)}::${stepIndex}" ${progress.checks[`${lesson.id}::${stepIndex}`]?'checked':''}><span>已操作</span></label></div><p class="step-action">${escape(step.action)}</p><div class="checkpoint"><strong>檢核點</strong><p>${escape(step.checkpoint)}</p></div><p class="evidence"><strong>留下證據：</strong>${escape(step.evidence)}</p></li>`).join('')}</ol></section><section class="content-card"><p class="eyebrow">WHEN THINGS GO WRONG</p><h2>卡住時，先看這裡</h2>${(lesson.pitfalls || []).map(pitfall => `<details class="pitfall"><summary>${escape(pitfall.symptom)}</summary><p><strong>可能原因：</strong>${escape(pitfall.cause)}</p><p><strong>嘗試修正：</strong>${escape(pitfall.fix)}</p></details>`).join('')}</section><section class="content-card"><p class="eyebrow">CHECK YOUR UNDERSTANDING</p><h2>換個問題，確認理解</h2><p class="muted">這裡是自學練習，可重複作答；不會自動提交正式成績。</p>${(lesson.quiz || []).map(quizHTML).join('')}</section><section class="content-card"><h2>延伸閱讀與來源</h2><ul class="source-list">${(lesson.sources || []).map(source => `<li><a href="${escape(safeURL(source.url))}" target="_blank" rel="noreferrer">${escape(source.title)} ↗</a></li>`).join('')}</ul></section><div class="next-lesson">${data.lessons[index+1]?`<a class="button" href="#lesson/${encodeURIComponent(data.lessons[index+1].id)}">下一堂：${escape(data.lessons[index+1].title)} →</a>`:`<a class="button" href="#assignment/${encodeURIComponent(lesson.stage_id)}">進入整合任務作答 →</a>`}</div></article><aside class="lesson-aside"><div class="aside-card"><p class="eyebrow">STAGE TASK</p><h3>${escape(stageName(lesson.stage_id))}</h3><p>把這堂課的原理，放進完整任務中驗證。</p><a class="button secondary" href="#assignment/${encodeURIComponent(lesson.stage_id)}">查看任務與問答 →</a></div><div class="aside-card"><h3>操作的三個習慣</h3><ol><li>修改之前先預測。</li><li>用量測或約束狀態確認。</li><li>寫下檔名與結果，方便重現。</li></ol></div><div class="aside-card subtle"><strong>進度留在這台裝置</strong><p>換電腦前請匯出，並在另一台裝置匯入紀錄。</p><button class="button outline" data-action="export">匯出學習紀錄</button></div></aside></div></section>`;
  }
  function taskSpecs(stage) {
    return `<div class="task-specifications"><details open><summary>尺寸與基準規格</summary><div class="table-scroll"><table><thead><tr><th>項目</th><th>規格</th><th>基準／說明</th></tr></thead><tbody>${stage.parameters.map(p => `<tr><th scope="row">${escape(p.name)}</th><td>${escape(p.value)}</td><td>${escape(p.reference)}</td></tr>`).join('')}</tbody></table></div></details><details><summary>CATIA 操作路線</summary>${list(stage.operation_steps,true)}</details><details><summary>本輪必繳成果</summary>${list(stage.deliverables)}</details><details><summary>完成後逐項檢查</summary>${list(stage.acceptance)}</details></div>`;
  }
  function assignmentPage(id) {
    const stage = stages.get(id);
    if (!stage) return notFound();
    const index = data.stages.indexOf(stage);
    return `<section class="container page-header"><a class="back-link" href="#overview">← 學習地圖</a><div class="assignment-heading"><div><p class="eyebrow">STAGE 0${index+1} · 第 ${escape(stage.weeks)} 週</p><h1>${escape(stage.title)}</h1><p>${escape(stage.summary)}</p></div><div class="mini-art">${diagram(index)}</div></div><div class="content-layout"><article><section class="content-card"><h2>這次，你要完成什麼？</h2><p class="task-brief">${escape(stage.brief)}</p><div class="stage-tags">${stage.workbenches.map(w => `<span>${escape(w)}</span>`).join('')}</div>${taskSpecs(stage)}</section><section class="content-card"><p class="eyebrow">THINK IT THROUGH</p><h2>12題，把你的設計說清楚。</h2><p>操作在 CATIA 完成，理由寫在這裡。請依題意提供數值、計算、指令、參照面與證據檔名。輸入後會自動保存。</p><p class="notice-inline">本頁是自學作答紀錄；不會上傳模型或集中收件。完成後請匯出，連同模型與截圖依老師指定方式繳交。</p><div class="task-questions">${Object.entries(stage.prompts).map(([step, prompts]) => `<details class="question-group" ${step==='1'?'open':''}><summary><span class="step-pill">${step}</span>${escape(stage.step_titles?.[Number(step)-1] || `步驟 ${step}`)}<small>${prompts.filter(p => (progress.answers[p.id]||'').trim()).length}／${prompts.length} 已作答</small></summary>${prompts.map((question, qIndex) => `<div class="answer-field"><label for="answer-${escape(question.id)}"><span class="question-number">題目 ${(Number(step)-1)*2+qIndex+1}</span>${escape(question.prompt)}</label><p id="hint-${escape(question.id)}" class="answer-hint">${escape(question.placeholder)}</p><textarea id="answer-${escape(question.id)}" data-answer="${escape(question.id)}" maxlength="6000" aria-describedby="hint-${escape(question.id)}" placeholder="${escape(question.placeholder)}">${escape(progress.answers[question.id]||'')}</textarea></div>`).join('')}</details>`).join('')}</div><div class="button-row section"><button class="button" data-action="export">匯出作答與學習紀錄 ↗</button><a class="button secondary" href="#progress">查看所有紀錄</a><a class="text-link" href="./practice-worksheet.txt" download>下載文字題本 ↓</a></div></section>${stage.quizzes?.length?`<section class="content-card"><p class="eyebrow">CHECK & TRANSFER</p><h2>前測與新情境練習</h2><p class="muted">這些是公開的自學練習，可重複作答並閱讀解釋，供你確認理解。</p>${stage.quizzes.map(quizHTML).join('')}</section>`:''}</article><aside class="lesson-aside"><div class="aside-card"><p class="eyebrow">PREPARE FOR THE TASK</p><h3>先讀相關知識課</h3><ul class="lesson-links">${data.lessons.filter(l => l.stage_id===id).map(l => `<li><a href="#lesson/${encodeURIComponent(l.id)}">${progress.completed[l.id]?'✓':'○'} ${escape(l.title)} →</a></li>`).join('')}</ul></div><div class="aside-card subtle"><h3>好的回答，包含證據</h3><p>寫出「改了哪個特徵、原值與新值、預測與實測、證據檔名」，讓接手的人能重現你的判斷。</p></div></aside></div></section>`;
  }
  function safeURL(value) {
    try {const url = new URL(value);return url.protocol === 'https:' ? url.href : '#';} catch {return '#';}
  }
  function glossaryItems() {
    const term = search.trim().toLocaleLowerCase();
    const filtered = data.glossary.filter(entry => !term || `${entry.term} ${entry.definition}`.toLocaleLowerCase().includes(term));
    return filtered.length ? filtered.map(entry => `<article class="glossary-item"><h2>${escape(entry.term)}</h2><p>${escape(entry.definition)}</p></article>`).join('') : '<p class="empty">沒有符合的指令或概念，請試試其他關鍵字。</p>';
  }
  function glossaryPage() {
    return `<section class="container page-header section-bottom"><p class="eyebrow">TOOLS & CONCEPTS</p><h1>指令字典</h1><p>記住的不只是按鈕名稱，還有什麼時候使用，以及如何檢查結果。</p><label class="search-field glossary-search"><span>搜尋指令與概念</span><input type="search" id="glossary-search" placeholder="搜尋 Pad、自由度、基準…" value="${escape(search)}"></label><div id="glossary-results" class="glossary-grid">${glossaryItems()}</div></section>`;
  }
  function progressPage() {
    const count = doneLessons();
    return `<section class="container page-header section-bottom"><p class="eyebrow">YOUR LEARNING RECORD</p><h1>我的學習與作答</h1><p>進度保存在目前瀏覽器。定期匯出一份備份，也可以把檔案交給老師查看。</p><div class="record-layout"><section class="content-card"><h2>這份紀錄屬於誰？</h2><label for="learner-name">姓名／學號（選填，僅保存在本機與匯出檔）</label><input id="learner-name" type="text" maxlength="80" value="${escape(progress.learner)}" placeholder="例如：王同學／A123456"><div class="record-actions"><button class="button" data-action="export">匯出 JSON 紀錄 ↗</button><button class="button secondary" data-action="import">匯入既有紀錄</button><button class="button outline" data-action="print">列印／另存 PDF</button></div><p class="muted small">匯入時會合併進度；相同題目的作答以匯入檔為準，操作前會請你確認。</p>${storageError?'<p class="notice-inline error-text">目前瀏覽器無法保存，請立即匯出，避免離開後遺失本次輸入。</p>':''}</section><section class="content-card progress-summary"><strong>${count}<span>／${data.lessons.length}</span></strong><h2>堂知識與實作已完成</h2><div class="progress-track"><span style="width:${Math.round(count/data.lessons.length*100)}%"></span></div><p>${answered()}／${questions.size} 題已有作答</p></section></div><div class="section-heading section"><div><p class="eyebrow">STAGE RECORDS</p><h2>三階段作答</h2></div></div><div class="stage-records">${data.stages.map((stage,index) => `<section class="content-card"><div class="stage-record-title"><span class="card-number">0${index+1}</span><div><h2>${escape(stage.title)}</h2><p>${answered(stage)}／12 題已作答</p></div><a class="text-link" href="#assignment/${encodeURIComponent(stage.id)}">繼續作答 →</a></div><div class="record-answers">${Object.entries(stage.prompts).map(([step,prompts]) => `<details><summary>${escape(stage.step_titles?.[Number(step)-1]||`步驟${step}`)}</summary>${prompts.map(question => `<div class="read-answer"><h3>${escape(question.prompt)}</h3><p>${escape(progress.answers[question.id]||'尚未作答')}</p></div>`).join('')}</details>`).join('')}</div></section>`).join('')}</div></section>`;
  }
  function notFound() {return '<section class="container page-header"><h1>找不到這堂課</h1><p>這個連結可能已更新，請回到學習地圖繼續。</p><a class="button" href="#overview">返回學習地圖</a></section>';}
  function render() {
    const parts = location.hash.slice(1).split('/');
    let id = '';
    try {id = decodeURIComponent(parts[1]||'');} catch {}
    const page = parts[0] || 'overview';
    const routes = {overview, lessons:lessonsPage, glossary:glossaryPage, progress:progressPage};
    root.innerHTML = page==='lesson'?lessonPage(id):page==='assignment'?assignmentPage(id):(routes[page]||notFound)();
    for (const item of document.querySelectorAll('[data-nav]')) {
      const selected = item.dataset.nav===page || (page==='lesson'&&item.dataset.nav==='lessons') || (page==='assignment'&&item.dataset.nav==='overview');
      if (selected) item.setAttribute('aria-current','page');else item.removeAttribute('aria-current');
    }
    document.title = `${page==='lesson'?(lessons.get(id)?.title||'課程'):page==='assignment'?(stages.get(id)?.title||'任務'):{overview:'知其然・知其所以然',lessons:'知識與實作',glossary:'指令字典',progress:'我的作答'}[page]||'CATIA'}｜CATIA 學習工作室`;
  }
  function exportProgress() {
    persist();
    const blob = new Blob([JSON.stringify(progress,null,2)],{type:'application/json;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href=url;link.download=`CATIA-學習紀錄-${new Date().toISOString().slice(0,10)}.json`;
    document.body.append(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
    toast('已準備下載學習紀錄。請確認瀏覽器已保存檔案。');
  }
  document.addEventListener('input', event => {
    const target = event.target;
    if (target.matches('[data-answer]') && questions.has(target.dataset.answer)) {
      progress.answers[target.dataset.answer]=target.value.slice(0,6000);queueSave();
      const group = target.closest('.question-group');
      if (group) {const fields=[...group.querySelectorAll('textarea')];group.querySelector('summary small').textContent=`${fields.filter(field=>field.value.trim()).length}／${fields.length} 已作答`;}
    } else if (target.id==='learner-name') {progress.learner=target.value.slice(0,80);queueSave();}
    else if (target.id==='lesson-search') {search=target.value;document.querySelector('#lesson-results').innerHTML=lessonCards();}
    else if (target.id==='glossary-search') {search=target.value;document.querySelector('#glossary-results').innerHTML=glossaryItems();}
  });
  document.addEventListener('change', event => {
    const target = event.target;
    if (target.dataset.check && checkKeys.has(target.dataset.check)) {progress.checks[target.dataset.check]=target.checked;persist();}
    else if (target.dataset.lessonComplete && lessons.has(target.dataset.lessonComplete)) {progress.completed[target.dataset.lessonComplete]=target.checked;persist();}
    else if (target.dataset.quizId && quizQuestions.has(target.dataset.quizId)) {
      const quiz=quizQuestions.get(target.dataset.quizId),selected=Number(target.value);
      if (!Number.isInteger(selected)||selected<0||selected>=quiz.options.length)return;
      progress.quizzes[quiz.id]=selected;persist();
      const feedback=target.closest('fieldset').querySelector('.quiz-feedback');
      feedback.className=`quiz-feedback ${selected===quiz.answer?'correct':'retry'}`;
      feedback.innerHTML=`<strong>${selected===quiz.answer?'✓ 判斷正確':'再想一想'}</strong><p>${escape(quiz.explanation)}</p>`;
    } else if (target.id==='stage-filter') {stageFilter=target.value;document.querySelector('#lesson-results').innerHTML=lessonCards();}
  });
  document.addEventListener('click',event=>{
    if(event.target.closest('.skip-link')){event.preventDefault();root.focus();root.scrollIntoView({block:'start'});return;}
    const button=event.target.closest('[data-action]');if(!button)return;
    if(button.dataset.action==='export')exportProgress();
    if(button.dataset.action==='import')document.querySelector('#import-file').click();
    if(button.dataset.action==='print'){persist();window.print();}
  });
  document.querySelector('#import-file').addEventListener('change',async event=>{
    const file=event.target.files[0];if(!file)return;
    try {
      if(file.size>MAX_IMPORT)throw new Error('匯入檔案上限為2 MB。');
      const incoming=validateProgress(JSON.parse(await file.text()));
      if(!window.confirm('將合併這份學習紀錄；相同題目的作答以匯入檔為準。要繼續嗎？'))return;
      for(const name of ['answers','quizzes'])Object.assign(progress[name],incoming[name]);
      for(const name of ['checks','completed'])for(const [id,value]of Object.entries(incoming[name]))progress[name][id]=Boolean(progress[name][id]||value);
      if(incoming.learner)progress.learner=incoming.learner;
      const saved=persist();render();
      toast(saved?'已合併並保存學習紀錄。':'已在本頁合併，但無法保存；請立即匯出備份。',!saved);
    } catch(error){toast(error instanceof SyntaxError?'檔案不是有效的 JSON，原有紀錄未更動。':error.message,true);}
    finally {event.target.value='';}
  });
  window.addEventListener('hashchange',()=>{if(saveTimer)persist();render();window.scrollTo(0,0);root.focus({preventScroll:true});});
  window.addEventListener('pagehide',()=>{if(saveTimer)persist();});
  window.addEventListener('beforeunload',event=>{if(storageError&&unsavedChanges){event.preventDefault();event.returnValue='';}});
  render();
})();
