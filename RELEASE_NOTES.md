# MicroDuck for GMod v0.1.0 — experimental

Includes walking and roller variants, the pistol remote, player/chase viewpoints,
sit/stand, somersault, left/right kicks, and the roller crouch-and-rise policy.
The native bridge supports four passive wheels, closed map collision solids,
state-preserving terrain refresh and solver-fault detection.

## Downloads

- **MicroDuck_Runtime_Windows_x64.zip** — required companion runtime for Workshop subscribers.
- **microduck_real_ai.gma** — optional manual install; Workshop publishers upload this file.
- **INSTALL_GUIDE.md / INSTALL_GUIDE.html** — setup, controls, updates and troubleshooting.
- **SHA256SUMS.txt** — hashes of the published files.
- **MicroDuck_Source.zip** — port source and build helpers; excludes private logs and backups.

Fully close GMod before updating native DLLs. Requires Windows 64-bit and the
Microsoft Visual C++ v14 x64 Redistributable. No Python/ONNX Runtime installation
is needed to play. See the install guide before copying files.

Tested in local single-player gm_flatgrass. The roller variant is experimental;
falls can require R to reset. Multiplayer and complex uneven terrain remain unverified.

Pollen Robotics' original policy weights are preserved exactly. Release packing
is lossless and does not quantize or retrain the networks.
