"""Fast installed-package check. Do not run pip on every normal Windows launch."""
from importlib import metadata
from pathlib import Path

def missing_packages(root):
    lock=Path(root)/'requirements.lock.txt'
    if not lock.is_file():return ['requirements.lock.txt unavailable']
    missing=[]
    for line in lock.read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith('#'):continue
        name,expected=line.split('==',1)
        try:actual=metadata.version(name)
        except metadata.PackageNotFoundError:actual=None
        if actual!=expected:missing.append(name)
    return missing

if __name__=='__main__':
    missing=missing_packages(Path(__file__).resolve().parents[1])
    if missing:print('Dependency setup needed: '+', '.join(missing))
    raise SystemExit(bool(missing))
