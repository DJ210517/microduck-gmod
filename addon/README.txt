MicroDuck - real neural policy for Garry's Mod

Pollen Robotics' original walking, sit/stand, forward-roll and left/right kick policies run
inside GMod's server Lua with their original observation normalizers and
61-input/14-output networks. Each policy
observes the live articulated robot and commands its fourteen joint motors at
50 Hz. An embedded MuJoCo solver advances the actual rigid bodies, gravity,
collisions, and bounded joint torques at 200 Hz. The robot runs at full speed;
GMod can use its normal server tick rate.

The detailed Source model follows these simulated bodies. Actual closed map
collision solids become physical collision geometry. Nearby props have collision
proxies and receive reaction impulses in Source. Heading and stopping feedback
adjust the velocity commands given to the neural policy. Motor power can be
switched off, allowing the robot to collapse under gravity. Reset explicitly
returns it to its spawn pose.

HOW TO TRY
Spawnmenu > Entities > MicroDuck > MicroDuck - Real Policy
Or use console: microduck_spawn

REMOTE CONTROL
Spawnmenu > Weapons > MicroDuck > MicroDuck Remote.
The remote uses the standard Half-Life 2 pistol model and has no ammunition.
Left-click a duck to pair and enter control mode. Later clicks reconnect to
the paired duck when you are not aiming at another duck. Right-click toggles
motor power, R resets its pose, and Space returns you to your player.
Switching away from or dropping the remote stops its control commands.
Shift + E switches between the chase camera and your normal player viewpoint.
In player view the pistol remote stays visible, the mouse looks around normally,
and WASD still drives the duck while your player stays in place. Space returns
movement to your player. The selected viewpoint is kept when reconnecting to
a duck during this game session. You can select a view before entering control.
E toggles sitting/standing. F performs the trained forward roll after the duck
has stopped and balanced. These controls also work while holding the remote
outside driving mode, using its paired duck. F temporarily replaces flashlight
input only while this remote is equipped. Hold Shift and left-click for a left
kick, or Shift and right-click for a right kick. Stop and balance first. Place a
small lightweight prop just ahead of the selected foot; the policies do not aim
at or track props. Each kick runs once, then waits for balance before walking.
Modified clicks do not toggle control mode or motor power.
While seated, press E to stand before
walking again. Busy actions finish their physical recovery before walking resumes.

microduck_control    Toggle close camera and keyboard control of selected duck
W/S                  Forward/backward command
A/D                  Turn; release to hold the new heading
Left/Right arrows    Sideways command
Mouse                Orbit the close camera
Shift + E (remote)   Toggle player viewpoint / chase camera
microduck_view player    Select player viewpoint
microduck_view chase     Select chase camera
R                    Reset pose while controlling
Space                Return to your player
E (remote equipped)  Sit / stand using the official alpha_sitstand policy
F (remote equipped)  Forward roll using the official roulade policy
Shift + left-click   Left kick using the official ball_kick_left policy
Shift + right-click  Right kick using the official ball_kick_right policy
microduck_reset      Restore the original standing spawn pose
microduck_motors     Toggle motor power (also E on the robot with another weapon)
microduck_command 0.3 0 0    Manual forward command, outside control mode
microduck_command 0 0 0      Stop command

ROLLER DUCK
Spawnmenu > Entities > MicroDuck > MicroDuck - Roller Skates.
This is a separate entity so the working walking duck keeps all its skills.
Select it with the same remote. W pushes, S brakes, A/D steer. Release W to
coast; bearing resistance gradually slows the wheels. Arrow-key strafing is
unavailable on skates. E runs the official crouch-and-rise cycle (3.5 seconds).
R resets the roller duck; right-click switches motor power. Kicks, walking sit,
and somersaults are available on the walking duck.
The original roller.onnx and roller_crouch.onnx networks run at action scale0.8,
with heading-error steering and four passive wheel hinges. Wheels have their
original mass/inertia and0.003Nm bearing resistance. Source models include the
original roller blades, tires and rims. There is no scripted propulsion.
The v4 native runtime is required; close GMod before updating it, then restart.
Roller support is an experimental single-player prototype.

INSTALLATION (WINDOWS 64-BIT)
Close Garry's Mod before replacing a loaded native module.
1. Copy dist/microduck_real_ai to garrysmod/addons/microduck_real_ai.
2. Copy the contents of dist/native_runtime/garrysmod into garrysmod.
   This installs lua/bin/gmsv_microduck_mujoco_win64.dll and lua/bin/mujoco.dll.
3. Start the 64-bit game and load a map. No special tick rate is required.

The GMA contains the Lua/model/data assets. Its native DLL sidecar is also
required; a Workshop/GMA-only install cannot supply that native dependency.
The matching MuJoCo 3.17.0 runtime and its notices are included in the sidecar.
The system Microsoft Visual C++ x64 runtime is required.
This release requires the updated native bridge with snapshot/restore support;
replace the old bridge while GMod is closed, then restart the game.

CURRENT SCOPE
Validated in local single-player gm_flatgrass. All 112 world collision solids
are imported there, including the lower ground beyond the raised platform.
Maps within the configured geometry budgets import all available world solids.
Larger maps use overlapping coverage that follows the duck while preserving
its position, velocity and neural-controller history. Displacement completeness
is unverified; the adapter uses only solids exposed by Source's world physics
API. Map static props are separate. Up to 32 nearby props/players use oriented-box
collision proxies; prop coupling is approximate, especially for very light or
fast objects. Physgun pickup of individual robot pieces is disabled. Props,
player contact, and damage impulses can disturb the robot. Multiplayer,
and complex uneven maps remain unverified. Fall recovery is handled by the
original standing/walking network with zero movement commands until upright.
This is a physical policy controller, not a path-planning NPC.

LEARNED SKILLS
Sit and stand share the official alpha_sitstand.onnx network, using its posture
flag and original sit/rise timing. Roulade uses the official roulade.onnx network;
completion is measured from the actual body's forward rotation before returning
to the walking/recovery policy. A blocked roll has a bounded policy window. These
actions can include sideways twist and heading changes. The left and right kicks
use separate official ball_kick_left/right.onnx networks, each with the released
half-second zero-command window and learned standing recovery. Prop impacts come
from physical foot contact; there is no added kick impulse. Source file hashes and
the exact upstream revision are included in data_static/microduck_skills/.

MODEL AND PHYSICS
The detailed_v5 meshes retain curved housings, panel edges, and joint detail.
Each body remains below Source's 65,536-vertex limit (maximum 51,290). Materials
distinguish plastic, metal, camera lens, and soles. Original robot collision
geometry and body mass/inertia are used in MuJoCo at their real metric scale.
Conversion is 39.37007874 Source units/metre. Source's previous 100x mass and
quarter-speed adaptations are no longer used. The motor controller uses the
identified stiffness/damping and bounded internal hinge torque; it is an
adaptation of the actuator dynamics, rather than the complete BAM drivetrain.

Policy source:
https://huggingface.co/pollen-robotics/microduck-policies
File: velstand.onnx
SHA256: 2fc7f8ee6acd7d0d3f66a99927b5d5a56589aeed02ec714de329b252d5ccf492

Code and training sources:
https://github.com/pollen-robotics/microduck
https://github.com/pollen-robotics/microduck_rl
Motor parameters: https://github.com/Rhoban/bam
Physics runtime: https://github.com/google-deepmind/mujoco

Meshes are adaptations of Pollen Robotics' MicroDuck meshes, converted,
simplified, split into Source rigid bodies, and recolored using supplied
material colors. Credit: Pollen Robotics.
Original: https://github.com/pollen-robotics/microduck_rl
Mesh adaptations: CC BY-NC-SA 4.0
https://creativecommons.org/licenses/by-nc-sa/4.0/
Noncommercial use, attribution, and share-alike terms apply to the meshes.
Upstream source code: Apache-2.0. See LICENSE-APACHE.txt.
MuJoCo licenses and third-party notices are included with the runtime/assets.
