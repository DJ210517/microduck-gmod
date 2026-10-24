"""Convert upstream MJCF links and the unchanged ONNX MLP for Source/GMod."""
from pathlib import Path
import json, hashlib, subprocess, shutil, sys
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import mujoco
import onnx
from onnx import numpy_helper
from scipy.spatial.transform import Rotation
import trimesh

ROOT = Path(__file__).resolve().parents[1]
GAME = Path(r'E:\SteamLibrary\steamapps\common\GarrysMod\garrysmod')
ADDON = ROOT/'addon'
BUILD = ROOT/'build'
ROBOT = ROOT/'upstream/microduck_rl/src/mjlab_microduck/robot/microduck'
U = 100/2.54
MASS_SCALE = 100.0  # Uniform scaling preserves dynamics; keeps small links above Source's mass floor.
REVISION = 'detailed_v5'
HOME = np.array([0,-.0873,-.4579,-.0049,.4530,.3491,.3491,0,0,0,.0873,.4579,.0049,-.4530])

def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj,separators=(',',':')),encoding='utf-8')

def write_lua_data(name,obj):
    payload=json.dumps(obj,separators=(',',':'))
    (ADDON/'lua/microduck'/f'{name}_data.lua').write_text('return [==['+payload+']==]\n',encoding='utf-8')

def export_policy():
    model=onnx.load(ROOT/'assets/velstand.onnx')
    assert [n.op_type for n in model.graph.node] == ['Sub','Div','Gemm','Elu','Gemm','Elu','Gemm','Elu','Gemm']
    arrays={x.name:numpy_helper.to_array(x) for x in model.graph.initializer}
    result={'sha256':hashlib.sha256((ROOT/'assets/velstand.onnx').read_bytes()).hexdigest(),
            'mean':arrays['obs_normalizer._mean'].ravel().tolist(),
            'divisor':arrays['onnx::Div_24'].ravel().tolist(), 'layers':[]}
    for n in model.graph.node:
        if n.op_type != 'Gemm': continue
        attrs={a.name:onnx.helper.get_attribute_value(a) for a in n.attribute}
        assert attrs.get('transB',0)==1 and attrs.get('alpha',1)==1 and attrs.get('beta',1)==1
        w,b=arrays[n.input[1]], arrays[n.input[2]]
        result['layers'].append({'inputs':int(w.shape[1]),'outputs':int(w.shape[0]),'w':w.ravel().tolist(),'b':b.tolist()})
    write_json(ADDON/'materials/microduck/policy.txt',result)
    write_lua_data('policy',result)
    write_json(BUILD/'policy_metadata.json',{p.key:p.value for p in model.metadata_props})
    return result

def smd(path, pieces):
    with path.open('w') as f:
        f.write('version 1\nnodes\n0 "root" -1\nend\nskeleton\ntime 0\n0 0 0 0 0 0 0\nend\ntriangles\n')
        for vertices,faces,material in pieces:
            mesh=trimesh.Trimesh(vertices=vertices,faces=faces,process=False)
            normals=mesh.vertex_normals
            for face in faces:
                f.write(material+'\n')
                for index in face:
                    v,normal=vertices[index],normals[index]
                    f.write('0 '+' '.join(f'{x:.8f}' for x in [*v,*normal,0,0])+'\n')
        f.write('end\n')

def build_robot():
    m=mujoco.MjModel.from_xml_path(str(ROBOT/'robot_groundcontact.xml'))
    d=mujoco.MjData(m)
    assert m.nbody==16 and m.nu==14
    d.qpos[7:]=HOME
    mujoco.mj_forward(m,d)
    frames={}; moments={}
    motor=json.loads((ROOT/'upstream/bam/bam/params/xl330/m6.json').read_text())
    for i in range(1,m.nbody):
        body_rotation=d.xmat[i].reshape(3,3)
        inertia_rotation=Rotation.from_quat(np.roll(m.body_iquat[i],-1)).as_matrix()
        tensor=inertia_rotation@np.diag(m.body_inertia[i])@inertia_rotation.T
        if i>1:
            # Source has no generalized-coordinate armature. Approximate the
            # identified gearbox rotor as added child-body axial inertia. This
            # is a physical tensor approximation, never a world-space support.
            j=int(m.body_jntadr[i]); axis=m.jnt_axis[j]
            tensor+=motor['armature']*np.outer(axis,axis)
        eig,axes=np.linalg.eigh(tensor)
        if np.linalg.det(axes)<0: axes[:,0]*=-1
        frames[i]=body_rotation@axes
        moments[i]=eig
    positions={i:d.xipos[i].copy() for i in range(1,m.nbody)}
    # Each link's model frame is its COM principal inertia frame.
    robot={'units_per_m':U,'mass_scale':MASS_SCALE,'model_dir':'microduck/'+REVISION,'motor':motor,'home':HOME.tolist(),'links':[],'joints':[]}
    materials={}
    min_z=1e9
    for i in range(1,m.nbody):
        name=m.body(i).name
        pieces=[]; collision=[]; render_meshes=[]
        for g in range(m.ngeom):
            if m.geom_bodyid[g]!=i or m.geom_type[g]!=mujoco.mjtGeom.mjGEOM_MESH: continue
            meshid=m.geom_dataid[g]
            va,vc=m.mesh_vertadr[meshid],m.mesh_vertnum[meshid]
            fa,fc=m.mesh_faceadr[meshid],m.mesh_facenum[meshid]
            v=m.mesh_vert[va:va+vc].copy()
            world=v@d.geom_xmat[g].reshape(3,3).T+d.geom_xpos[g]
            v=(world-positions[i])@frames[i]*U
            faces=m.mesh_face[fa:fa+fc].copy()
            if m.geom_group[g]==2:
                matid=m.geom_matid[g]
                rgb=m.mat_rgba[matid,:3] if matid>=0 else m.geom_rgba[g,:3]
                source_mat=m.material(matid).name if matid>=0 else 'generic'
                mat='md_'+source_mat.removesuffix('_material')
                materials[mat]={'rgb':rgb.tolist(),'part':source_mat}
                # MuJoCo/STL data contain duplicated facet vertices. Weld before
                # simplification; otherwise disconnected facets cannot collapse.
                mesh=trimesh.Trimesh(vertices=v,faces=faces,process=True)
                render_meshes.append((mesh,mat))
                min_z=min(min_z,float(world[:,2].min()))
            elif m.geom_contype[g] & 1:
                collision.append(v)
        assert render_meshes,name
        # Preserve flat panel edges and round housings. Give large assemblies a
        # shared vertex budget instead of discarding the same amount per part.
        face_limit=12000
        while True:
            pieces=[]
            for original,mat in render_meshes:
                mesh=original
                if len(mesh.faces)>face_limit:
                    mesh=mesh.simplify_quadric_decimation(face_count=face_limit)
                mesh=trimesh.graph.smooth_shade(mesh,angle=np.radians(40),facet_minarea=30)
                pieces.append((mesh.vertices,mesh.faces,mat))
            if sum(len(p[0]) for p in pieces)<55000: break
            face_limit=int(face_limit*.8)
            assert face_limit>1000,name
        # Use the convex hull of the curated floor-contact geometry. Internal links
        # get a visual hull but all robot self-collisions are disabled at runtime.
        hull=trimesh.convex.convex_hull(np.vstack(collision or [p[0] for p in pieces]))
        if len(hull.faces)>200:
            hull=hull.simplify_quadric_decimation(face_count=200).convex_hull
        # StudioMDL rejects sub-inch slivers. Thicken only the narrow axis of
        # the two leg housings, and retain the explicitly exported COM frame.
        if name in {'leg','leg_2'}:
            vertices=hull.vertices.copy()
            axis=int(np.argmin(np.ptp(vertices,axis=0)))
            mid=(vertices[:,axis].min()+vertices[:,axis].max())*.5
            vertices[:,axis]=mid+(vertices[:,axis]-mid)*(.85/np.ptp(vertices[:,axis]))
            hull=trimesh.convex.convex_hull(vertices)
        folder=BUILD/name; folder.mkdir(parents=True,exist_ok=True)
        smd(folder/'visual.smd',pieces)
        smd(folder/'collision.smd',[(hull.vertices,hull.faces,'color_128_128_128')])
        (folder/'model.qc').write_text(f'''$modelname "microduck/{REVISION}/{name}.mdl"
$body body "visual.smd"
$origin 0 0 0 -90
$surfaceprop "rubber"
$cdmaterials "models/microduck/"
$sequence idle "visual.smd" fps 1
$collisionmodel "collision.smd"
{{
 $mass {float(m.body_mass[i])*MASS_SCALE:.9f}
 $masscenter 0 0 0
 $inertia 1
 $damping 0
 $rotdamping 0
}}
''')
        # Euler angles from proper x/y/z basis (Source local Y is left).
        r=frames[i]
        yaw,pitch,roll=Rotation.from_matrix(r).as_euler('ZYX')
        assert np.max(np.abs(Rotation.from_euler('ZYX',[yaw,pitch,roll]).as_matrix()-r))<1e-8
        robot['links'].append({'name':name,'pos':(positions[i]*U).tolist(),
            'collision_vertices':hull.vertices.tolist(),
            'angle':np.rad2deg([pitch,yaw,roll]).tolist(),
            'mass':float(m.body_mass[i])*MASS_SCALE,
            'inertia':(moments[i]*MASS_SCALE).tolist(),
            'trunk_axes':[frames[i].T[:,k].tolist() for k in range(3)] if i==1 else None})
    for j in range(1,m.njnt):
        c=int(m.jnt_bodyid[j]); p=int(m.body_parentid[c]); axis=d.xaxis[j].copy(); pivot=d.xanchor[j].copy()
        ref=np.cross(axis,[1,0,0] if abs(axis[0])<.8 else [0,1,0]); ref/=np.linalg.norm(ref)
        robot['joints'].append({'name':m.joint(j).name,'parent':p,'child':c,
            'pivot_p':((pivot-positions[p])@frames[p]*U).tolist(),
            'pivot_c':((pivot-positions[c])@frames[c]*U).tolist(),
            'axis_p':(axis@frames[p]).tolist(),'axis_c':(axis@frames[c]).tolist(),
            'ref_p':(ref@frames[p]).tolist(),'ref_c':(ref@frames[c]).tolist(),
            'range':m.jnt_range[j].tolist(),'home':float(HOME[j-1])})
    robot['floor_offset']=float(-min_z*U+.03)
    write_json(ADDON/'materials/microduck/robot.txt',robot)
    write_lua_data('robot',robot)
    for mat,info in materials.items():
        rgb,part=info['rgb'],info['part']
        exponent,boost=35,.28
        if any(x in part for x in ['sole','soft_mouth','jaw_soft']): exponent,boost=8,.06
        elif 'lens' in part: exponent,boost=120,1.5
        elif any(x in part for x in ['bearing','plate','leg_material','neck_material']): exponent,boost=70,.7
        elif any(x in part for x in ['jaw_material','foot_','ankle_']): exponent,boost=45,.42
        p=ADDON/'materials/models/microduck'/f'{mat}.vmt'
        p.write_text('"VertexLitGeneric"\n{\n "$basetexture" "color/white"\n "$color2" "['+' '.join(f'{x:.5f}' for x in rgb)+f']"\n "$phong" "1"\n "$phongexponent" "{exponent}"\n "$phongboost" "{boost}"\n "$phongfresnelranges" "[0.15 0.4 1]"\n "$halflambert" "1"\n}}\n')
    return robot

def compile_models(robot):
    compiler=GAME.parent/'bin/studiomdl.exe'
    def compile_one(link):
        folder=BUILD/link['name']
        log=subprocess.run([str(compiler),'-game',str(GAME),str(folder/'model.qc')],cwd=folder,capture_output=True,text=True)
        (folder/'compile.log').write_text(log.stdout+log.stderr)
        if log.returncode or not (GAME/'models/microduck'/REVISION/f"{link['name']}.mdl").exists():
            raise RuntimeError(log.stdout+log.stderr)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(compile_one,robot['links']))
    shutil.copytree(GAME/'models/microduck',ADDON/'models/microduck',dirs_exist_ok=True)

if __name__=='__main__':
    export_policy()
    robot=build_robot()
    compile_models(robot)
    print('Built',len(robot['links']),'links,',len(robot['joints']),'joints')

