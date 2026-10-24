import {sceneControls,voiceControls} from './immersive-ui.js?v=5.6.0';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function interactionStage(s,i,actors,services,messages){
 const a=actors.interaction,e=i.encounter||{title:'案例會談',task:s.data.case.variant?.role_task||'釐清本教案疑慮與下一步。',state:'active'},entries=i.encounter_plan?.entries||[];
 const last=(s.messages||[]).filter(m=>{const meta=typeof m.metadata==='string'?JSON.parse(m.metadata||'{}'):m.metadata||{};return m.role==='assistant'&&meta.mode!=='peer'&&(!meta.actor||meta.actor.id===a.id);}).at(-1);
 return `<section class="encounter-brief"><div><div class="eyebrow">FACE TO FACE / 情境會談</div><h2>${esc(e.title)}</h2><p>您是${esc(({RT:'醫事放射師',PT:'物理治療師',DT:'營養師',RN:'護理師',MD:'醫師'})[s.profession]||s.profession)}，本次與${esc(a.display_name||a.title)}面對面溝通。</p></div><span class="badge">自評情境難度 Level ${s.level}</span></section>
 <nav class="encounter-partners" aria-label="本輪會談對象">${entries.map(x=>`<button class="${x.target===e.target?'current':'secondary'}" data-action="select-actor" data-purpose="interaction" data-actor="${esc(x.actor_id)}" ${x.target===e.target?'disabled':''}>${esc(x.target==='patient'?'病患／家屬':'物理治療師')} · ${esc(x.title)}${x.state==='closed'?' ✓':''}</button>`).join('')}</nav>
 <div class="encounter-layout" style="scroll-margin-top:95px"><section class="encounter-room"><div class="encounter-name"><b>${esc(a.display_name||a.name)}</b><span id="presence-state">面對面會談 · 準備中</span></div><div id="avatar" class="avatar" role="img" aria-label="three.js立體骨架角色面對面會談"></div><div class="encounter-caption"><span id="speaker-state">${last?'接續上次會談':'您的對話對象'}</span><p id="current-reply" aria-live="polite">${esc(e.state==='closed'?'這場會談已結束。可繼續這場會談或選擇另一位對象。':last?.content||'我在這裡，準備好後可以開始談。')}</p></div></section>
 <section class="card encounter-desk"><h3>本場任務</h3><p>${esc(e.task)}</p><p class="source">依「${esc(s.data.case.title)}」既有資料互動；角色不會因換造型而產生新病歷。</p><div class="note"><b>${esc(i.difficulty.label)}</b><details><summary>本級情境壓力</summary>${esc(i.difficulty.behavior)}</details></div>
 ${voiceControls(s.id,a.id)}<p id="conversation-end" role="status" ${e.state==='closed'?'':'hidden'}>會談已結束；逐字稿已保存。<button type="button" data-action="conversation-reopen" class="secondary">繼續這場會談</button></p>
 <details open><summary>也可輸入文字</summary><form id="chat-form"><label for="chat-text">您的回應</label><textarea id="chat-text" required maxlength="2000" placeholder="像面對面交談一樣，回應對方、詢問或交接。"></textarea><label class="checkline"><input id="speak" type="checkbox" checked>朗讀角色回覆</label><div class="actions"><span id="chat-state" class="muted">準備好後開始溝通</span><button type="submit">送出回應</button></div></form></details></section></div>
 <details class="card encounter-transcript"><summary>會談逐字稿與案例資料</summary><p>${esc(s.data.case.patient)}</p><div id="chatlog" class="chatlog" aria-live="off">${messages}</div><p class="source">逐字稿保留實際角色、模型、教案與會談版本，供教師回饋。</p></details>
 <details class="card"><summary>場景工具與服務設定</summary>${sceneControls(i)}${`<div class="trust"><span id="trust-bar" style="width:${i.trust}%"></span></div><small id="trust-label">情境信任值 ${i.trust} / 100（不是能力分數）</small>`}<div class="scene-actions">${[['identify','確認身分'],['report','查看案例資料'],['safety','檢查情境安全'],['handoff','準備交接']].map(([key,label])=>`<button class="secondary" data-action="scene" data-scene="${key}">${label}</button>`).join('')}</div><div id="scene-detail" class="note">場景操作記錄與臨床能力判斷分別保存。</div><label for="chat-mode">對話服務</label><select id="chat-mode"><option value="ai" ${!services.ollama.ready?'disabled':''}>AI 情境會談</option><option value="scripted" ${!services.ollama.ready?'selected':''}>劇本演練（非 AI）</option>${s.level===5?'<option value="peer">虛擬 Level 2 學員指導練習</option>':''}</select><p class="source">${esc(services.ollama.model)} · ${services.ollama.ready?'本機 AI 可用':'本機 AI 尚未就緒；目前為明示劇本模式'}</p><button class="link" data-action="services">重新檢查服務</button><div id="service-detail"></div><p class="source">人物設定只提供外觀與聲線；本場任務與情緒由教案、等級及會談進展決定。</p></details>`;
}

export function conversationState(result){
 const c=result.conversation||result.metadata?.conversation||{},phase=c.phase||'active';
 return {phase,emotion:c.emotion||'neutral',closed:phase==='closed',label:phase==='closing'?'對方提出收尾；您仍可繼續提問':phase==='closed'?'會談已結束':'承接對話中'};
}

export function encounterEvidence(plan){
 if(!plan?.entries?.length)return '';
 const phase={ready:'尚未開始',active:'互動中',closing:'提出收尾',closed:'學員同意結束'};
 return `<section class="card"><h2>情境會談任務與進展</h2><p class="source">自評難度 Level ${plan.self_level} · ${esc(plan.version)}。以下是模擬會談狀態，不是能力評分或 EPA 授權。</p>${plan.entries.map(e=>`<div class="module"><h3>${esc(e.title)} · ${esc(phase[e.state]||e.state)}</h3><p>${esc(e.task)}</p><p class="source">${e.turns} 輪學員輸入；請依逐字稿觀察疑慮回應、資料界線、回述確認、交接分工與收尾共識。</p></div>`).join('')}</section>`;
}
