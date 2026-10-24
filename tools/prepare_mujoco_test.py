"""Assemble the local development adapter without changing release files."""
from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
def lua_string(s):
    return '[====[' + s + ']====]'
def chunk(path):
    return '(function()\n' + (root/path).read_text() + '\nend)()'
config = {
    'baseXML': lua_string((root/'build/mujoco_runtime/base.xml').read_text()),
    'render': chunk('build/mujoco_runtime/render_data.lua'),
    'world': chunk('build/mujoco_world.lua'),
    'heading': chunk('addon/lua/microduck/heading.lua'),
    'dataDirectory': json.dumps('E:/SteamLibrary/steamapps/common/GarrysMod/garrysmod/data'),
    'runtimeDLL': json.dumps((root/'.venv/Lib/site-packages/mujoco/mujoco.dll').as_posix()),
}
out = 'MicroDuckMJPrototype={\n' + ',\n'.join(k+'='+v for k,v in config.items()) + '\n}\n'
out += (root/'build/mujoco_entity.lua').read_text()
(root/'build/mujoco_reload.lua').write_text(out)
print('Prepared MuJoCo development adapter', len(out))
