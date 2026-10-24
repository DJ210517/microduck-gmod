import json
from pathlib import Path
p=Path(r'E:/SteamLibrary/steamapps/common/GarrysMod/garrysmod/data/microduck_dev')
r=json.loads((p/'benchmark.json').read_text())
for c in r:
 f=c['frames']
 fall=next((x['t'] for x in f if x['gravity'][2]>-.7 or x['z']<c['initial_z']-2),6)
 print(c['case']['name'], 'first_fall',round(fall,2),'standing_samples',sum(x['gravity'][2]<-.9 and x['z']>c['initial_z']-1 for x in f),'maxgap',round(max(max(x['gaps']) for x in f),3))
