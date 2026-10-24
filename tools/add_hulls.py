import json
import numpy as np
import build_assets as b
p=b.ADDON/'materials/microduck/robot.txt'
r=json.loads(p.read_text())
for l in r['links']:
    lines=(b.BUILD/l['name']/'collision.smd').read_text().split('triangles\n')[1].splitlines()
    vertices=np.array([[float(y) for y in x.split()[1:4]] for x in lines if x.startswith('0 ')])
    l['collision_vertices']=np.unique(vertices,axis=0).tolist()
b.write_json(p,r)
