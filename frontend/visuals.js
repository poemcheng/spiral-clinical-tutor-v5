// Platform artwork and icons. Inspired by the university's colors, not its official emblem.
export const palette={blue:'#234EAE',navy:'#122C59',red:'#D64254',white:'#FFFFFF',paper:'#F4F6FB'};
const paths={
 home:'<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7H9v7H4a1 1 0 0 1-1-1Z"/>',
 arrow:'<path d="M4 12h15m-6-6 6 6-6 6"/>',
 user:'<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
 lock:'<rect x="5" y="10" width="14" height="11" rx="3"/><path d="M8 10V6a4 4 0 0 1 8 0v4m-4 4v3"/>',
 eye:'<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
 shield:'<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><path d="m8 12 3 3 5-6"/>',
 people:'<circle cx="9" cy="8" r="3"/><path d="M2 21v-3a7 7 0 0 1 14 0v3m0-17a3 3 0 0 1 0 6m3 4a6 6 0 0 1 3 5v2"/>',
 book:'<path d="M12 5c-3-2-7-2-10-1v15c4-1 7-1 10 1 3-2 6-2 10-1V4c-3-1-7-1-10 1Zm0 0v15"/><path d="M5 8h3m-3 4h3m8-4h3m-3 4h3"/>',
 clipboard:'<rect x="5" y="4" width="14" height="18" rx="3"/><rect x="9" y="2" width="6" height="4" rx="1"/><path d="m8 12 2 2 5-5m-7 9h8"/>',
 play:'<rect x="2" y="4" width="20" height="16" rx="4"/><path d="m10 8 6 4-6 4Z"/>',
 interaction:'<path d="M15 4h5v5m0-5-6 6M9 20H4v-5m0 5 6-6"/><circle cx="7" cy="7" r="3"/><circle cx="17" cy="17" r="3"/>',
 quiz:'<path d="M14 2H5a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9Z"/><path d="M14 2v7h7M7 13h3m4 0h3M7 17h3m4 0h3"/>',
 report:'<path d="M5 3h10l4 4v14H5Z"/><path d="M14 3v5h5M8 17v-3m4 3v-6m4 6v-4"/>',
 history:'<path d="M3 10a9 9 0 1 1 1 8M3 4v6h6m3-3v5l3 2"/>',
 logout:'<path d="M9 3H4v18h5m5-14 5 5-5 5M8 12h12"/>',
 grid:'<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
 check:'<path d="m5 12 4 4L20 5"/>',
 spark:'<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5ZM20 2v4m-2-2h4"/>',
 chart:'<path d="M3 3v18h18M7 15l4-5 4 3 6-8"/>',
 heart:'<path d="M20 5c-3-3-6-1-8 1-2-2-5-4-8-1s-1 7 8 15C21 12 23 8 20 5Z"/>',
 message:'<path d="M21 12a9 9 0 0 1-9 9H3l2-5a9 9 0 1 1 16-4Z"/><path d="M7 10h10m-10 4h6"/>',
 MD:'<path d="M4 3v6a5 5 0 0 0 10 0V3M2 3h4m6 0h4m-7 11v2a5 5 0 0 0 10 0v-2"/><circle cx="19" cy="11" r="3"/>',
 RN:'<path d="M20 5c-3-3-6-1-8 1-2-2-5-4-8-1s-1 7 8 15C21 12 23 8 20 5Z"/><path d="M5 11h4l2-3 2 7 2-4h4"/>',
 DT:'<path d="M20 3C9 2 3 6 5 13s12 7 15-10Z"/><path d="M3 21 16 8m-6 6v-4m0 4h4"/>',
 PT:'<circle cx="13" cy="4" r="2"/><path d="m7 22 3-7-2-5 4-3 4 4 5 1m-11 3 5 3 2 4M8 10l-4 3"/>',
 OT:'<path d="M7 13V6a2 2 0 0 1 4 0v6-8a2 2 0 0 1 4 0v8-6a2 2 0 0 1 4 0v9c0 5-3 7-7 7-3 0-5-2-7-5l-2-3a2 2 0 0 1 3-2l1 1Z"/>',
 RT:'<path d="M7 3H3v4m14-4h4v4M3 17v4h4m14-4v4h-4"/><rect x="7" y="6" width="10" height="12" rx="2"/><path d="M10 9h4m-4 3h4m-4 3h4"/>',
 RSP:'<path d="M12 3v8m0-3 3 3m-3-3-3 3M9 6C6 8 2 12 3 18c1 4 6 3 6 0V6Zm6 0c3 2 7 6 6 12-1 4-6 3-6 0V6Z"/>',
 RPH:'<path d="m6 18 12-12M4 20a6 6 0 0 1 0-8l8-8a6 6 0 0 1 8 8l-8 8a6 6 0 0 1-8 0Z"/>',
 ST:'<path d="M14 17H8l-5 4v-7A8 8 0 0 1 11 3a8 8 0 0 1 8 8"/><path d="M9 8v4m4-6v8m4-6v4m4 2v6m-3-4v2"/>',
 AUD:'<path d="M5 9a7 7 0 1 1 13 4c-2 2-4 2-4 5a4 4 0 0 1-8 0M9 10a3 3 0 1 1 5 2l-2 2"/><path d="M3 8v5"/>',
 CP:'<path d="M12 4c-3-3-7-1-7 3-4 0-5 6-2 8-1 5 6 8 9 4m0-15c3-3 7-1 7 3 4 0 5 6 2 8 1 5-6 8-9 4V4Z"/><path d="M5 7c0 3 2 4 4 4m10-4c0 3-2 4-4 4M4 15h3m10 0h3m-8-3-3 4m3-4 3 4"/>',
 MLS:'<path d="m10 3 5 3-5 9-5-3Zm-4 18h14M10 9l4 2m2 0a6 6 0 0 1-2 10M4 17h8"/><path d="m11 2 5 3"/>',
};
export function icon(name,size=24,cls=''){
  return `<svg class="ui-icon ${cls}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${paths[name]||paths.grid}</svg>`;
}
export const stepIcons=['clipboard','book','play','interaction','quiz','report'];
export const professionDescriptions={MD:'診斷整合・團隊決策',RN:'照護衛教・持續追蹤',DT:'營養評估・個人化飲食',PT:'功能評估・運動訓練',OT:'生活功能・環境支持',RT:'影像品質・報告溝通',RSP:'呼吸照護・活動觀察',RPH:'用藥整合・藥事溝通',ST:'吞嚥照護・溝通支持',AUD:'聽覺評估・溝通可近性',CP:'心理支持・行為改變',MLS:'檢體品質・檢驗溝通'};
export function brandMark(cls=''){
  return `<img class="brand-mark ${cls}" src="/static/assets/hospital-logo.png" width="56" height="56" alt="" aria-hidden="true">`;
}
export function learningJourney(){
  const names=['能力自評','教案目標','情境學習','角色互動','即時測驗','成果回饋'];
  return `<div class="journey-visual" aria-label="六階段學習旅程示意"><div class="journey-caption"><span class="tiny-dot"></span>YOUR LEARNING JOURNEY<span>六階段學習旅程</span></div><div class="journey-core"><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div><div class="journey-orbit-label orbit-label-one">教學 TEACHING</div><div class="journey-orbit-label orbit-label-two">服務 SERVICE</div><div class="journey-orbit-label orbit-label-three">研究 RESEARCH</div><div class="journey-symbol">${brandMark()}<span>以人為本<br><b>以能力為核心</b></span></div><div class="journey-spark">${icon('spark',22)}</div></div><div class="journey-nodes">${names.map((s,i)=>`<div><span class="journey-node">${icon(stepIcons[i],19)}</span><small>${String(i+1).padStart(2,'0')}</small><b>${s}</b></div>`).join('')}</div></div>`;
}
const dimLabels={CJ:'臨床判斷',PC:'評估照護',COM:'病人溝通',TC:'團隊溝通',SAFE:'安全倫理',HC:'全人照護'};
export function competencyRadar(scores={},unique='self',profile=null){
  const labels=profile?Object.fromEntries(profile.indicators.map(i=>[i.id,i.name])):dimLabels;
  const escape=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const ids=Object.keys(labels), cx=260,cy=200,r=120;
  const point=(i,f)=>[cx+Math.cos(-Math.PI/2+i*2*Math.PI/ids.length)*r*f,cy+Math.sin(-Math.PI/2+i*2*Math.PI/ids.length)*r*f];
  const pts=f=>ids.map((_,i)=>point(i,f).map(v=>v.toFixed(1)).join(',')).join(' ');
  const values=ids.map(id=>scores[id]===null||scores[id]===undefined||!Number.isFinite(Number(scores[id]))?null:Math.min(100,Math.max(0,Number(scores[id]))));
  const position=(v,i)=>point(i,v/100).map(n=>n.toFixed(1)).join(',');
  const actual=values.every(v=>v!==null)?`<polygon points="${values.map(position).join(' ')}" fill="#234EAE" fill-opacity=".16" stroke="#234EAE" stroke-width="2.5"/>`:values.map((v,i)=>{const next=(i+1)%ids.length;return v!==null&&values[next]!==null?`<polyline points="${position(v,i)} ${position(values[next],next)}" fill="none" stroke="#234EAE" stroke-width="2.5"/>`:'';}).join('');
  const summary=ids.map((id,i)=>`${labels[id]} ${values[i]===null?'未評估':(values[i]/20).toFixed(1)+'/5'}`).join('，');
  return `<svg class="competency-radar" viewBox="0 0 520 430" role="img" aria-label="職種核心能力自評雷達圖：${escape(summary)}"><title>附件職種核心能力對照（自評1–5；未評估不以0分代替）</title>${[.2,.4,.6,.8,1].map(f=>`<polygon points="${pts(f)}" fill="${f===1?'#F5F7FC':'none'}" stroke="#DDE4F1" stroke-width="1"/>`).reverse().join('')}${ids.map((id,i)=>{const [x,y]=point(i,1);return `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="#DDE4F1"/>`;}).join('')}${actual}${ids.map((id,i)=>{const v=values[i],[tx,ty]=point(i,1.35),anchor=tx>cx+20?'start':tx<cx-20?'end':'middle';const chars=Array.from(labels[id]),lines=[];while(chars.length)lines.push(chars.splice(0,8).join(''));const top=ty-(lines.length-1)*7;const marker=v===null?'':(()=>{const [x,y]=point(i,v/100);return `<circle cx="${x}" cy="${y}" r="4" fill="#D64254" stroke="white" stroke-width="2"/>`;})();return `${marker}<text x="${tx}" y="${top-4}" text-anchor="${anchor}" fill="#485B7B" font-size="14" font-family="inherit">${lines.map((line,k)=>`<tspan x="${tx}" dy="${k?14:0}">${escape(line)}</tspan>`).join('')}</text><text x="${tx}" y="${top+14*(lines.length-1)+14}" text-anchor="${anchor}" fill="#193E87" font-size="13" font-weight="700" font-family="inherit">${v===null?'未評估':(v/20).toFixed(1)+' / 5'}</text>`;}).join('')}<text x="260" y="422" text-anchor="middle" fill="#6F7E95" font-size="11" font-family="inherit">自評／舊版對應參考 · 未評項目不繪製分數點 · 非能力認證</text></svg>`;
}
export function learningTrack(steps,step){
  return `<ol class="learning-track" aria-label="六階段學習進度">${steps.map((s,i)=>`<li class="${i+1<step?'complete':i+1===step?'current':'upcoming'}" ${i+1===step?'aria-current="step"':''}><span class="track-icon">${icon(i+1<step?'check':stepIcons[i],18)}</span><span><small>STEP ${String(i+1).padStart(2,'0')}</small><b>${s}</b></span></li>`).join('')}</ol>`;
}
