from pathlib import Path
import hashlib,json,struct,shutil,statistics
root=Path(__file__).resolve().parents[1]
def read(name):return json.loads((root/'build'/name).read_text())
live=read('roller_live_brake_fixed.json');edge=read('roller_edge_live.json');prop=read('roller_prop_live.json');walk=read('roller_walk_regression_live.json');offline=read('roller_v4_checks.json')
for r in (live,edge,prop,walk,offline):assert r['passed'],r.get('checks',r.get('error'))
installed=read('installed_manifest.json')
for rel,digest in installed['files'].items():assert hashlib.sha256((Path(installed['directory'])/rel).read_bytes()).hexdigest()==digest,rel
backup=read('rollers_backup.json');assert hashlib.sha256(Path(backup['path']).read_bytes()).hexdigest()==backup['sha256']
vertices={p.stem:struct.unpack_from('<i',p.read_bytes(),16)[0] for p in (root/'addon/models/microduck/rollers_v1').glob('*.vvd')}
assert len(vertices)==19 and max(vertices.values())<65536
frames=[f for f in live['samples'] if 6<f['t']<12]
speed=statistics.mean((f['velocity'][0]**2+f['velocity'][1]**2)**.5 for f in frames)
report={'passed':True,'backup':backup,'native':offline,'live':{k:v for k,v in live.items() if k not in ('samples','events')},'mean_skating_speed_m_s':speed,
 'edge':{k:v for k,v in edge.items() if k!='samples'},'prop':{k:v for k,v in prop.items() if k!='samples'},'walking_regression':walk['checks'],
 'installed_files_verified':len(installed['files']),'maximum_roller_model_vertices':max(vertices.values()),'package':read('package.json'),
 'scope':'Experimental separate roller entity. Live single-player gm_flatgrass at normal66.7Hz; real passive wheels, real released neural policies. Falls can require explicit R reset; no released roller get-up policy is bundled. Multiplayer/uneven terrain unverified.'}
(root/'build/roller_release_qa.json').write_text(json.dumps(report,indent=2))
image=Path(r'E:/SteamLibrary/steamapps/common/GarrysMod/garrysmod/data/microduck_roller/ingame.jpg')
if image.exists():shutil.copyfile(image,root/'build/roller_ingame.jpg')
print(json.dumps({'passed':True,'speed':speed,'installed_files':len(installed['files']),'drop_height':edge['landed_height'],'prop_moved_m':prop['moved_m'],'max_vertices':max(vertices.values())},indent=2))
