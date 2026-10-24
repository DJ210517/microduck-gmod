# MicroDuck runtime setup

This Windows x64 installer embeds the same v0.1.0 runtime ZIP and verifies every
payload against its manifest. It auto-detects Steam libraries, allows folder
selection, refuses installation while GMod runs, backs up changed DLLs, verifies
Windows can load them, and restores old runtime files if a write/load fails.
It requests normal user privileges and never stops the game or changes Windows
security settings. Microsoft Visual C++ is checked; an official download link is
provided if that dependency needs updating.

## Build

1. Download the matching runtime ZIP from the v0.1.0 release into
   `dist/workshop_release/MicroDuck_Runtime_Windows_x64.zip`. The build checks its
   pinned SHA-256 before embedding it.
2. On Windows 10/11, run `python installer/build_setup.py`. The build uses the
   Windows .NET Framework C# compiler; it needs no external C# package downloads.
3. Output: `dist/installer/MicroDuck_Setup_Windows_x64.exe` and checksum file.

Python is only for building. Players run the EXE directly.

## Fixture tests

The EXE accepts `--self-test ABSOLUTE_PATH/installer_fixture` to run the installer
against a dedicated synthetic game directory and emit `results.json`. The tests
cover multi-library detection, wrong directories, running-game rejection, payload
checksums, actual DLL loading, repair, upgrade backups and rollback. Real GMod
installations are detected read-only; they are never used as the test destination.
Use a fresh fixture directory for each run.
