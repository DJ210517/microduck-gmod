"""Check mocap contact-velocity bias against a very massive dynamic platform.

Offline only. The bridge source/DLL and GMod installation are not modified.
"""
from pathlib import Path
import json
import mujoco as mj
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def model(mocap, cone):
    return mj.MjModel.from_xml_string(f'''<mujoco>
      <option timestep=".005" gravity="0 0 -9.81" cone="{cone}" integrator="Euler" tolerance="1e-14" iterations="200"/>
      <worldbody>
        <body name="platform" pos="0 0 -.05" {'mocap="true"' if mocap else ''}>
          {'' if mocap else '<freejoint/>'}
          <inertial pos="0 0 0" mass="1e6" diaginertia="1e6 1e6 1e6"/>
          <geom name="platform" type="box" size="1 1 .05" condim="6" friction="1 .05 .01"/>
        </body>
        <body name="sphere" pos=".2 .1 .0995">
          <freejoint/>
          <geom name="sphere" type="sphere" size=".1" mass="1" condim="6" friction="1 .05 .01"/>
        </body>
      </worldbody></mujoco>''')


def bias(m, d, body, linear, angular):
    """Apply full rigid proxy velocity, unlike tangential-only surfacevel."""
    for c in d.contact:
        if c.efc_address < 0:
            continue
        if m.geom_bodyid[c.geom[0]] == body:
            sign = -1
        elif m.geom_bodyid[c.geom[1]] == body:
            sign = 1
        else:
            continue
        point = linear + np.cross(angular, c.pos - d.xipos[body])
        cs = sign * np.r_[c.frame.reshape(3, 3) @ point,
                          c.frame.reshape(3, 3) @ angular]
        if c.dim == 1 or m.opt.cone == mj.mjtCone.mjCONE_ELLIPTIC:
            delta = cs[:c.dim]
        else:
            delta = np.array([cs[0] + sign_ * c.friction[k - 1] * cs[k]
                              for k in range(1, c.dim) for sign_ in [1, -1]])
        rows = np.arange(c.efc_address, c.efc_address + len(delta))
        d.efc_vel[rows] += delta
        d.efc_aref[rows] -= d.efc_KBIP[rows, 1] * delta


def main():
    results = []
    for cone in ['pyramidal', 'elliptic']:
        for name, linear, angular in [
            ('translation', [.2, -.1, 0], [0, 0, 0]),
            ('upward', [0, 0, .2], [0, 0, 0]),
            ('rotation', [0, 0, 0], [.2, -.1, .3]),
            ('combined', [.2, -.1, .15], [.2, -.1, .3]),
        ]:
            linear, angular = np.array(linear), np.array(angular)
            fixed, dynamic = model(True, cone), model(False, cone)
            a, b = mj.MjData(fixed), mj.MjData(dynamic)
            b.qvel[:3], b.qvel[3:6] = linear, angular
            # Remove gravity from the reference platform's acceleration. An
            # externally driven proxy is kinematic, so it does not free-fall.
            b.xfrc_applied[1, :3] = -dynamic.opt.gravity * dynamic.body_mass[1]
            mj.mj_step1(fixed, a)
            mj.mj_step1(dynamic, b)
            bias(fixed, a, 1, linear, angular)
            vel_error = float(np.max(np.abs(a.efc_vel - b.efc_vel)))
            aref_error = float(np.max(np.abs(a.efc_aref - b.efc_aref)))
            mj.mj_step2(fixed, a)
            mj.mj_step2(dynamic, b)
            qacc_error = float(np.max(np.abs(a.qacc[-6:] - b.qacc[-6:])))
            results.append(dict(cone=cone, case=name, contact_velocity_error=vel_error,
                                reference_acceleration_error=aref_error,
                                sphere_acceleration_error=qacc_error))
            assert vel_error < 1e-12 and aref_error < 1e-10, results[-1]
            assert qacc_error < 1e-3, results[-1]
    report = dict(passed=True, cases=results,
                  implementation='After mj_step1, efc_vel += delta and efc_aref -= B*delta; Euler integrator only')
    (ROOT / 'build/audit_mocap_velocity.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
