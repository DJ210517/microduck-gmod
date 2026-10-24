"""Inline the edited server entity through the temporary SP test transport."""
from pathlib import Path
import subprocess,sys
root=Path(__file__).resolve().parents[1]
code=(root/'addon/lua/entities/md_microduck/init.lua').read_text(encoding='utf-8').replace('include("shared.lua")','include("entities/md_microduck/shared.lua")')
prefix='for _,e in ipairs(ents.FindByClass("md_microduck")) do e:Remove() end\nMicroDuck.Robot=nil\nENT={}\n'
suffix='\nscripted_ents.Register(ENT,"md_microduck");ENT=nil\n'
dest=root/'build/dev_reload.lua';dest.write_text(prefix+code+suffix,encoding='utf-8')
subprocess.run([sys.executable,str(root/'tools/send_test.py'),str(dest)],check=True)
