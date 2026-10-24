"""Write isolated symmetric sole collider candidates for a live comparison.

No addon or game files are written and StudioMDL is not invoked. All points are
expressed in the existing v5 COM/principal frame, so existing visual models and
joint pivots need no change. Candidate QC files compile under unique model names.
"""
from pathlib import Path
import json
import numpy as np
import mujoco
import trimesh
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'build/contact_candidates'
ROBOT=json.loads((ROOT/'addon/materials/microduck/robot.txt').read_text())
MODEL=mujoco.MjModel.from_xml_path(str(ROOT/'upstream/microduck_rl/src/mjlab_microduck/robot/microduck/robot_groundcontact.xml'))
DATA=mujoco.MjData(MODEL)
DATA.qpos[7:]=ROBOT['home']
mujoco.mj_forward(MODEL,DATA)
U=ROBOT['units_per_m']

def inscribed_polygon(points,count=12):
    """Remove the least-area boundary corners; never extend past the CAD hull."""
    poly=points[ConvexHull(points).vertices].copy()
    while len(poly)>count:
        prev=np.roll(poly,1,axis=0); nxt=np.roll(poly,-1,axis=0)
        a=poly-prev; b=nxt-poly
        area=np.abs(a[:,0]*b[:,1]-a[:,1]*b[:,0])
        poly=np.delete(poly,np.argmin(area),axis=0)
    return poly

def smd(path,points):
    hull=trimesh.convex.convex_hull(points)
    with path.open('w') as stream:
        stream.write('version 1\nnodes\n0 "root" -1\nend\nskeleton\ntime 0\n0 0 0 0 0 0 0\nend\ntriangles\n')
        for face in hull.faces:
            stream.write('color_128_128_128\n')
            for index in face:
                stream.write('0 '+' '.join(f'{x:.9f}' for x in [*hull.vertices[index],*hull.vertex_normals[index],0,0])+'\n')
        stream.write('end\n')
    return hull

geom=MODEL.geom('left_foot_collision').id
mid=MODEL.geom_dataid[geom]; va=MODEL.mesh_vertadr[mid]; vc=MODEL.mesh_vertnum[mid]
cad=(MODEL.mesh_vert[va:va+vc]@DATA.geom_xmat[geom].reshape(3,3).T+DATA.geom_xpos[geom])*U
bottom=float(cad[:,2].min())
full=inscribed_polygon(cad[:,:2])
contact=inscribed_polygon(cad[cad[:,2]<=bottom+.005,:2])
variants={'outline_prism':full,'contact_prism':contact}
result={'source_revision':ROBOT['model_dir'],'units_per_m':U,'notes':[
    'Diagnostic only; no runtime or production files changed.',
    'Right collider is an exact reflection of left CAD, transformed to its own COM frame.',
    'Collision bottom equals the original CAD lowest z in home pose.',
    'outline_prism retains an inscribed 12-corner approximation to full CAD footprint; it fills rounded sole bevels.',
    'contact_prism retains only the CAD contact patch within 0.005 Source units (0.127 mm) of the lowest plane.',
    'Both extend upward 0.85 Source units into the foot; mass and inertia must still be set from robot data.'
], 'variants':{}}
OUT.mkdir(parents=True,exist_ok=True)
for variant,poly in variants.items():
    result['variants'][variant]={}
    for side in ['left','right']:
        name='ankle_'+side
        link=next(x for x in ROBOT['links'] if x['name']==name)
        ang=link['angle']; rot=Rotation.from_euler('ZYX',[ang[1],ang[0],ang[2]],degrees=True).as_matrix()
        world=np.array([[x,y if side=='left' else -y,z] for z in [bottom,bottom+.85] for x,y in poly])
        local=(world-np.array(link['pos']))@rot
        folder=OUT/f'{variant}_{name}'
        folder.mkdir(exist_ok=True)
        hull=smd(folder/'collision.smd',local)
        model=f'microduck/audit_v6feet/{variant}_{name}.mdl'
        (folder/'model.qc').write_text(f'''$modelname "{model}"
$body body "../../{name}/visual.smd"
$origin 0 0 0 -90
$surfaceprop "rubber"
$cdmaterials "models/microduck/"
$sequence idle "../../{name}/visual.smd" fps 1
$collisionmodel "collision.smd"
{{
 $mass {link['mass']:.9f}
 $masscenter 0 0 0
 $inertia 1
 $damping 0
 $rotdamping 0
}}
''')
        result['variants'][variant][name]={'vertices':local.tolist(),'world_vertices':world.tolist(),
            'model':'models/'+model,'qc':str(folder/'model.qc'),'mass':link['mass'],'mass_center':[0,0,0],
            'bottom_source_units':bottom,'thickness_source_units':.85,
            'footprint_area_source_units2':float(ConvexHull(poly).volume),
            'CAD_full_footprint_fraction':float(ConvexHull(poly).volume/ConvexHull(cad[:,:2]).volume),
            'volume_source_units3':float(hull.volume)}
payload=json.dumps(result,separators=(',',':'))
(OUT/'colliders.json').write_text(json.dumps(result,indent=2))
(OUT/'colliders.lua').write_text('return [==['+payload+']==]\n')
# Standalone snippet for the parent to inline into its own controlled spawn.
(OUT/'apply_to_data.lua').write_text('''-- Run BEFORE creating a fresh MicroDuck. Does not mutate existing physics bodies.
-- Define ContactCandidates from colliders.json, then choose one variant.
local chosen=ContactCandidates.variants.contact_prism
for _,link in ipairs(MicroDuck.Robot.links) do
 local candidate=chosen[link.name]
 if candidate then
  link.collision_vertices=candidate.vertices
  link.contact_candidate_model=candidate.model
 end
end
-- The parent spawn harness must use contact_candidate_model for each sole,
-- or call PhysicsInitConvex(points,"rubber",vector_origin) BEFORE constraints.
''')
for variant,feet in result['variants'].items():
    s=feet['ankle_left']
    print(variant,'vertices',len(s['vertices']),'volume',round(s['volume_source_units3'],6),
          'footprint_fraction',round(s['CAD_full_footprint_fraction'],4),'bottom',round(bottom,6))
print(OUT/'colliders.json')
