import {epaLibraryPanel,mountEPA} from './epa-panel.js?v=5.6.2-r2';
const q=new URLSearchParams(location.search),sid=q.get('session'),clip=q.get('clip'),frame=q.has('frame')?Number(q.get('frame')):undefined,root=document.querySelector('#epa-review');let dispose;
try{
 if(!/^\d+$/.test(sid||''))throw Error('無效訓練連結');
 const r=await fetch(`/api/sessions/${sid}/epa-lessons`),d=await r.json();if(!r.ok)throw Error(d.detail||'讀取失敗');
 root.innerHTML=epaLibraryPanel(d,Number(sid),{readonly:true});dispose=await mountEPA(root.querySelector('.epa-library'),{initialClip:clip,initialFrame:frame});
}catch(e){root.textContent=e.message+'。請先於原平台登入並開啟已解鎖的訓練。';}
window.addEventListener('pagehide',()=>dispose?.(),{once:true});
