"""Compare the trained joint armature against the current Source tensor surrogate."""
from pathlib import Path
import json
import numpy as np
import mujoco
from scipy.spatial.transform import Rotation

root = Path(__file__).resolve().parents[1]
model_path = root / 'upstream/microduck_rl/src/mjlab_microduck/robot/microduck/robot_groundcontact.xml'
robot = json.loads((root / 'addon/materials/microduck/robot.txt').read_text())
motor = robot['motor']

def mass_matrix(model):
    data = mujoco.MjData(model)
    data.qpos[7:] = robot['home']
    mujoco.mj_forward(model, data)
    matrix = np.zeros((model.nv, model.nv))
    mujoco.mj_fullM(model, data, matrix)
    return matrix

real = mujoco.MjModel.from_xml_path(str(model_path))
real.dof_armature[6:] = motor['armature']
real_matrix = mass_matrix(real)
home_data = mujoco.MjData(real)
home_data.qpos[7:] = robot['home']
mujoco.mj_forward(real, home_data)
physical_in_source = []
for body, link in enumerate(robot['links'], 1):
    pitch, yaw, roll = link['angle']
    source_frame = Rotation.from_euler('ZYX', [yaw,pitch,roll], degrees=True).as_matrix()
    physical_frame = home_data.ximat[body].reshape(3,3)
    relative_frame = source_frame.T @ physical_frame
    tensor = relative_frame @ np.diag(real.body_inertia[body]) @ relative_frame.T * robot['mass_scale']
    physical_in_source.append({'name':link['name'], 'diagonal':np.diag(tensor).tolist(), 'tensor':tensor.tolist()})
(root/'build/audit_physical_inertia.json').write_text(json.dumps(physical_in_source,indent=2))
surrogate = mujoco.MjModel.from_xml_path(str(model_path))
surrogate.dof_armature[:] = 0
changes = []
for body in range(1, surrogate.nbody):
    quat = np.roll(surrogate.body_iquat[body], -1)
    rotation = Rotation.from_quat(quat).as_matrix()
    inertia = rotation @ np.diag(surrogate.body_inertia[body]) @ rotation.T
    if body > 1:
        joint = int(surrogate.body_jntadr[body])
        axis = surrogate.jnt_axis[joint]
        inertia += motor['armature'] * np.outer(axis, axis)
    values, axes = np.linalg.eigh(inertia)
    if np.linalg.det(axes) < 0:
        axes[:, 0] *= -1
    values = np.maximum(values, np.max(values) * .51)
    surrogate.body_inertia[body] = values
    surrogate.body_iquat[body] = np.roll(Rotation.from_matrix(axes).as_quat(), 1)
    changes.append({'body': surrogate.body(body).name, 'new_inertia': values.tolist()})
surrogate_matrix = mass_matrix(surrogate)
names = ['root_x', 'root_y', 'root_z', 'root_roll', 'root_pitch', 'root_yaw']
names += [real.joint(i).name for i in range(1, real.njnt)]
report = {'diagonal': [dict(name=name, trained=float(real_matrix[i,i]), current=float(surrogate_matrix[i,i]), ratio=float(surrogate_matrix[i,i]/real_matrix[i,i])) for i,name in enumerate(names)], 'changes': changes}
(root/'build/audit_inertia.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report['diagonal'], indent=2))
