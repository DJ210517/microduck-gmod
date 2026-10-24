from pathlib import Path
import json,numpy as np
from scipy.spatial import cKDTree
p=Path(r'E:/SteamLibrary/steamapps/common/GarrysMod/garrysmod/data/microduck_dev')
r=json.loads((p/'geometry_audit.json').read_text())
data=json.loads(Path('addon/materials/microduck/robot.txt').read_text())
for i,l in enumerate(r['links']):
 actual=np.array(l['mesh']); expected=np.array(data['links'][i]['collision_vertices'])
 print(l['name'],'mesh_bounds',np.round(actual.min(0),2),np.round(actual.max(0),2),'expected',np.round(expected.min(0),2),np.round(expected.max(0),2),'dist',round(cKDTree(expected).query(actual)[0].max(),2),'bottom',round(np.array(l['world'])[:,2].min(),3),'com',l['com'])
print(r['joints'])
