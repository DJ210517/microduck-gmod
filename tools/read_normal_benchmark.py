from pathlib import Path
import json,numpy as np
p=Path(r'E:/SteamLibrary/steamapps/common/GarrysMod/garrysmod/data/microduck_dev/normal_benchmark.json')
r=json.loads(p.read_text())
Path('build/normal_benchmark.json').write_text(json.dumps(r))
for c in r:
 f=c['frames']; fall=next((x['t'] for x in f if x['gravity'][2]>-.7 or x['pos'][2]<c['initial_z']-2),None)
 print(c['config']['name'],'t',round(f[-1]['t'],2),'wall',round(f[-1]['wall'],2),'tick',c['tick'],'fall',fall,'gap',round(max(x['gap'] for x in f),3),'final_gravity',np.round(f[-1]['gravity'],3).tolist(),'travel',np.round(np.array(f[-1]['pos'])-np.array(f[0]['pos']),2).tolist())
