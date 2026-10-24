"""Fetch a portable, hash-checked compiler into this project's build directory."""
from pathlib import Path
import hashlib,json,urllib.request,zipfile
root=Path(__file__).resolve().parents[1]
dest=root/'build/toolchain'
dest.mkdir(parents=True,exist_ok=True)
index=json.load(urllib.request.urlopen('https://ziglang.org/download/index.json'))
release=index['0.17.0']['x86_64-windows']
archive=dest/Path(release['tarball']).name
if not archive.exists():
    urllib.request.urlretrieve(release['tarball'],archive)
digest=hashlib.sha256(archive.read_bytes()).hexdigest()
assert digest==release['shasum'],(digest,release['shasum'])
compiler=dest/archive.stem/'zig.exe'
if not compiler.exists():
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            assert (dest/item.filename).resolve().is_relative_to(dest.resolve())
        z.extractall(dest)
print(json.dumps({'compiler':str(compiler),'sha256':digest,'source':release['tarball']}))
