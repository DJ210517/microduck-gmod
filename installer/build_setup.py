"""Build a standalone Windows x64 setup EXE from the already verified runtime ZIP."""
from pathlib import Path
import hashlib, json, os, subprocess, zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist/installer'
OUT.mkdir(parents=True, exist_ok=True)
runtime = ROOT / 'dist/workshop_release/MicroDuck_Runtime_Windows_x64.zip'
EXPECTED_RUNTIME_SHA256 = '8050c2dc4ec70968804847074d405c663153c0f87c01a02689c32a056856bda1'
assert hashlib.sha256(runtime.read_bytes()).hexdigest() == EXPECTED_RUNTIME_SHA256
with zipfile.ZipFile(runtime) as z:
    assert z.testzip() is None
    manifest = json.loads(z.read('manifest.json'))
    for entry in manifest['files']:
        assert hashlib.sha256(z.read(entry['path'])).hexdigest() == entry['sha256']
compiler = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
exe = OUT / 'MicroDuck_Setup_Windows_x64.exe'
args = [str(compiler), '/nologo', '/target:winexe', '/platform:x64', '/optimize+', '/utf8output',
        '/out:' + str(exe), '/win32manifest:' + str(ROOT / 'installer/app.manifest'),
        '/resource:' + str(runtime) + ',Runtime.zip', '/r:System.Windows.Forms.dll', '/r:System.Drawing.dll',
        '/r:System.Web.Extensions.dll', '/r:System.IO.Compression.dll',
        str(ROOT / 'installer/MicroDuckSetup.cs'), str(ROOT / 'installer/SetupTests.cs')]
subprocess.run(args, check=True)
digest = hashlib.sha256(exe.read_bytes()).hexdigest()
(OUT / 'MicroDuck_Setup_SHA256.txt').write_text(digest + '  ' + exe.name + '\n')
(OUT / 'setup_manifest.json').write_text(json.dumps({'file': exe.name, 'bytes': exe.stat().st_size,
    'sha256': digest, 'embedded_runtime_zip_sha256': hashlib.sha256(runtime.read_bytes()).hexdigest(),
    'bridge_api': manifest['bridge_api'], 'mujoco_version': manifest['mujoco_version'],
    'signed': False, 'administrator_requested': False, 'files': manifest['files']}, indent=2))
print(json.dumps({'exe': str(exe), 'bytes': exe.stat().st_size, 'sha256': digest}))
