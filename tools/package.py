from pathlib import Path
import json,shutil,subprocess,hashlib
from runtime_payload import stage_native_runtime,archive_native_runtime
from pack_policies import pack
root=Path(__file__).resolve().parents[1]
source=root/'addon'
out=root/'dist/microduck_real_ai'
assert out.resolve().parent==(root/'dist').resolve() and not out.is_symlink()
if out.exists(): shutil.rmtree(out)
out.mkdir(parents=True,exist_ok=True)
r=json.loads((source/'materials/microduck/robot.txt').read_text())
for name in ['lua','materials']:
    shutil.copytree(source/name,out/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('*.txt'))
if (source/'data_static/microduck_mj/manifest.json').is_file():
    shutil.copytree(source/'data_static',out/'data_static',dirs_exist_ok=True)
models=out/'models/microduck'
if models.exists():
    for old in models.iterdir():
        if old.is_dir() and old.name not in (Path(r['model_dir']).name,'rollers_v1'):
            assert old.resolve().is_relative_to(out.resolve())
            shutil.rmtree(old)
shutil.copytree(source/'models'/r['model_dir'],out/'models'/r['model_dir'],dirs_exist_ok=True)
if (source/'models/microduck/rollers_v1').exists():
    shutil.copytree(source/'models/microduck/rollers_v1',out/'models/microduck/rollers_v1',dirs_exist_ok=True)
for name in ['addon.json']:
    shutil.copyfile(source/name,out/name)
for stale in ['README.txt','LICENSE-APACHE.txt','materials/microduck/policy.txt','materials/microduck/robot.txt']:
    old=out/stale
    assert old.resolve().is_relative_to(out.resolve())
    if old.exists(): old.unlink()
credits=(source/'README.txt').read_text()+'\n\n'+(source/'LICENSE-APACHE.txt').read_text()
(out/'lua/microduck/credits.lua').write_text('--[==[\n'+credits+'\n]==]\n',encoding='utf-8')
shutil.copyfile(source/'README.txt',root/'dist/README.txt')
game=Path(r'E:\SteamLibrary\steamapps\common\GarrysMod')
packed_policies=pack(source,out)
gma=root/'dist/microduck_real_ai.gma'
result=subprocess.run([str(game/'bin/gmad.exe'),'create','-folder',str(out),'-out',str(gma)],capture_output=True,text=True)
(root/'build/package.log').write_text(result.stdout+result.stderr)
if result.returncode: raise RuntimeError(result.stdout+result.stderr)
native=stage_native_runtime(root/'dist/native_runtime')
report={'gma_bytes':gma.stat().st_size,'gma_sha256':hashlib.sha256(gma.read_bytes()).hexdigest(),'policy_sha256':hashlib.sha256((root/'assets/velstand.onnx').read_bytes()).hexdigest(),'files':len(list(out.rglob('*'))),'model_dir':r['model_dir']}
report['lossless_policy_packing']=packed_policies
report['native_runtime']={'directory':'dist/native_runtime','files':native['files'],'mujoco_version':native['mujoco_version']}
report['native_runtime_zip']=archive_native_runtime(root/'dist/native_runtime',root/'dist/MicroDuck_Runtime_Windows_x64.zip')
report['skill_policy_sha256']={name:hashlib.sha256((root/'assets'/name).read_bytes()).hexdigest() for name in ('alpha_sitstand.onnx','roulade.onnx','ball_kick_left.onnx','ball_kick_right.onnx')}
report['roller_policy_sha256']={name:hashlib.sha256((root/'assets'/name).read_bytes()).hexdigest() for name in ('roller.onnx','roller_crouch.onnx')}
(root/'build/package.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items()if k not in ('lossless_policy_packing','native_runtime')}))
