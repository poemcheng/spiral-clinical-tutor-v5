const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function epaAnnotation(segment,keyframe){
 if(!segment&&!keyframe)return '<p class="note">此格未提供人工事件註記。模型觀測仍可檢視，請以原片前後脈絡判讀。</p>';
 const fields=[['可見動作／觀察線索','visible_action'],['對話功能（非逐字稿）','dialogue_function'],['動作與對話關聯','action_dialogue_relation'],['動作類別','category'],['EPA觀察與安全重點','epa_focus'],['這一步的教學目的','purpose'],['判讀限制與其他解釋','limitation']];
 const pose=keyframe?.qualitative_pose;
 return `<section class="epa-annotation"><h3>${esc(segment?.title||keyframe?.title||'EPA影格解析')}</h3><p class="source">段落教學脈絡，不宣稱每張圖均完成所列行為。${esc(segment?.evidence_type||'來源教案與可見畫面對照之教學草稿')}</p><dl>${fields.filter(([,k])=>segment?.[k]||k==='visible_action'&&keyframe?.visible_action).map(([label,k])=>`<dt>${label}</dt><dd>${esc(k==='visible_action'&&keyframe?.visible_action?keyframe.visible_action:segment[k])}</dd>`).join('')}</dl>${segment?.dimensions?.length?`<p>來源能力標記：${segment.dimensions.map(esc).join('、')}（不是正式EPA授權）</p>`:''}${pose?`<details open><summary>此代表格的人工姿勢註記（非精確量測）</summary><dl>${Object.entries(pose).map(([k,v])=>`<dt>${esc({subject_posture:'主體與姿勢',head_neck:'頭頸',trunk:'軀幹',upper_limbs:'上肢',lower_limbs:'下肢',joints_classification:'關節、肢段與互動'}[k]||k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl><p>來源人工估計的角度與視線描述，與下方本格模型數值分開判讀；未代表教師已核定。</p></details>`:''}</section>`;
}
export function bodyRegionSummary(poses=[]){
 if(!poses.length)return '<p>本格沒有可靠人體骨架；頭頸、軀幹、上肢、下肢均無法作模型判讀。</p>';
 const show=x=>x==null?'遮擋／未達可見門檻':`${Number(x).toFixed(1)}°二維投影`;
 const head=p=>{const points=(p.landmarks||[]).slice(0,11),n=points.filter(v=>v.visibility>=.65&&v.presence>=.65&&v.x>=0&&v.x<=1&&v.y>=0&&v.y<=1).length;return points.length?`頭部關鍵點可見${n}/11；只提供畫面位置線索，不是頸椎角度量測。`:'未提供可核對的頭部關鍵點。';};
 return `<section><h3>本格頭頸、軀幹與肢段觀測</h3>${poses.map(p=>`<article><h4>候選軌跡 P${esc(p.track_id)}（非身分或職類）</h4><dl><dt>頭頸與視線</dt><dd>${head(p)}骨架不確認注視對象、理解或同理，需看原圖及語音。</dd><dt>軀幹</dt><dd>投影偏斜 ${show(p.metrics?.torso_tilt)}</dd><dt>上肢</dt><dd>左肘 ${show(p.metrics?.left_elbow)}；右肘 ${show(p.metrics?.right_elbow)}</dd><dt>下肢</dt><dd>左膝 ${show(p.metrics?.left_knee)}；右膝 ${show(p.metrics?.right_knee)}</dd></dl></article>`).join('')}</section>`;
}
