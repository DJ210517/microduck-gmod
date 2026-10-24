# MicroDuck for Garry's Mod

Experimental Windows 64-bit port of Pollen Robotics' physical robot and learned
policies. Walking and passive-wheel roller variants, pistol remote, player/chase
viewpoints, sit/stand, somersault, left/right kicks, and roller crouch.

**Players:** open [the download release](https://github.com/DJ210517/microduck-gmod/releases/tag/v0.1.0), download `MicroDuck_Runtime_Windows_x64.zip`, and follow
[the download/install guide](INSTALL_GUIDE.md). Subscribe on Workshop or install
the manual GMA. No Python is needed to play. Never install two addon copies.

This snapshot contains the port's code and original public ONNX policies. It
excludes compiler binaries, private test logs, gameplay snapshots and backups.
Generated Source meshes are distributed in the addon GMA; their reproducible
conversion scripts are included. Upstream robot/model sources are not vendored.

## Development

Use Python 3.14 with `requirements.txt` in `.venv`. Obtain `microduck`,
`microduck_rl` and `bam` from their upstream repositories under `upstream/`.
The policy/robot revision pins are recorded in `assets/skills_provenance.json`.
Build scripts use a local 64-bit GMod install for StudioMDL/GMad; adjust their
game path for your installation. The native build expects the Zig toolchain
described by `tools/get_native_compiler.py`. `native/mujoco_bridge/API.txt`
documents the v4 API. `tools/package.py` stages a clean addon and packs policy
JSON losslessly. `tools/build_release_bundle.py` prepares the release artifacts.

## Attribution and license

Original robot, policies and meshes: [Pollen Robotics](https://github.com/pollen-robotics/microduck)
and [microduck_rl](https://github.com/pollen-robotics/microduck_rl).
MuJoCo: https://github.com/google-deepmind/mujoco
Motor model reference: https://github.com/Rhoban/bam
Code notices: Apache-2.0 (`LICENSE-APACHE.txt`). Adapted robot meshes remain
CC BY-NC-SA 4.0, https://creativecommons.org/licenses/by-nc-sa/4.0/ . The GMA and
native ZIP retain their notices; the mesh license is not replaced by the code license.
