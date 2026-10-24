# Publish this prepared release

The local release is prepared; uploading a GitHub release and publishing a Steam
Workshop item are separate actions. Neither is implied by a successful archive build.

## GitHub

Create a public repository named `microduck-gmod` in your own GitHub account.
Upload the contents of `github_source/` as its initial source tree. Create release
`v0.1.0`, mark it as a prerelease, paste `RELEASE_NOTES.md`, and attach:

- MicroDuck_Runtime_Windows_x64.zip
- microduck_real_ai.gma
- MicroDuck_Source.zip
- INSTALL_GUIDE.md and INSTALL_GUIDE.html
- SHA256SUMS.txt

Do not upload the workspace, .venv, local backups, debug logs, user gameplay
snapshots, or compiler caches. `github_source/` is the selected public source.

The permanent runtime asset URL will be:
`https://github.com/DJ210517/microduck-gmod/releases/download/v0.1.0/MicroDuck_Runtime_Windows_x64.zip`

The repository is https://github.com/DJ210517/microduck-gmod . Keep the
repository/runtime URLs in `release/config.json` current and rerun
`tools/build_release_bundle.py` to render the Workshop description links.

## Steam Workshop

Use the prepared `microduck_real_ai.gma` and matching 512×512 baseline JPEG icon.
Upload via your existing Workshop uploader or GMod's `bin/gmpublish.exe`:

```powershell
& 'PATH_TO_GARRYSMOD/bin/gmpublish.exe' create -addon 'FULL_PATH/microduck_real_ai.gma' -icon 'FULL_PATH/microduck_real_ai.jpg'
```

The description is in `WORKSHOP_DESCRIPTION.txt`. Fill its two public download
links before making the item visible. The item description must clearly state
the separate native-runtime requirement. Start with private visibility and
verify the uploaded item, metadata and download before changing visibility.

Use `gmpublish.exe update -id ITEM_ID -addon FULL_PATH.gma -changes CHANGELOG`
for a later update, preserving the original item. Record the actual item ID,
runtime release URL and package hash together. The GMA contains no DLLs.

Official instructions:
https://wiki.facepunch.com/gmod/Workshop_Addon_Creation
https://wiki.facepunch.com/gmod/Workshop_Addon_Updating
