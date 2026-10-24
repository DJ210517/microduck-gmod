"""Verified, self-contained snapshot of playable assets and their source."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,zipfile
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('label');a=p.parse_args()
assert a.label and all(c.isalnum() or c=='-' for c in a.label)
dest=root/'backups'/(a.label+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
dest.mkdir()
paths=[f for name in ('addon','assets','tools','tests','native') for f in (root/name).rglob('*') if f.is_file() and '__pycache__' not in f.parts]
paths += [root/'dist'/name for name in ('microduck_real_ai.gma','MicroDuck_Runtime_Windows_x64.zip','README.txt')]
hashes={f.relative_to(root).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in paths}
archive=dest/'microduck-working-backup.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
    for f in paths:z.write(f,f.relative_to(root))
    z.writestr('BACKUP_SHA256.json',json.dumps(hashes,indent=2))
    z.writestr('RESTORE.txt','Working walking duck, remote, sit/stand, somersault and both kicks.\nClose GMod. Extract dist/microduck_real_ai.gma into garrysmod/addons, removing the newer loose microduck_real_ai addon folder to avoid duplicate assets. Extract MicroDuck_Runtime_Windows_x64.zip and copy its garrysmod contents into the game garrysmod folder. Source files are also included. Restart GMod.\n')
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
report={'path':str(archive),'files':len(paths),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
(dest/'backup.json').write_text(json.dumps(report,indent=2));(root/'build/rollers_backup.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
