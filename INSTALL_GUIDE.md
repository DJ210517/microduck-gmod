# MicroDuck for Garry's Mod — download and install

Windows 64-bit • Experimental single-player release • Walking and roller variants

You need **two parts**: the Workshop addon and the matching native runtime ZIP.
The Workshop download includes the robot models, remote, collision assets and
all seven learned policies. The companion ZIP supplies the native physics engine.

## 1. Download

- Open the [v0.1.0 download page](https://github.com/DJ210517/microduck-gmod/releases/tag/v0.1.0).
- Download [MicroDuck_Runtime_Windows_x64.zip](https://github.com/DJ210517/microduck-gmod/releases/download/v0.1.0/MicroDuck_Runtime_Windows_x64.zip).
- While the Workshop item is being prepared, also download
  [microduck_real_ai.gma](https://github.com/DJ210517/microduck-gmod/releases/download/v0.1.0/microduck_real_ai.gma)
  and follow **Manual install without Workshop** below.
- Once published, subscribing to **MicroDuck — Real AI Walking & Roller Skates**
  replaces the manual GMA download. The runtime ZIP is still required.
- Install the latest supported **Microsoft Visual C++ v14 x64 Redistributable**
  from [Microsoft's official download page](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist).

You do **not** need Python, ONNX Runtime, a GPU, or the original robotics repository.
GitHub's automatically generated "Source code" archives are for developers;
they do not replace the runtime ZIP.

## 2. Install the runtime

1. Fully close Garry's Mod.
2. In Steam, right-click **Garry's Mod → Manage → Browse local files**.
   This opens the installation folder, normally named `GarrysMod`.
3. Extract **MicroDuck_Runtime_Windows_x64.zip** somewhere convenient.
4. Copy the ZIP's **garrysmod** folder into that installation folder and merge
   the folders. Replace older copies of the two MicroDuck runtime files when updating.
5. Check that these exact files now exist:

```text
GarrysMod/
  garrysmod/
    lua/
      bin/
        gmsv_microduck_mujoco_win64.dll
        mujoco.dll
```

The DLLs go directly in `garrysmod/lua/bin`. They do not go inside an addon
folder, `GarrysMod/bin/win64`, or an extra nested `garrysmod/garrysmod` folder.

Launch the **64-bit** game after copying. Loading a new map without closing
the game does not replace an already loaded DLL.

## 3. Spawn and drive

Start **Sandbox → gm_flatgrass** for the first test. Open the spawn menu:

- **Entities → MicroDuck → MicroDuck — Real Policy** for the walking robot.
- **Entities → MicroDuck → MicroDuck — Roller Skates** for the roller robot.
- **Weapons → MicroDuck → MicroDuck Remote** for the pistol-shaped controller.

Aim at a duck and **left-click** to pair and drive it. The remote has no bullets.
Subsequent clicks reconnect to the paired duck when you are not aiming at another one.

| Control | Walking duck | Roller duck |
| --- | --- | --- |
| W / S | Walk forward / backward | Push / brake |
| A / D | Turn | Steer |
| Left / right arrows | Strafe | Unused |
| Mouse | Orbit in chase view; look around in player view | Same |
| Shift + E | Player viewpoint / chase camera | Same |
| E | Sit / stand | Crouch and rise |
| F | Somersault | Unavailable |
| Shift + left / right click | Left / right kick | Unavailable |
| Right-click | Motors on / off | Same |
| R | Reset to spawn | Same |
| Space | Return movement to your player | Same |

In **player view**, your pistol and normal viewpoint remain visible while WASD
drives the duck. Your player stays in place. Press **Space** before walking your
player closer; reconnect with the remote afterward. The viewpoint preference is
kept when reconnecting during the same game session.

Stop and balance before kicking or rolling. The kick policies do not aim at props:
place a small lightweight prop just ahead of the selected foot. Roller wheels
coast when W is released and S applies gradual braking. A fallen roller duck
may need **R**; an automatic roller get-up policy is not included.

## Updating

Steam updates the Workshop content. If a release requires a newer native runtime,
close the game, download that release's runtime ZIP, copy its two DLLs over the
old versions, and restart. This release requires **bridge API 4 / MuJoCo 3.17.0**.

Remove or move your old loose `garrysmod/addons/microduck_real_ai` development
copy out of the game before using the Workshop version. Keep only one enabled copy.
Back up the old folder outside `garrysmod/addons` if you want to preserve it.

## Manual install without Workshop

Download `microduck_real_ai.gma` from the same release and place it in
`GarrysMod/garrysmod/addons`. Install the runtime ZIP as above. Do not install
both that GMA and a Workshop subscription at the same time.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Native module not found | The two DLL paths above; launch the 64-bit game. |
| Missing MSVCP140_ATOMIC_WAIT.dll or a VC runtime error | Install Microsoft's current v14 **x64** Redistributable, then restart. |
| Roller duck requests the v4 runtime | Update both runtime files while GMod is closed. |
| Missing policy / checksum mismatch | Redownload the matching addon; remove duplicate old addon copies. |
| ERROR model or missing materials | Wait for Workshop content to download and enable the addon. |
| Keys move your player | Equip the remote and left-click the duck to enter control mode. |
| Duck fell over | Give the walking policy time to recover, or press R. Roller falls may require R. |
| Physgun will not grab a robot piece | Individual-piece pickup is disabled; use the remote. |

The current validation target is local single-player gm_flatgrass. Multiplayer,
Linux/macOS, and complex uneven terrain are not validated. Prop interaction uses
approximate collision proxies, especially noticeable with very light objects.

## Uninstall

Unsubscribe or remove the manual GMA. With GMod closed, remove
`garrysmod/lua/bin/gmsv_microduck_mujoco_win64.dll`. The companion `mujoco.dll`
can also be removed if no other addon uses it. Your other game files are unaffected.

## Credits

Robot, meshes and trained policies: [Pollen Robotics](https://github.com/pollen-robotics/microduck)
and [microduck_rl](https://github.com/pollen-robotics/microduck_rl).
Physics: [MuJoCo](https://github.com/google-deepmind/mujoco).
Code notices use Apache-2.0; adapted robot meshes retain CC BY-NC-SA 4.0.
Full notices accompany the addon/runtime.

Facepunch documents the [Workshop file restrictions](https://wiki.facepunch.com/gmod/Workshop_Addon_Creation)
and [native module installation path](https://wiki.facepunch.com/gmod/Global.require).
