/* CareLab v2 GitHub Pages adapter: deterministic synthetic data; no network requests.
 * All clinical-sounding outputs are teaching examples, never medical advice.
 */
(function () {
  'use strict';
  const patient = {
    id: 'SYN-LIN72-01', name: '林阿姨（合成角色）', age: 72,
    goal: '維持自行買菜與參加社區聚會的生活',
    source: '教學合成資料 / 完全虛構',
    limitations: ['沒有肌力或肌肉量量測', '不提供診斷', 'ECG、足壓、步態是演示訊號']
  };
  const walk = [15, 20, null, 10, 25, 20, 15];
  const QA = [
    {keys:['買菜','外出','活動','生活'],answer:'我想自己買菜，也想繼續參加社區活動。可以先看看我想達成什麼，再一起討論。',evidence:'synthetic_interview.txt / life-goal'},
    {keys:['11/03','11月3','空白','缺失','未記錄'],answer:'那天有外出，但我忘記記步行分鐘。請保留「未記錄」，不要當作零。',evidence:'synthetic_interview.txt / missing-day'},
    {keys:['飲食','吃','營養','蛋白'],answer:'我有記錄吃過的食物，不過沒有記份量。希望能和營養專業人員討論。',evidence:'synthetic_interview.txt / nutrition'},
    {keys:['跌倒','平衡','害怕'],answer:'我想知道如何安全地參與活動，但這份合成案例沒有提供正式跌倒史或評估結果。',evidence:'synthetic_interview.txt / no-fall-history'},
    {keys:['肌少','診斷','是不是生病'],answer:'這套系統是教學模擬，不能根據畫面或生活紀錄確認肌少症。請向專業人員諮詢正式評估。',evidence:'teaching_safety_rule'}
  ];
  function frame(t,scenario){
    const stress=scenario==='discordant'?1:0;
    const sin=Math.sin, pi=Math.PI;
    return {
      t, scenario, hr_bpm: Math.round((75+3*sin(2*pi*t/19)+8*stress)*10)/10,
      spo2_pct: scenario==='missing'?null:Math.round((97+0.5*sin(t/11))*10)/10,
      bp_mmHg:[Math.round(124+3*sin(t/9)+5*stress),Math.round(77+2*Math.cos(t/12))],
      gait_m_s:Math.round((.78+.1*sin(t/17))*100)/100,
      pressures:[Math.round((.6+.2*sin(t/3))*100)/100,Math.round((.6+.2*Math.cos(t/3))*100)/100],
      source:'synthetic_demo',diagnostic:false
    };
  }
  function analyze(scenario){
    const valid=walk.filter(v=>v!==null);const total=valid.reduce((a,b)=>a+b,0);
    const issues=['所有訊號與角色均為合成，不可作診斷或療效推論'];
    if(scenario==='missing')issues.push('血氧模態缺失：不可由其他模態補出血氧數值');
    if(scenario==='discordant')issues.push('模態衝突示例：文字與合成訊號不一致，需核對來源與時間戳，停止下結論');
    return {patient,scenario,issues,facts:[
      {claim:'七日紀錄有六天填寫步行分鐘',source:'activity_meal_7days.csv',verified:true},
      {claim:`已記錄日合計 ${total} 分鐘、平均 ${(total/valid.length).toFixed(1)} 分鐘（分母 6）`,source:'activity_meal_7days.csv',verified:true},
      {claim:'11/03 未記錄；不能視為零',source:'activity_meal_7days.csv',verified:true},
      {claim:patient.goal,source:'synthetic_interview.txt',verified:true}],
      modalities:{text:{source:'synthetic_interview.txt',verified:true},activity:{source:'activity_meal_7days.csv',missing_days:['11/03'],verified:true},physiology:{source:'synthetic_demo',diagnostic:false},motion:{source:'procedural_3d_animation',diagnostic:false}}
    };
  }
  function sbar(scenario){
    return {
      S:'合成個案林阿姨希望維持買菜及社區參與，進行照護溝通練習（非真實患者）。',
      B:'72歲；七日活動自述六筆有效、一天未記錄。無正式肌力量測、肌肉量或疾病史。',
      A:'僅能描述合成自述資料。已記錄步行分鐘合計105分鐘、平均17.5分鐘／已記錄日。不可診斷肌少症。'+(scenario==='missing'?' 血氧模態缺失。':'')+(scenario==='discordant'?' 模態衝突待核。':''),
      R:'先與本人確認生活目標及缺漏紀錄；如有持續功能困難，轉介合適專業人員評估。',
      sources:'synthetic_interview.txt; activity_meal_7days.csv; teaching_rules'
    };
  }
  function grade(fields){
    const criteria={S:['目標','買菜','社區'],B:['72','未記錄','紀錄'],A:['105','17.5','不能','不可'],R:['確認','評估','專業']};
    let score=0;const details={};
    for(const [key,words] of Object.entries(criteria)){
      const value=String(fields[key]||'');const found=words.filter(w=>value.includes(w)).length;
      const sub=Math.round(25*found/words.length);score+=sub;
      details[key]={score:sub,max:25,checks:Object.fromEntries(words.map(w=>[w,value.includes(w)]))};
    }
    const all='SBAR'.split('').map(k=>String(fields[k]||'')).join(' ');
    const unsafe=['確診肌少症','一定是肌少症','治癒肌少症'].some(k=>all.includes(k));
    if(unsafe)score=Math.min(score,60);
    return {score,max:100,details,unsafe_claim:unsafe,label:'教學字詞覆蓋評分，不是臨床判斷、EPA 認證或醫療能力測驗'};
  }
  function reply(q){
    for(const item of QA){if(item.keys.some(k=>q.includes(k)))return {reply:item.answer,evidence:item.evidence,mode:'scripted_demo'};}
    return {reply:'請再針對我的生活目標、飲食、缺失紀錄或評估界線提出具體問題。',evidence:'scripted_fallback',mode:'scripted_demo'};
  }
  window.carelabAPI=async function(path,options={}){
    const url=new URL(path,location.href), data=options.body?JSON.parse(options.body):{};
    const scenario=['baseline','missing','discordant'].includes(data.scenario)?data.scenario:'baseline';
    if(url.pathname.endsWith('/api/frame')){
      const s=['baseline','missing','discordant'].includes(url.searchParams.get('scenario'))?url.searchParams.get('scenario'):'baseline';
      const t=Math.max(0,Math.min(3600,Number(url.searchParams.get('t')||0)));
      return frame(t,s);
    }
    if(url.pathname.endsWith('/api/analyze'))return analyze(scenario);
    if(url.pathname.endsWith('/api/sbar'))return sbar(scenario);
    if(url.pathname.endsWith('/api/grade'))return grade(data.fields||{});
    if(url.pathname.endsWith('/api/chat')){
      if(data.provider && data.provider!=='demo')throw Error('公開 GitHub Pages 版僅供固定腳本；請使用自行架設的受控 FastAPI 後端啟用外部模型。');
      return reply(String(data.question||''));
    }
    if(url.pathname.endsWith('/api/patient'))return patient;
    if(url.pathname.endsWith('/api/health'))return {status:'ok',synthetic_only:true,providers:['demo'],hosting:'github-pages'};
    throw Error('Unknown demo API endpoint: '+url.pathname);
  };
})();