const video=document.querySelector('#workflow');
const status=document.querySelector('#video-status');
video.addEventListener('loadedmetadata',()=>{status.textContent=`完整影片 ${Math.floor(video.duration/60)} 分 ${Math.round(video.duration%60)} 秒；可點章節跳轉。`;});
video.addEventListener('error',()=>{status.textContent='目前無法直接載入影片，請使用上方 MP4 下載連結。';});
fetch('operation-chapters.json').then(r=>{if(!r.ok)throw Error('chapters');return r.json();}).then(rows=>{
  for(const row of rows){
    const button=document.createElement('button');button.type='button';
    const minutes=Math.floor(row.start/60);const seconds=Math.floor(row.start%60);
    button.textContent=`${String(minutes).padStart(2,'0')}:${String(seconds).padStart(2,'0')} ${row.title}`;
    button.addEventListener('click',()=>{video.currentTime=row.start;video.play().catch(()=>{status.textContent='請按影片播放鍵開始觀看。';});video.scrollIntoView({behavior:'smooth',block:'center'});});
    document.querySelector('#chapters').append(button);
  }
}).catch(()=>{document.querySelector('#chapters').textContent='章節暫時無法載入，仍可使用影片進度條。';});
