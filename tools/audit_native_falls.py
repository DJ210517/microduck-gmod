"""Read-only offline drop tests using the shipping native DLL and captured map.

Separates missing collision geometry from discrete-contact tunneling. Never
changes or controls GMod, its installed files, or the shipping DLL.
"""
from pathlib import Path
import ctypes as C
import json
import sys
import mujoco as mj
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'native/mujoco_bridge'))
from test_bridge import DLL, HOME, array, check, state

ORIGIN = np.array([584.6844482421875, 258.7928466796875, -12287.96875])
U = 100 / 2.54
SCENES = {
    'old_prisms': Path('E:/SteamLibrary/steamapps/common/GarrysMod/garrysmod/data/microduck_mj/world_74.xml'),
    'true_solids': ROOT / 'build/mujoco_runtime/audit_world_convex.xml',
}


def main():
    check(DLL.md_load(str(ROOT / '.venv/Lib/site-packages/mujoco/mujoco.dll').encode()))
    rows = []
    for name, scene in SCENES.items():
        m = mj.MjModel.from_xml_path(str(scene));d = mj.MjData(m);mj.mj_forward(m, d)
        for source_x in [1200, 1500, 2000, 3000]:
            xy = [(source_x - ORIGIN[0]) / U, 0]
            ray_id = np.array([-1], dtype=np.int32)
            ray_distance = mj.mj_ray(m, d, np.array([*xy, .125]), np.array([0.,0.,-1.]),
                                     None, True, -1, ray_id)
            h = check(DLL.md_create(str(scene).encode()))
            check(DLL.md_set_motors(h, 0))
            check(DLL.md_reset(h, array([*xy,.125]), array([1,0,0,0])))
            first_contact = None;peak_contacts = 0;min_z = 1e9
            frames = []
            for step in range(700):
                check(DLL.md_step(h,.005,array(HOME)))
                s = state(h);n = DLL.md_contact_count(h)
                if n and first_contact is None:first_contact = dict(t=s.simtime,z=s.root_position[2],vz=s.root_velocity[2])
                peak_contacts = max(peak_contacts,n);min_z=min(min_z,s.root_position[2])
                if step % 10 == 0:frames.append(dict(t=s.simtime,pos=list(s.root_position),v=list(s.root_velocity),contacts=n))
            end = state(h);check(DLL.md_destroy(h))
            rows.append(dict(scene=name,source_x=source_x,ray_distance=ray_distance,ray_geom=int(ray_id[0]),
                             first_contact=first_contact,peak_contacts=peak_contacts,min_root_z=min_z,
                             final_position=list(end.root_position),final_velocity=list(end.root_velocity),frames=frames))
    DLL.md_close_all()
    report=dict(origin=ORIGIN.tolist(),ground_relative_z=(-12800-ORIGIN[2])/U,tests=rows)
    (ROOT/'build/audit_native_falls.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({**report,'tests':[{k:v for k,v in row.items() if k!='frames'} for row in rows]},indent=2))


if __name__ == '__main__':main()
