"""Install the official Windows connector and verify its release SHA256."""
import hashlib,json,os,re,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def install():
    folder=ROOT/'runtime/internet-tools';folder.mkdir(parents=True,exist_ok=True)
    target=folder/'cloudflared.exe';metadata=folder/'cloudflared-release.json'
    if target.is_file() and metadata.is_file():
        data=json.loads(metadata.read_text(encoding='utf-8'))
        with target.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        if digest==data.get('sha256'):return data
    request=urllib.request.Request('https://api.github.com/repos/cloudflare/cloudflared/releases/latest',headers={'User-Agent':'ClinicalTutorSetup'})
    with urllib.request.urlopen(request,timeout=30) as response:release=json.load(response)
    asset=next(a for a in release['assets'] if a['name']=='cloudflared-windows-amd64.exe')
    if not asset['browser_download_url'].startswith('https://github.com/cloudflare/cloudflared/releases/download/'):raise ValueError('Unexpected connector source')
    expected=asset.get('digest','').removeprefix('sha256:')
    if not expected:
        match=re.search(r'cloudflared-windows-amd64.exe:\s*([0-9a-f]{64})',release['body'])
        if not match:raise ValueError('Official release checksum missing')
        expected=match.group(1)
    with urllib.request.urlopen(asset['browser_download_url'],timeout=90) as response:raw=response.read()
    if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Connector checksum mismatch')
    temporary=target.with_suffix('.download');temporary.write_bytes(raw);temporary.replace(target)
    data={'version':release['tag_name'],'sha256':expected,'official_release':release['html_url']}
    metadata.write_text(json.dumps(data,indent=2),encoding='utf-8');return data

if __name__=='__main__':print(json.dumps(install()))
