"""Package source and academic deliverables, excluding local data and secrets."""
import hashlib
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'entregables'
archive=OUT/'MVP-Intendencia-v1.zip'
excluded={'.git','instance','.venv','__pycache__','raw'}
files=[p for p in ROOT.rglob('*') if p.is_file() and not any(part in excluded for part in p.relative_to(ROOT).parts)
       and p.suffix not in {'.pyc','.zip'} and p.name not in {'SHA256SUMS.txt','servidor-demo.log'}]
with ZipFile(archive,'w',ZIP_DEFLATED) as package:
    for path in sorted(files):
        package.write(path,'MVP-Intendencia-v1/'+str(path.relative_to(ROOT)))
assert ZipFile(archive).testzip() is None
checks=[]
for path in sorted(OUT.iterdir()):
    if path.is_file() and path.suffix in {'.zip','.pdf','.pptx','.mp4','.txt','.json','.srt'} and path.name != 'SHA256SUMS.txt':
        checks.append(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.name)
(OUT/'SHA256SUMS.txt').write_text('\n'.join(checks)+'\n')
print(f'{archive} · {len(files)} archivos · {archive.stat().st_size:,} bytes')
