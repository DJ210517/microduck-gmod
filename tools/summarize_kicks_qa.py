from pathlib import Path
import hashlib,json,shutil
root=Path(__file__).resolve().parents[1]
data=Path(r'E:/SteamLibrary/steamapps/common/GarrysMod/garrysmod/data/microduck_kicks')
raw=json.loads((root/'build/kicks_live_initial.json').read_text())
assert len(raw['cases'])==4
cases=[]
for c in raw['cases']:
    if not c.get('passed'):continue
    assert all(c['checks'].values()) and not c.get('error')
    assert c['actual_gravity'] and .099<c['mass_kg']<.101
    phases=[s['phase'] for s in c['samples']]
    assert c['skill'] in phases and 'recover' in phases and phases[-1]=='walk'
    cases.append({k:v for k,v in c.items() if k not in ('samples','native_start')})
assert {c['skill'] for c in cases}=={'kick_left','kick_right'}
assert {c['shape'] for c in cases}=={'sphere','cube'}
assert any(c['yaw']!=0 for c in cases)
shutil.copyfile(data/'live.json',root/'build/kicks_live_placement_trials.json')
autoload=json.loads((data/'autoload.json').read_text());assert autoload['passed']
report={'passed':True,'validation':'Live single-player gm_flatgrass, real remote UserCmd inputs, passive Source props with gravity. Numerical Lua/ONNX parity and control/scheduler regression tests separately recorded.',
    'server_tickrate':1/raw['tick'],'controls':{'left_kick':'Shift + left mouse','right_kick':'Shift + right mouse'},'cases':cases,
    'fresh_map_autoload':autoload,
    'user_confirmation':'it works, i tested it',
    'trial_limits':'Initial left-sphere trial rejected because prop rolled into duck before triggering; three other original trials passed intended-foot contact, positive forward impulse, prop movement, upright recovery and post-kick walking. Further placement trials showed a miss when target moved from9cm to10.5cm ahead. Test sphere mesh was replaced by exact Source sphere for those placement trials. Kicks remain blind and positioning-sensitive. Final modifier-latch changes validated by control regression; final installed build autoloaded after map change. Live input testing stopped after user confirmation.',
    'policy_lua_parity':json.loads((root/'build/skills_lua_parity.json').read_text()),
    'control_regression':json.loads((root/'build/audit_microduck_controls.json').read_text()),
    'backup':json.loads((root/'build/kicks_backup.json').read_text()),
    'package':json.loads((root/'build/package.json').read_text())}
installed=json.loads((root/'build/installed_manifest.json').read_text())
for rel,expected in installed['files'].items():
    assert hashlib.sha256((Path(installed['directory'])/rel).read_bytes()).hexdigest()==expected
report['installed_files_verified']=len(installed['files'])
(root/'build/kicks_release_qa.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k in ('passed','server_tickrate','controls','installed_files_verified')},indent=2))
print(json.dumps([{k:c[k] for k in ('skill','yaw','shape','max_forward_m','max_planar_m','peak_forward_m_s','walked_m') if k in c} for c in cases],indent=2))
