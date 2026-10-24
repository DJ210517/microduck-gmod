"""Stage official roller physics, neural networks, and matching Source meshes."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,urllib.request
from concurrent.futures import ThreadPoolExecutor
import mujoco,numpy as np,trimesh
import build_assets as B
import build_mujoco_assets as A
from export_policies import extract,REVISION

ROOT=B.ROOT;ROBOT=B.ROBOT;OUT=ROOT/'build/roller_runtime'
JOINTS=['left_hip_yaw','left_hip_roll','left_hip_pitch','left_knee','left_ankle','neck_pitch','head_pitch','head_yaw','head_roll','right_hip_yaw','right_hip_roll','right_hip_pitch','right_knee','right_ankle']
WHEELS=['passive_LF_wheel','passive_LR_wheel','passive_RF_wheel','passive_RR_wheel']
EXPECTED={'roller':'cf05651d2708a2f9364212e86b866c97a70ace8131c492500105e8f28bf99afd','roller_crouch':'a1a084be240469c76ac9d3fa44d4792f16d4b1da60398b3ecd3cfc5e2244d990'}

def policies():
    result={}
    for name,file in [('roller','roller.onnx'),('roller_crouch','roller_crouch.onnx')]:
        path=ROOT/'assets'/file
        url=f'https://huggingface.co/pollen-robotics/microduck-policies/resolve/{REVISION}/{file}'
        if not path.exists():path.write_bytes(urllib.request.urlopen(url).read())
        weights,meta=extract(path)
        assert weights['sha256']==EXPECTED[name]
        assert meta['joint_names'].split(',')==JOINTS
        assert len(meta['default_joint_pos'].split(','))==14
        (ROOT/f'addon/lua/microduck/policy_{name}_data.lua').write_text('return [==['+json.dumps(weights,separators=(',',':'))+']==]\n')
        result[name]={'url':url,'sha256':weights['sha256'],'metadata':meta,'action_scale':.8}
    (ROOT/'addon/data_static/microduck_skills/roller_provenance.json').write_text(json.dumps({'revision':REVISION,'policies':result,'wheel_bearing_frictionloss':.003,'controller':'Four wheels remain passive; original14 joint motor targets, action scale0.8; command3 is heading error.'},indent=2))
    return result

def build(render=True):
    OUT.mkdir(parents=True,exist_ok=True)
    tree=A.prepare.prepare_scene(ROBOT/'scene_rollers.xml')
    assets=OUT/'assets';assets.mkdir(exist_ok=True)
    for mesh in tree.findall('./asset/mesh'):
        source=Path(mesh.attrib['file']);target=assets/source.name;shutil.copy2(source,target);mesh.set('file',target.as_posix())
    A.prepare.write_scene(tree,OUT/'base.xml')
    m=mujoco.MjModel.from_xml_path(str(ROBOT/'scene_rollers.xml'));d=mujoco.MjData(m)
    assert (m.nq,m.nv)==(25,24)
    for name,value in zip(JOINTS,B.HOME):d.qpos[m.joint(name).qposadr[0]]=value
    mujoco.mj_forward(m,d)
    ids=[m.body('trunk_base').id]+[int(m.jnt_bodyid[m.joint(n).id]) for n in JOINTS+WHEELS]
    links=[];folders=[]
    for i,body in enumerate(ids,1):
        name=m.body(body).name;rotation=d.xmat[body].reshape(3,3);pieces=[]
        for g in range(m.ngeom):
            if m.geom_bodyid[g]!=body or m.geom_group[g]!=2 or m.geom_type[g]!=mujoco.mjtGeom.mjGEOM_MESH:continue
            mid=m.geom_dataid[g];va,vc=m.mesh_vertadr[mid],m.mesh_vertnum[mid];fa,fc=m.mesh_faceadr[mid],m.mesh_facenum[mid]
            world=m.mesh_vert[va:va+vc]@d.geom_xmat[g].reshape(3,3).T+d.geom_xpos[g]
            mesh=trimesh.Trimesh(vertices=(world-d.xipos[body])@rotation*B.U,faces=m.mesh_face[fa:fa+fc],process=True)
            if len(mesh.faces)>6000:mesh=mesh.simplify_quadric_decimation(face_count=6000)
            mid=m.geom_matid[g];rgba=m.mat_rgba[mid] if mid>=0 else m.geom_rgba[g]
            mat='md_roller_'+str(mid)
            material=ROOT/f'addon/materials/models/microduck/{mat}.vmt'
            material.write_text('"VertexLitGeneric"\n{\n "$basetexture" "color/white"\n "$color2" "['+' '.join(str(float(x)) for x in rgba[:3])+']"\n "$phong" "1"\n "$phongexponent" "35"\n "$phongboost" "0.25"\n}\n')
            mesh=trimesh.graph.smooth_shade(mesh,angle=np.radians(40),facet_minarea=30)
            pieces.append((mesh.vertices,mesh.faces,mat))
        assert pieces,name
        while sum(len(p[0]) for p in pieces)>55000:
            smaller=[]
            for v,f,mat in pieces:
                mesh=trimesh.Trimesh(vertices=v,faces=f,process=True)
                if len(mesh.faces)>24:mesh=mesh.simplify_quadric_decimation(face_count=max(24,int(len(mesh.faces)*.7)))
                mesh=trimesh.graph.smooth_shade(mesh,angle=np.radians(40),facet_minarea=30)
                smaller.append((mesh.vertices,mesh.faces,mat))
            pieces=smaller
        links.append({'name':name,'body_id':i,'model':f'models/microduck/rollers_v1/{name}.mdl','body_to_model':np.eye(3).tolist()})
        if render:
            folder=ROOT/'build/roller_models'/name;folder.mkdir(parents=True,exist_ok=True);folders.append(folder)
            B.smd(folder/'visual.smd',pieces)
            hull=trimesh.convex.convex_hull(np.vstack([p[0] for p in pieces]))
            # Selectable render hull only; actual collisions retain upstream MJCF.
            verts=hull.vertices.copy()
            for axis in range(3):
                width=np.ptp(verts[:,axis])
                if width<.85:verts[:,axis]=(verts[:,axis]-np.mean(verts[:,axis]))*(.85/max(width,1e-8))
            hull=trimesh.convex.convex_hull(verts)
            B.smd(folder/'collision.smd',[(hull.vertices,hull.faces,'md_roller_0')])
            (folder/'model.qc').write_text(f'$modelname "microduck/rollers_v1/{name}.mdl"\n$body body "visual.smd"\n$origin 0 0 0 -90\n$surfaceprop "rubber"\n$cdmaterials "models/microduck/"\n$sequence idle "visual.smd" fps 1\n$collisionmodel "collision.smd"\n{{\n $mass 1\n $masscenter 0 0 0\n}}\n')
    render_data={'units_per_m':B.U,'home':B.HOME.tolist(),'links':links}
    (OUT/'robot.json').write_text(json.dumps(render_data))
    (OUT/'render_data.lua').write_text('return util.JSONToTable([==['+json.dumps(render_data,separators=(',',':'))+']==])\n')
    info={'nq':m.nq,'nv':m.nv,'robot_links':19,'units_per_m':B.U,'home':B.HOME.tolist(),'render_links':links}
    (OUT/'manifest.json').write_text(json.dumps(info,indent=2))
    portable=A.stage_portable(OUT,ROOT/'addon','_roller')
    if render:
        def compile_one(folder):
            proc=subprocess.run([str(B.GAME.parent/'bin/studiomdl.exe'),'-game',str(B.GAME),str(folder/'model.qc')],cwd=folder,capture_output=True,text=True)
            (folder/'compile.log').write_text(proc.stdout+proc.stderr)
            assert proc.returncode==0,(folder,proc.stdout[-3000:])
            assert (B.GAME/'models/microduck/rollers_v1'/f'{folder.name}.mdl').exists(),folder
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(compile_one,folders))
        shutil.copytree(B.GAME/'models/microduck/rollers_v1',ROOT/'addon/models/microduck/rollers_v1',dirs_exist_ok=True)
    return {'scene':str(OUT/'base.xml'),'portable':portable,'policies':policies(),'body_order':[m.body(b).name for b in ids]}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--no-render',action='store_true');a=p.parse_args()
    report=build(not a.no_render);(ROOT/'build/roller_assets.json').write_text(json.dumps(report,indent=2));print(json.dumps({'bodies':report['body_order'],'policy_hashes':{k:v['sha256'] for k,v in report['policies'].items()}}))
