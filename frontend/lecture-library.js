const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function lectureModule(library,index){
 const entry=library?.lectures?.[0],module=entry?.modules.find(m=>m.module===index);
 if(!module)return '<p class="note warning">此講師的已發布影片尚未安裝，請選擇對應專業講師，或由管理者同步最新版影片庫。</p>';
 return `<div class="published-lecture"><p><span class="badge">已發布 · 可直接播放</span> ${esc(entry.actor_name)} · ${entry.actor_gender==='male'?'男聲':'女聲'}</p>${entry.guideline_note?`<p class="source">${esc(entry.guideline_note)}</p>`:''}<video class="video" controls playsinline preload="metadata" aria-label="${esc(module.title)}講師影片" src="${esc(module.url)}"></video><p class="source">${esc(entry.lecturer_scope)} · ${Math.round(module.duration)}秒 · 來源 ${esc(entry.source_fingerprint.slice(0,12))}</p><details><summary>文字稿與教學目的</summary><p>${esc(module.transcript)}</p><p>${esc(entry.teaching_purpose)}</p><p class="source">${esc(entry.review_status)}</p></details></div>`;
}

export function lectureModuleCard(module,index,{library,canGenerate,readonly,existing}){
 return `<article class="module"><h3>${index+1}. ${esc(module)} <span class="badge">已解鎖</span></h3><p class="muted">共用教案導讀可直接觀看；當級任務及個人補強以本輪教案文字為準。</p>${lectureModule(library,index)}${existing?`<details><summary>本輪生成版本與歷史影片（保留原始版本）</summary><video class="video" controls playsinline preload="none" src="${esc(existing.url)}"></video>${existing.immersive_url?`<p><a href="${esc(existing.immersive_url)}" target="_blank" rel="noopener">開啟原版3D講師教案 ↗</a></p>`:''}</details>`:''}${canGenerate&&!readonly?`<details><summary>主機本機生成個人化版本</summary><p>此功能由本機主機執行；新版本經教材管理者核對後再發布。</p><button class="secondary" data-action="generate-video" data-module="${index}">產生虛擬講師影片（含語音）</button></details>`:''}${!readonly?`<label class="checkline"><input type="checkbox" name="module-done" value="${index}" required>我已完成本模組影片或案例教材學習</label>`:''}</article>`;
}
