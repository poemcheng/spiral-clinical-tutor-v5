"""Vendor official H5P runtime libraries at resolved immutable Git commits."""
from pathlib import Path
import hashlib
import io
import json
import shutil
import subprocess
import urllib.request
import zipfile
ROOT=Path(__file__).resolve().parents[1]
REPOS={'H5P.MultiChoice':'h5p-multi-choice','H5P.Question':'h5p-question','H5P.JoubelUI':'h5p-joubel-ui','FontAwesome':'font-awesome','H5P.Transition':'h5p-transition','H5P.FontIcons':'h5p-font-icons','H5P.Components':'h5p-components','jQuery.ui':'jquery-ui'}
DEST=ROOT/'frontend/vendor/h5p-libraries'
def fetch(url):
 return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'ClinicalTutor-source-vendor'}),timeout=60).read()
def main():
 DEST.mkdir(parents=True,exist_ok=True);pending=['H5P.MultiChoice'];done={}
 prior=json.loads((DEST/'provenance.json').read_text()) if (DEST/'provenance.json').exists() else {}
 while pending:
  name=pending.pop()
  if name in done:continue
  repo=REPOS[name];commit=prior.get(name,{}).get('commit') or json.loads(fetch(f'https://api.github.com/repos/h5p/{repo}/commits/master'))['sha']
  raw=fetch(f'https://codeload.github.com/h5p/{repo}/zip/{commit}')
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   base=z.namelist()[0];lib=json.loads(z.read(base+'library.json'));folder=f"{name}-{lib['majorVersion']}.{lib['minorVersion']}";target=DEST/folder;target.mkdir(exist_ok=True)
   for entry in z.infolist():
    rel=Path(entry.filename[len(base):]);p=(target/rel).resolve()
    if not p.is_relative_to(target.resolve()):raise ValueError('Unsafe vendor archive')
    if entry.is_dir():p.mkdir(parents=True,exist_ok=True)
    else:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(entry))
   for dep in lib.get('preloadedDependencies',[]):pending.append(dep['machineName'])
   if any(not (target/a['path']).is_file() for a in lib.get('preloadedJs',[])+lib.get('preloadedCss',[])):
    build=ROOT/'runtime/h5p-vendor-build'/folder
    shutil.copytree(target,build,dirs_exist_ok=True)
    cli=shutil.which('npm.cmd') or shutil.which('npm')
    subprocess.run([cli,'install','--ignore-scripts'],cwd=build,check=True)
    subprocess.run([cli,'run','build'],cwd=build,check=True)
    shutil.copytree(build/'dist',target/'dist',dirs_exist_ok=True)
   done[name]={'folder':folder,'majorVersion':lib['majorVersion'],'minorVersion':lib['minorVersion'],'commit':commit,'archive_sha256':hashlib.sha256(raw).hexdigest(),'source':f'https://github.com/h5p/{repo}/tree/{commit}','license':lib.get('license')}
 shutil.copytree(ROOT/'node_modules/h5p-standalone/dist',ROOT/'frontend/vendor/h5p',dirs_exist_ok=True)
 license_file=ROOT/'node_modules/h5p-standalone/LICENSE'
 if license_file.exists():shutil.copyfile(license_file,ROOT/'frontend/vendor/h5p/LICENSE')
 (DEST/'provenance.json').write_text(json.dumps(done,indent=2),encoding='utf-8')
 print(json.dumps({name:r['folder'] for name,r in done.items()}))
if __name__=='__main__':main()
