import {poseSnapshot} from './pose-panel.js?v=5.6.0';
import {stepExplanation} from './learning-levels.js?v=5.6.0';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number=(x,d=0)=>Number.isFinite(Number(x))?Number(x).toFixed(d):'—';
const date=x=>new Date(x*1000).toLocaleString('zh-TW');
export function frameObservation(note,index,reviews=[],editable=false){
 const history=reviews.filter(r=>r.note_index===index),last=history.at(-1),media=note.media_snapshot;
 return `<article class="note" data-frame-note="${index}"><h3>觀察 ${index+1} · ${esc(media?.title||note.clip_id)}</h3><p>${number(note.seconds,3)} 秒 · 第 ${number(note.frame)} 格 · 水平 ${number(note.yaw)}°／垂直 ${number(note.pitch)}°</p><p class="pre">${esc(note.observation)}</p>${note.analysis_snapshot?poseSnapshot(note.analysis_snapshot):note.teaching_step?stepExplanation(note.teaching_step):''}<p class="source">${esc(last?'學員原始觀察（教師回饋另列）':note.review_status)}${media?` · 來源 ${esc((media.proxy_sha256||media.source_sha256||'').slice(0,12)||'未提供雜湊')}`:' · 舊紀錄未包含媒體雜湊，保留原始證據'}</p><p><b>${last?last.decision==='reviewed'?'教師已檢視':'教師建議補充':'待教師回饋'}</b></p>${history.map(r=>`<div class="frame-feedback"><p>${esc(r.teacher)} · ${esc(date(r.created))} · ${r.decision==='reviewed'?'已檢視':'需補充'}</p><p class="pre">${esc(r.feedback)}</p></div>`).join('')}${editable?`<form class="frame-review-form" data-note-index="${index}" data-expected-review="${esc(last?.id||'')}"><label>觀察回饋狀態<select name="decision"><option value="reviewed">已檢視</option><option value="needs_revision">建議補充</option></select></label><label>具體回饋<textarea name="feedback" required minlength="10" maxlength="2000" placeholder="指出觀察證據、資訊缺口及下一步建議"></textarea></label><button type="submit">保存逐格觀察回饋</button><p class="source" role="status" data-frame-feedback-status></p></form>`:''}</article>`;
}
export function frameEvidence(notes=[],reviews=[],editable=false){
 return `<section class="card"><h2>Level 5 · 逐格觀察與教師回饋</h2><p class="source">保留學員原始觀察與每次教師回饋。此為學習回饋，能力核定與正式分數另存。</p>${notes.length?notes.map((n,i)=>frameObservation(n,i,reviews,editable)).join(''):'<p>尚無逐格觀察紀錄。</p>'}</section>`;
}

export function learningNotesEvidence(notes=[]){return `<section class="card"><h2>Level 1–5 教案學習紀錄</h2><p class="source">各級判讀與教材版本分別保存；不自動改寫正式分數。</p>${notes.length?notes.map(n=>`<article class="note"><h3>Level ${n.lesson_snapshot?.level||'—'} · ${esc(n.lesson_snapshot?.title||n.lesson_id)}</h3><p>${esc(n.reflection)}</p><p class="source">${esc(date(n.created))} · ${esc(n.curriculum_version)}</p></article>`).join(''):'<p>尚未保存各級教案的學習判讀。</p>'}</section>`;}
