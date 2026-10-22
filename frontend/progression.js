export function placementPanel(result,esc,radar){
 const s=result.scores,p=s.level_result||{},summary=s.summary||{};
 return `<div class="grid3">
 <div class="card stat"><small>本次自評分數</small><strong>${summary.self_mean??'—'}<small> / 100</small></strong><p class="source">依本次作答與經驗量尺計算</p></div>
 <div class="card stat"><small>自評分流等級</small><strong>Level ${p.self_level??'—'}</strong><p class="source">決定本輪案例難度與提示支持</p></div>
 <div class="card stat"><small>累積學習等級</small><strong>Level ${p.learning_level??'—'}</strong><p class="source">依練習使用與正確性解鎖更多教材</p></div></div>
 <div class="note"><b>兩個等級獨立計算</b><p>例如：自評 Level 2、累積學習 Level 5，仍使用 Level 2 案例與提示，同時開放已累積解鎖的教案資訊；累積學習不代表能力認證。</p></div>
 <div class="card"><h2>自評分級依據與下一步</h2><p>各職種核心指標評分 × 20 後等權平均；以下為平台試行的自評分流規則。</p>
 <div class="row">${(p.bands||[]).map(b=>`<span class="badge ${b.level===p.self_level?'':'gold'}">${b.min}–${b.max} 分 → Level ${b.level}</span>`).join('')}</div>
 <p>${esc(p.note||'自評分流與教材累積解鎖獨立保存。')}</p>
 ${p.applies_next_round?`<div class="note">既有訓練維持 Level ${p.session_level} 與原教案；本次自評 Level ${p.self_level} 於下一輪套用，避免中途改動評分規準。</div>`:''}
 <p>客觀前測：${summary.objective_auto_percent??'尚無自動評分題'}${summary.objective_auto_percent!=null?' / 100':''}；簡答待評 ${summary.pending_teacher_items??0} 題。</p></div>
 <div class="card"><h2>${s.competency_profile?.label||''}核心指標自評結果</h2>${radar(s.competency_scores||s.self_dimensions||{},'placement',s.competency_profile)}</div>
 <div class="actions">${result.session_id?`<button data-action="assessment-continue" data-session="${result.session_id}">${p.applies_next_round?'接續原訓練':'依自評 Level '+p.self_level+' 進入教案'} →</button>`:'<button data-action="home">完成自評，回職種首頁</button>'}</div>`;
}
export function progressPanel(progress){
 if(!progress)return '';
 return `<div class="card"><h2>本輪教材累積結果與下輪解鎖</h2><div class="grid3"><div class="stat"><small>結算時累積學習等級</small><strong>Level ${progress.learning_level}</strong></div><div class="stat"><small>近期熟練度</small><strong>${progress.mastery??'待累積'}<small> / 100</small></strong></div><div class="stat"><small>累積學習積分</small><strong>${progress.learning_points}</strong></div></div>
 <p>${progress.promoted?'本輪累積達標，教材解鎖等級已提升。':'持續完成達標練習可解鎖更多教材資訊。'}已完成 ${progress.completed_practices} 輪，其中 ${progress.passed_practices} 輪達80分且安全通過。</p><p>${progress.note}</p><p>此等級不改變自評分流或教師正式能力核定。</p>
 ${(progress.next_plan?.paths||[]).map(p=>`<p><span class="badge">${p.unlocked?'已解鎖':'尚未解鎖'}</span> ${p.title} · ${p.requirement}</p>`).join('')}</div>`;
}
export function informationPanel(items,esc){
 if(!items?.length)return '';
 return `<div class="card"><h2>依累積學習等級解鎖的教案資訊</h2><p class="muted">使用與正確性增加可閱讀的資訊；本輪案例難度仍依自評分流。</p>${items.map(i=>`<details class="module" ${i.unlocked?'open':''}><summary><span class="badge">${i.unlocked?'已解鎖':'尚未解鎖'}</span> 累積 Level ${i.level} · ${esc(i.title)}</summary>${i.unlocked?(i.content||[]).map(c=>`<p>${esc(c)}</p>`).join(''):'<p>持續完成安全達標的練習，累積至此等級後開放。</p>'}</details>`).join('')}</div>`;
}
export function clinicalNotes(review,esc){if(!review)return '';return `<details class="card"><summary>教案專業與版本核對</summary><p>${esc(review.status)}</p>${(review.items||[]).map(i=>`<p><b>${esc(i.topic)}</b>：${esc(i.note)} ${i.url?`<a href="${esc(i.url)}" target="_blank" rel="noopener">核對來源 ↗</a>`:''}</p>`).join('')}${(review.general||[]).map(n=>`<p>${esc(n)}</p>`).join('')}</details>`;}
