"""Prepare public release files only; never uploads or touches the game."""
from pathlib import Path
import hashlib,html,json,re,shutil,zipfile
from PIL import Image
from runtime_payload import stage_native_runtime,archive_native_runtime

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'dist/workshop_release'
OUT.mkdir(parents=True,exist_ok=True)
CONFIG=json.loads((ROOT/'release/config.json').read_text(encoding='utf-8'))
REPO=CONFIG.get('repository_url')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def archive(path,items):
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=9)as z:
        for source,name in sorted(items,key=lambda x:x[1]):
            info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
            z.writestr(info,source.read_bytes(),compresslevel=9)
    with zipfile.ZipFile(path)as z:assert z.testzip() is None

def inline(s):
    s=html.escape(s)
    s=re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',r'<a href="\2">\1</a>',s)
    s=re.sub(r'`([^`]+)`',r'<code>\1</code>',s)
    return re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',s)
def render_markdown(text):
    out=[];pre=False;table=False
    for line in text.splitlines():
        if line.startswith('```'):
            out.append('</code></pre>'if pre else'<pre><code>');pre=not pre;continue
        if pre:out.append(html.escape(line)+'\n');continue
        if line.startswith('|'):
            if re.match(r'^\|[\s:|\-]+\|$',line):continue
            if not table:out.append('<table>');table=True
            out.append('<tr>'+''.join('<td>'+inline(c.strip())+'</td>'for c in line.strip('|').split('|'))+'</tr>');continue
        if table:out.append('</table>');table=False
        if not line.strip():out.append('<div class="gap"></div>');continue
        if line.startswith('#'):
            n=len(line)-len(line.lstrip('#'));out.append(f'<h{n}>'+inline(line[n:].strip())+f'</h{n}>')
        else:out.append('<p>'+inline(line)+'</p>')
    if table:out.append('</table>')
    return '\n'.join(out)

for name in ('INSTALL_GUIDE.md','RELEASE_NOTES.md','PUBLISHING.md'):
    shutil.copyfile(ROOT/'release'/name,OUT/name)
body=render_markdown((ROOT/'release/INSTALL_GUIDE.md').read_text(encoding='utf-8'))
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MicroDuck — Install Guide</title>
<style>body{font:17px/1.6 system-ui,sans-serif;background:#f5f6f8;color:#202732;margin:0}main{max-width:900px;margin:30px auto;background:white;padding:38px;border-radius:16px}h1,h2{line-height:1.2}h1{font-size:34px}h2{margin-top:40px}p{margin:5px 0}a{color:#065bb4}code,pre{background:#edf1f5;border-radius:4px}code{padding:2px 5px}pre{padding:18px;overflow:auto}pre code{padding:0}table{border-collapse:collapse;width:100%;font-size:15px}td{padding:10px;border:1px solid #d5dbe3}tr:first-child{background:#e6edf5;font-weight:700}.gap{height:12px}.download{display:inline-block;padding:12px 20px;border-radius:9px;background:#ffca45;color:#17202c;font-weight:700;text-decoration:none}@media(max-width:600px){main{padding:22px;margin:0;border-radius:0}h1{font-size:27px}}</style><main><a class="download" href="MicroDuck_Runtime_Windows_x64.zip" download>Download companion runtime ZIP</a><p>Keep this guide beside the ZIP when using the local release bundle.</p>'''+body+'</main></html>'
(OUT/'INSTALL_GUIDE.html').write_text(page,encoding='utf-8')
native=stage_native_runtime(ROOT/'dist/native_runtime')
runtime_archive=archive_native_runtime(ROOT/'dist/native_runtime',ROOT/'dist/MicroDuck_Runtime_Windows_x64.zip')
package_report_path=ROOT/'build/package.json'
if package_report_path.exists():
    package_report=json.loads(package_report_path.read_text(encoding='utf-8'))
    package_report['native_runtime_zip']=runtime_archive
    package_report_path.write_text(json.dumps(package_report,indent=2),encoding='utf-8')
for name in ('MicroDuck_Runtime_Windows_x64.zip','microduck_real_ai.gma'):
    shutil.copyfile(ROOT/'dist'/name,OUT/name)
description=(ROOT/'release/WORKSHOP_DESCRIPTION.txt').read_text(encoding='utf-8')
repo=CONFIG.get('repository_url');runtime=CONFIG.get('runtime_download_url')
if repo:
    runtime=runtime or repo+'/releases/download/v'+CONFIG['version']+'/MicroDuck_Runtime_Windows_x64.zip'
    description=description.replace('{{RUNTIME_DOWNLOAD_URL}}',runtime).replace('{{INSTALL_GUIDE_URL}}',repo+'/blob/main/INSTALL_GUIDE.md')
(OUT/'WORKSHOP_DESCRIPTION.txt').write_text(description,encoding='utf-8')

# Export an authentic game capture in Workshop's required icon format.
pic=Image.open(ROOT/'build/roller_ingame.jpg').convert('RGB')
w,h=pic.size;side=int(min(w,h)*.70);cx=int(w*.52);cy=int(h*.57)
x=max(0,min(w-side,cx-side//2));y=max(0,min(h-side,cy-side//2))
pic=pic.crop((x,y,x+side,y+side)).resize((512,512),Image.Resampling.LANCZOS)
pic.save(OUT/'microduck_real_ai.jpg',quality=92,subsampling=2,progressive=False,optimize=True)

public=OUT/'github_source';public.mkdir(exist_ok=True)
for name in ('INSTALL_GUIDE.md','RELEASE_NOTES.md'):
    shutil.copyfile(OUT/name,public/name)
readme='''# MicroDuck for Garry's Mod

Experimental Windows 64-bit port of Pollen Robotics' physical robot and learned
policies. Walking and passive-wheel roller variants, pistol remote, player/chase
viewpoints, sit/stand, somersault, left/right kicks, and roller crouch.

**Players:** open Releases, download `MicroDuck_Runtime_Windows_x64.zip`, and follow
[the download/install guide](INSTALL_GUIDE.md). Subscribe on Workshop or install
the manual GMA. No Python is needed to play. Never install two addon copies.

This snapshot contains the port's code and original public ONNX policies. It
excludes compiler binaries, private test logs, gameplay snapshots and backups.
Generated Source meshes are distributed in the addon GMA; their reproducible
conversion scripts are included. Upstream robot/model sources are not vendored.

## Development

Use Python 3.14 with `requirements.txt` in `.venv`. Obtain `microduck`,
`microduck_rl` and `bam` from their upstream repositories under `upstream/`.
The policy/robot revision pins are recorded in `assets/skills_provenance.json`.
Build scripts use a local 64-bit GMod install for StudioMDL/GMad; adjust their
game path for your installation. The native build expects the Zig toolchain
described by `tools/get_native_compiler.py`. `native/mujoco_bridge/API.txt`
documents the v4 API. `tools/package.py` stages a clean addon and packs policy
JSON losslessly. `tools/build_release_bundle.py` prepares the release artifacts.

## Attribution and license

Original robot, policies and meshes: [Pollen Robotics](https://github.com/pollen-robotics/microduck)
and [microduck_rl](https://github.com/pollen-robotics/microduck_rl).
MuJoCo: https://github.com/google-deepmind/mujoco
Motor model reference: https://github.com/Rhoban/bam
Code notices: Apache-2.0 (`LICENSE-APACHE.txt`). Adapted robot meshes remain
CC BY-NC-SA 4.0, https://creativecommons.org/licenses/by-nc-sa/4.0/ . The GMA and
native ZIP retain their notices; the mesh license is not replaced by the code license.
'''
if REPO:
    readme=readme.replace('**Players:** open Releases, download',f'**Players:** open [the download release]({REPO}/releases/tag/v{CONFIG["version"]}), download')
(public/'README.md').write_text(readme,encoding='utf-8')
shutil.copyfile(ROOT/'addon/LICENSE-APACHE.txt',public/'LICENSE-APACHE.txt')
(public/'.gitignore').write_text('.venv/\nupstream/\nbuild/\ndist/\nbackups/\n__pycache__/\n')
selected=[]
for folder,patterns in [('addon/lua',['*.lua']),('native/mujoco_bridge',['*.cpp','*.h','build.py','prepare_scene.py','API.txt']),('native/physics_step',['abi.h']),('tools',['*.py']),('assets',['*.onnx','*manifest.json','*provenance.json']),('release',['*.md','*.txt','config.json'])]:
    for pattern in patterns:
        selected.extend((ROOT/folder).rglob(pattern))
selected += [ROOT/'requirements.txt',ROOT/'addon/addon.json',ROOT/'addon/README.txt']
for p in sorted(set(selected)):
    if '__pycache__'in p.parts:continue
    # Generated policy Lua is redundant with included original ONNX + exporters.
    if p.name.startswith('policy')and p.name.endswith('_data.lua'):continue
    dest=public/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
archive(OUT/'MicroDuck_Source.zip',[(p,p.relative_to(public).as_posix())for p in public.rglob('*')if p.is_file()and '.git' not in p.relative_to(public).parts])
files=[p for p in OUT.iterdir()if p.is_file()and p.name not in ('SHA256SUMS.txt','release_manifest.json','MicroDuck_Workshop_Release_Kit.zip')]
(OUT/'SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+p.name+'\n'for p in sorted(files)))
manifest={'version':CONFIG['version'],'repository_url':repo,'runtime_download_url':runtime,'github_published':False,'steam_published':False,
 'files':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)}for p in sorted(files)},'native_bridge_api':4,
 'pending':['GitHub release upload and verification','Steam Workshop upload']}
receipt_path=ROOT/'build/github_publication.json'
if receipt_path.exists():
    receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
    if receipt.get('verified')and receipt.get('repository_url')==repo and receipt.get('version')==CONFIG['version']:
        if all(receipt.get('files',{}).get(p.name,{}).get('sha256')==sha(p) for p in files):
            manifest.update(github_published=True,github_release_url=receipt['release_url'],pending=['Steam Workshop upload'])
(OUT/'release_manifest.json').write_text(json.dumps(manifest,indent=2))
archive(OUT/'MicroDuck_Workshop_Release_Kit.zip',[(p,p.relative_to(OUT).as_posix())for p in OUT.rglob('*')if p.is_file()and p.name!='MicroDuck_Workshop_Release_Kit.zip'and '.git' not in p.relative_to(OUT).parts])
print(json.dumps({'folder':str(OUT),'gma_bytes':(OUT/'microduck_real_ai.gma').stat().st_size,'runtime_zip_bytes':(OUT/'MicroDuck_Runtime_Windows_x64.zip').stat().st_size,'kit_zip_bytes':(OUT/'MicroDuck_Workshop_Release_Kit.zip').stat().st_size,'repository_url':repo},indent=2))
