"""Stage collision-exact MicroDuck MuJoCo assets; never writes to the game."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import xml.etree.ElementTree as ET

import mujoco
import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prepare_scene', ROOT / 'native/mujoco_bridge/prepare_scene.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def build(output: Path, terrain: Path | None = None) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    staged_meshes = output / 'assets'
    staged_meshes.mkdir(exist_ok=True)
    tree = prepare.prepare_scene(terrain=terrain)
    hashes = {}
    for mesh in tree.findall('./asset/mesh'):
        if not mesh.get('file'):
            continue
        source = Path(mesh.attrib['file'])
        target = staged_meshes / source.name
        # Name collisions must fail, not quietly substitute a different terrain mesh.
        if target.name in hashes and hashes[target.name] != hashlib.sha256(source.read_bytes()).hexdigest():
            raise ValueError(f'Conflicting mesh filename: {target.name}')
        shutil.copy2(source, target)
        hashes[target.name] = hashlib.sha256(target.read_bytes()).hexdigest()
        mesh.set('file', target.as_posix())
    scene = output / 'base.xml'
    prepare.write_scene(tree, scene)
    robot_source = ROOT / 'addon/materials/microduck/robot.txt'
    robot = json.loads(robot_source.read_text())
    shutil.copy2(robot_source, output / 'robot.json')
    for filename in ('scene.xml', 'robot_groundcontact.xml'):
        shutil.copy2(prepare.DEFAULT_SCENE.parent / filename, output / ('upstream_' + filename))

    original = mujoco.MjModel.from_xml_path(str(prepare.DEFAULT_SCENE))
    model = mujoco.MjModel.from_xml_path(str(scene))
    assert (model.nq, model.nv, model.nu, model.nmocap, model.nbody) == (21, 20, 14, 32, 48)
    assert model.njnt == original.njnt == 15
    for field in ('body_mass', 'body_inertia', 'body_ipos', 'body_iquat', 'body_pos', 'body_quat'):
        np.testing.assert_allclose(getattr(model, field)[:16], getattr(original, field)[:16], atol=1e-14)
    for field in ('dof_damping', 'dof_frictionloss', 'dof_armature', 'jnt_range',
                  'actuator_gainprm', 'actuator_biasprm', 'actuator_forcerange'):
        np.testing.assert_allclose(getattr(model, field), getattr(original, field), atol=1e-14)
    expected_names = [link['name'] for link in robot['links']]
    assert [model.body(i).name for i in range(1, 16)] == expected_names
    assert model.geom('left_foot_collision').contype == 1
    assert model.geom('right_foot_collision').contype == 1
    assert 'floor' not in [model.geom(i).name for i in range(model.ngeom)]
    assert not any(int(t) == int(mujoco.mjtGeom.mjGEOM_PLANE) for t in model.geom_type)

    data = mujoco.MjData(model)
    data.qpos[7:] = robot['home']
    mujoco.mj_forward(model, data)
    render_links = []
    for i, link in enumerate(robot['links'], 1):
        pitch, yaw, roll = link['angle']
        source_frame = Rotation.from_euler('ZYX', [yaw, pitch, roll], degrees=True).as_matrix()
        body_to_model = data.xmat[i].reshape(3, 3).T @ source_frame
        render_links.append({'name': link['name'], 'body_id': i,
                             'model': f"models/{robot['model_dir']}/{link['name']}.mdl",
                             'body_to_model': body_to_model.tolist()})
    manifest = {
        'scene': str(scene), 'nq': model.nq, 'nv': model.nv, 'nu': model.nu,
        'robot_links': 15, 'mocap_proxies': 32, 'physics_geoms': model.ngeom - 32,
        'units_per_m': robot['units_per_m'], 'home': robot['home'],
        'timestep': model.opt.timestep, 'meshes_sha256': hashes,
        'source_model_directory': robot['model_dir'], 'render_links': render_links,
        'render_formula': 'position = origin + xipos * units_per_m; rotation = xmat @ body_to_model',
        'world_asset_marker': '<!--MICRODUCK_WORLD_ASSETS-->',
        'world_geom_marker': '<!--MICRODUCK_WORLD_GEOMS-->',
        'terrain': str(terrain.resolve()) if terrain else None,
        'proxy_initial_state': 'Parked at z=-1000m, compiled collision masks 1; bridge disables after create',
        'verification': 'Original masses, COM/inertia frames, poses, joint ranges, armature/damping/friction and actuator parameters identical',
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    payload = json.dumps({'units_per_m': robot['units_per_m'], 'home': robot['home'], 'links': render_links}, separators=(',', ':'))
    (output / 'render_data.lua').write_text('return util.JSONToTable([==[' + payload + ']==])\n', encoding='utf-8')
    return manifest


def stl_to_msh(source: Path) -> bytes:
    """Losslessly retain binary STL float32 vertices in MuJoCo's MSH format.

    MSH has an explicit content type supported by the core loader, so a .dat
    extension works with both the GMAD whitelist and Lua file.Write.
    """
    raw = source.read_bytes()
    if len(raw) < 84:
        raise ValueError(f'Not a binary STL: {source}')
    count = struct.unpack_from('<I', raw, 80)[0]
    if len(raw) != 84 + count * 50:
        raise ValueError(f'Unexpected binary STL size: {source}')
    dtype = np.dtype([('normal', '<f4', (3,)), ('vertices', '<f4', (3, 3)), ('attribute', '<u2')])
    triangles = np.ndarray(count, dtype=dtype, buffer=raw, offset=84)
    vertices, inverse = np.unique(triangles['vertices'].reshape(-1, 3), axis=0, return_inverse=True)
    faces = inverse.astype('<i4').reshape(-1, 3)
    return (struct.pack('<4i', len(vertices), 0, 0, len(faces)) +
            vertices.astype('<f4').tobytes() + faces.tobytes())


def stage_portable(output: Path, addon: Path, variant: str = '') -> dict:
    """Create mounted source assets; no install, native loading, or packaging."""
    output, addon = output.resolve(), addon.resolve()
    assert variant in ('', '_roller')
    payload = addon / ('data_static/microduck_mj' + variant)
    (payload / 'assets').mkdir(parents=True, exist_ok=True)
    (payload / 'licenses').mkdir(exist_ok=True)
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    tree = ET.parse(output / 'base.xml', parser=parser)
    for mesh in tree.getroot().findall('./asset/mesh'):
        if not mesh.get('file'):
            continue
        source = Path(mesh.attrib['file'])
        if source.suffix.lower() != '.stl':
            raise ValueError(f'Portable conversion currently expects STL: {source}')
        relative = 'assets/' + source.stem.lower() + '.dat'
        (payload / relative).write_bytes(stl_to_msh(source))
        mesh.set('file', relative)
        mesh.set('content_type', 'model/vnd.mujoco.msh')
    prepare.write_scene(tree.getroot(), payload / 'base.xml')
    shutil.copy2(output / 'robot.json', payload / 'robot.json')
    info = json.loads((output / 'manifest.json').read_text())
    render = {'units_per_m': info['units_per_m'], 'home': info['home'], 'links': info['render_links']}
    (payload / 'render.json').write_text(json.dumps(render, separators=(',', ':')), encoding='utf-8')
    lua = addon / 'lua/microduck'
    lua.mkdir(parents=True, exist_ok=True)
    shutil.copy2(output / 'render_data.lua', lua / ('mujoco' + variant + '_render_data.lua'))
    distribution = Path(mujoco.__file__).parent.parent / f'mujoco-{mujoco.__version__}.dist-info/licenses'
    for original, name in [('LICENSE', 'mujoco_license.txt'), ('LICENSES_THIRD_PARTY.md', 'mujoco_third_party.txt')]:
        shutil.copy2(distribution / original, payload / 'licenses' / name)
    shutil.copy2(ROOT / 'addon/LICENSE-APACHE.txt', payload / 'licenses/microduck_license.txt')
    source_model = mujoco.MjModel.from_xml_path(str(output / 'base.xml'))
    portable_model = mujoco.MjModel.from_xml_path(str(payload / 'base.xml'))
    assert (portable_model.nq, portable_model.nv, portable_model.nu, portable_model.nmocap) == (source_model.nq, source_model.nv, source_model.nu, 32)
    for field in ('body_mass', 'body_inertia', 'body_ipos', 'body_iquat', 'dof_armature'):
        np.testing.assert_array_equal(getattr(source_model, field), getattr(portable_model, field))
    # Mesh compilation recenters/reorients vertices. Compare physical points in
    # the world frame instead of assuming identical internal mesh ordering.
    from scipy.spatial import cKDTree
    a, b = mujoco.MjData(source_model), mujoco.MjData(portable_model)
    mujoco.mj_forward(source_model, a)
    mujoco.mj_forward(portable_model, b)
    worst = 0.
    for geom in range(source_model.ngeom):
        if source_model.geom_type[geom] != mujoco.mjtGeom.mjGEOM_MESH:
            continue
        points = []
        for model, data in ((source_model, a), (portable_model, b)):
            mesh = model.geom_dataid[geom]
            start, count = model.mesh_vertadr[mesh], model.mesh_vertnum[mesh]
            points.append(model.mesh_vert[start:start+count] @ data.geom_xmat[geom].reshape(3, 3).T + data.geom_xpos[geom])
        for source, target in (points, points[::-1]):
            worst = max(worst, float(cKDTree(target).query(source)[0].max()))
    assert worst < 2e-7, worst
    files = [{'path': p.relative_to(payload).as_posix(), 'bytes': p.stat().st_size,
              'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
             for p in sorted(payload.rglob('*')) if p.is_file() and p.name != 'manifest.json']
    content_id = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:16]
    manifest = {'schema_version': 1, 'content_id': content_id, 'mujoco_version': mujoco.__version__,
                'base_scene': 'base.xml', 'mesh_encoding': 'MuJoCo MSH with model/vnd.mujoco.msh',
                'nq': int(source_model.nq), 'nv': int(source_model.nv), 'robot_links': info['robot_links'], 'actuators': 14, 'mocap_proxies': 32,
                'units_per_m': info['units_per_m'], 'max_mesh_conversion_error_m': worst, 'files': files}
    (payload / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/mujoco_runtime')
    parser.add_argument('--terrain', type=Path)
    parser.add_argument('--stage-addon', action='store_true', help='Also create portable data_static payload under addon/')
    parser.add_argument('--addon', type=Path, default=ROOT / 'addon')
    args = parser.parse_args()
    result = build(args.output, args.terrain)
    if args.stage_addon:
        portable = stage_portable(args.output, args.addon)
        print(json.dumps({'portable_content_id': portable['content_id'], 'files': len(portable['files']),
                          'mesh_conversion_error_m': portable['max_mesh_conversion_error_m']}))
    print(json.dumps({key: result[key] for key in ('scene', 'nq', 'nv', 'nu', 'robot_links', 'mocap_proxies', 'physics_geoms', 'verification')}, indent=2))
