"""Native sidecar staging/install helpers; import has no side effects.

DLLs cannot be packed in GMAs. stage_native_runtime makes a separate file tree
whose garrysmod/ subtree is copied into the game's garrysmod directory.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage_native_runtime(destination: Path) -> dict:
    import mujoco
    destination = destination.resolve()
    # The versioned build can be tested beside a loaded module. Distribution
    # keeps the stable require("microduck_mujoco") name after a game restart.
    bridge = ROOT / 'build/native/microduck_mujoco4/gmsv_microduck_mujoco4_win64.dll'
    runtime = Path(mujoco.__file__).parent / 'mujoco.dll'
    sources = {'garrysmod/lua/bin/gmsv_microduck_mujoco_win64.dll': bridge,
               'garrysmod/lua/bin/mujoco.dll': runtime}
    licenses = runtime.parent.parent / f'mujoco-{mujoco.__version__}.dist-info/licenses'
    sources['licenses/mujoco/LICENSE.txt'] = licenses / 'LICENSE'
    sources['licenses/mujoco/THIRD_PARTY.txt'] = licenses / 'LICENSES_THIRD_PARTY.md'
    files = []
    for relative, source in sources.items():
        if not source.is_file():
            raise FileNotFoundError(f'Required native runtime payload not built: {source}')
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        files.append({'path': relative, 'bytes': target.stat().st_size, 'sha256': sha256(target)})
    result = {'schema_version': 1, 'platform': 'windows-x86_64', 'mujoco_version': mujoco.__version__,
              'native_module': 'microduck_mujoco', 'bridge_api': 4, 'files': files,
              'external_dependency': 'Microsoft Visual C++ v14 x64 runtime, including MSVCP140_ATOMIC_WAIT.dll',
              'install_root': 'GarrysMod', 'installed': False}
    (destination / 'manifest.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    (destination / 'INSTALL.txt').write_text(
        'MicroDuck native runtime - Windows x64\n\n'
        'Subscribe to/install the MicroDuck addon separately.\n'
        'Close Garry\'s Mod before installing or updating the runtime.\n'
        'Steam > Garry\'s Mod > Manage > Browse local files.\n'
        'Copy this archive\'s garrysmod folder into that GarrysMod installation, merging folders.\n'
        'The final files must be garrysmod/lua/bin/gmsv_microduck_mujoco_win64.dll\n'
        'and garrysmod/lua/bin/mujoco.dll. Restart the 64-bit game.\n\n'
        'This runtime includes terrain-refresh and numerical-fault protection.\n'
        'Requires the latest supported Microsoft Visual C++ v14 x64 runtime.\n'
        'Official download: https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist\n'
        'Includes bridge API4 for walking and passive roller wheels. No Python installation is needed.\n'
        'License notices are in licenses/. Multiplayer is not yet validated.\n', encoding='utf-8')
    guide=ROOT/'release/INSTALL_GUIDE.md'
    if guide.exists():shutil.copyfile(guide,destination/'INSTALL_GUIDE.md')
    return result


def archive_native_runtime(source: Path, archive: Path) -> dict:
    source, archive = source.resolve(), archive.resolve()
    manifest = json.loads((source / 'manifest.json').read_text())
    for entry in manifest['files']:
        path = (source / entry['path']).resolve()
        if not path.is_relative_to(source) or sha256(path) != entry['sha256']:
            raise ValueError('Native runtime archive source failed verification')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        selected=[source/entry['path'] for entry in manifest['files']]+[source/'manifest.json',source/'INSTALL.txt']
        if (source/'INSTALL_GUIDE.md').exists():selected.append(source/'INSTALL_GUIDE.md')
        for path in sorted(selected):
            if path.is_file():
                info=zipfile.ZipInfo(path.relative_to(source).as_posix(),(1980,1,1,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
                output.writestr(info,path.read_bytes(),compresslevel=9)
    with zipfile.ZipFile(archive) as check:
        if check.testzip() is not None: raise ValueError('Native runtime ZIP failed CRC verification')
    return {'file': str(archive), 'bytes': archive.stat().st_size, 'sha256': sha256(archive)}


def install_native_runtime(source: Path, game_directory: Path) -> dict:
    """Install only listed native files; never replace unrelated game files."""
    source, game_directory = source.resolve(), game_directory.resolve()
    manifest = json.loads((source / 'manifest.json').read_text())
    if manifest.get('schema_version') != 1 or manifest.get('platform') != 'windows-x86_64':
        raise ValueError('Unsupported native sidecar manifest')
    verified = {}
    for entry in manifest['files']:
        relative = Path(entry['path'])
        if relative.parts[:3] != ('garrysmod', 'lua', 'bin'):
            continue
        if relative.name not in ('gmsv_microduck_mujoco_win64.dll', 'mujoco.dll') or len(relative.parts) != 4:
            raise ValueError(f'Unexpected native runtime path: {relative}')
        original = (source / relative).resolve()
        target = (game_directory / Path(*relative.parts[1:])).resolve()
        if not original.is_relative_to(source) or not target.is_relative_to(game_directory / 'lua/bin'):
            raise ValueError('Native runtime path escaped its intended directory')
        if sha256(original) != entry['sha256']:
            raise ValueError(f'Native runtime payload hash mismatch: {relative}')
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or sha256(target) != entry['sha256']:
            shutil.copy2(original, target)
        if sha256(target) != entry['sha256']:
            raise ValueError(f'Native runtime install hash mismatch: {target}')
        verified[target.name] = entry['sha256']
    if len(verified) != 2:
        raise ValueError('Native sidecar manifest must contain both bridge and MuJoCo DLLs')
    return {'directory': str(game_directory / 'lua/bin'), 'files': verified}
