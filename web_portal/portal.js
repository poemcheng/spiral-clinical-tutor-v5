export function localServer(value){
 const url=new URL(value);if(url.protocol!=='https:'||url.username||url.password)throw Error('請輸入主機提供的 HTTPS 位址。');
 const parts=url.hostname.split('.').map(Number);
 const privateIP=parts.length===4&&parts.every(n=>Number.isInteger(n)&&n>=0&&n<=255)&&(parts[0]===10||(parts[0]===192&&parts[1]===168)||(parts[0]===172&&parts[1]>=16&&parts[1]<=31));
 if(!privateIP)throw Error('此入口僅連線同網路的內部 IP 位址。');
 url.pathname='/login';url.search='';url.hash='';return url.href;
}
if(typeof document!=='undefined'){
 const field=document.querySelector('#host'),status=document.querySelector('#status');
 fetch('server-config.json',{cache:'no-store'}).then(r=>r.json()).then(c=>{field.value=localStorage.getItem('clinical-lan-server')||c.default_server;document.querySelector('#check-link').href=new URL('/static/connection-check.html',localServer(field.value)).href;document.querySelector('#fingerprint').textContent='CA 憑證 SHA-256：'+c.ca_sha256;}).catch(()=>{status.textContent='請向主機管理者確認 HTTPS 位址。';});
 document.querySelector('#connect').onsubmit=e=>{e.preventDefault();try{const target=localServer(field.value);localStorage.setItem('clinical-lan-server',new URL(target).origin);location.assign(target);}catch(error){status.textContent=error.message;}};
}
