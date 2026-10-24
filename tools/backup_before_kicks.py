from pathlib import Path
from datetime import datetime
import hashlib,json,zipfile
root=Path(__file__).resolve().parents[1]
dest=root/'backups'/('working-skills-before-kicks-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
dest.mkdir()
paths=[p for folder in ['addon','tools','tests','native'] for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
paths += [root/'assets'/name for name in ['velstand.onnx','alpha_sitstand.onnx','roulade.onnx','skills_manifest.json','skills_provenance.json']]
paths += [root/'dist'/name for name in ['microduck_real_ai.gma','MicroDuck_Runtime_Windows_x64.zip','README.txt']]
archive=dest/'microduck-working-skills-backup.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
    for p in paths:z.write(p,p.relative_to(root))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
report={'path':str(archive),'files':len(paths),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
(dest/'backup.json').write_text(json.dumps(report,indent=2));(root/'build/kicks_backup.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
