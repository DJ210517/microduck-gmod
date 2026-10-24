"""Install this task's staged addon folder and record copied-file hashes."""
from pathlib import Path
import hashlib,json,shutil
from runtime_payload import install_native_runtime
root=Path(__file__).resolve().parents[1]
source=(root/'dist/microduck_real_ai').resolve()
addons=Path(r'E:/SteamLibrary/steamapps/common/GarrysMod/garrysmod/addons').resolve()
target=(addons/'microduck_real_ai').resolve()
assert target.is_relative_to(addons) and target!=addons and not target.is_symlink()
assert source.is_dir() and (source/'addon.json').is_file()
shutil.copytree(source,target,dirs_exist_ok=True)
manifest={}
for path in source.rglob('*'):
    if not path.is_file(): continue
    rel=path.relative_to(source)
    expected=hashlib.sha256(path.read_bytes()).hexdigest()
    assert hashlib.sha256((target/rel).read_bytes()).hexdigest()==expected,rel
    manifest[rel.as_posix()]=expected
native=install_native_runtime(root/'dist/native_runtime',addons.parent)
(root/'build/installed_manifest.json').write_text(json.dumps({'directory':str(target),'files':manifest,'native_runtime':native},indent=2))
print('Installed and hash-checked',len(manifest),'files in',target)
