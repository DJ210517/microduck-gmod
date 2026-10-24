"""Verify packaged release artifacts; requires an already extracted GMA tree."""
from pathlib import Path, PurePosixPath
import hashlib, json, lzma, zipfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist/workshop_release'
STAGE = ROOT / 'dist/microduck_real_ai'
EXTRACT = ROOT / 'build/workshop_extract_v01'
def sha(data): return hashlib.sha256(data).hexdigest()

manifest = json.loads((OUT / 'release_manifest.json').read_text(encoding='utf-8'))
for name, entry in manifest['files'].items():
    data = (OUT / name).read_bytes()
    assert len(data) == entry['bytes'] and sha(data) == entry['sha256'], name
checksums = (OUT / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()
for line in checksums:
    digest, name = line.split('  ', 1)
    assert sha((OUT / name).read_bytes()) == digest, name

stage = {p.relative_to(STAGE).as_posix(): p for p in STAGE.rglob('*') if p.is_file() and p.name != 'addon.json'}
extracted = {p.relative_to(EXTRACT).as_posix(): p for p in EXTRACT.rglob('*') if p.is_file() and p.name != 'addon.json'}
assert stage.keys() == extracted.keys(), (stage.keys() - extracted.keys(), extracted.keys() - stage.keys())
for name in stage:
    assert stage[name].read_bytes() == extracted[name].read_bytes(), name
    assert Path(name).suffix.lower() not in {'.dll', '.exe', '.html', '.js', '.py'}, name
assert not any('md_dev' in name or '/tests/' in name for name in stage)

packed = json.loads((EXTRACT / 'data_static/microduck_policies/manifest.json').read_text(encoding='utf-8'))['policies']
assert len(packed) == 7
for name, entry in packed.items():
    raw = lzma.decompress((EXTRACT / f'data_static/microduck_policies/{name}.dat').read_bytes())
    original = (ROOT / f'addon/lua/microduck/{name}.lua').read_text(encoding='utf-8').encode()
    assert raw == original[len(b'return [==['):-len(b']==]\n')], name
    assert len(raw) == entry['original_json_bytes'] and sha(raw) == entry['json_sha256'], name

zip_files = {}
for path in OUT.glob('*.zip'):
    with zipfile.ZipFile(path) as z:
        assert z.testzip() is None, path.name
        for name in z.namelist():
            assert not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts, name
            assert '\\' not in name and ':' not in name, name
        zip_files[path.name] = len(z.namelist())
with zipfile.ZipFile(OUT / 'MicroDuck_Runtime_Windows_x64.zip') as z:
    native = json.loads(z.read('manifest.json'))
    expected = {e['path'] for e in native['files']} | {'manifest.json', 'INSTALL.txt', 'INSTALL_GUIDE.md'}
    assert set(z.namelist()) == expected
    assert native['bridge_api'] == 4 and native['platform'] == 'windows-x86_64'
    for e in native['files']:
        assert len(z.read(e['path'])) == e['bytes'] and sha(z.read(e['path'])) == e['sha256']
with zipfile.ZipFile(OUT / 'MicroDuck_Source.zip') as z:
    assert not any(p in PurePosixPath(n).parts for n in z.namelist() for p in ('.git', '.venv', 'build', 'backups', '__pycache__'))
    assert not any(n.endswith(('.dll', '.exe')) for n in z.namelist())
with Image.open(OUT / 'microduck_real_ai.jpg') as pic:
    assert pic.format == 'JPEG' and pic.size == (512, 512) and not pic.info.get('progressive')
    assert pic.layer[0][1:3] == (2, 2), pic.layer  # baseline 4:2:0

live = ROOT / 'build/packed_policy_loaders_live.json'
report = {'passed': True, 'gma_files_verified': len(stage), 'policies_byte_exact': len(packed),
          'zips_crc_verified': zip_files, 'release_hashes_verified': len(manifest['files']),
          'icon_baseline_512_420': True, 'native_api': native['bridge_api'],
          'live_loader_checks': json.loads(live.read_text(encoding='utf-8')) if live.exists() else None,
          'public_links_ready': '{{' not in (OUT / 'WORKSHOP_DESCRIPTION.txt').read_text(encoding='utf-8')}
(ROOT / 'build/workshop_package_qa.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
