from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
scale=float(sys.argv[1])
code=(root/'addon/lua/entities/md_microduck/init.lua').read_text(encoding='utf-8')
code=code.replace('include("shared.lua")','include("entities/md_microduck/shared.lua")')
code=code.replace('local R=MD.Robot',f'''local R=util.JSONToTable(include("microduck/robot_data.lua"),true)
local scale={scale}
R.units_per_m=R.units_per_m*scale;R.floor_offset=R.floor_offset*scale
for _,l in ipairs(R.links) do
 for k=1,3 do l.pos[k]=l.pos[k]*scale;l.inertia[k]=l.inertia[k]*scale*scale end
 for _,v in ipairs(l.collision_vertices) do for k=1,3 do v[k]=v[k]*scale end end
end
for _,j in ipairs(R.joints) do for _,name in ipairs({{"pivot_p","pivot_c"}}) do for k=1,3 do j[name][k]=j[name][k]*scale end end end
MD.Robot=R''')
code=code.replace('local pos,a=LocalToWorld(vec(l.pos)',f'e:SetModelScale({scale},0)\n        local pos,a=LocalToWorld(vec(l.pos)',1)
code=code.replace('R.mass_scale*dt)',f'R.mass_scale*dt*{scale*scale})')
initial=(root/'tests/live_initial.lua').read_text().replace('util.JSONToTable(include("microduck/robot_data.lua"),true)','MicroDuck.Robot')
out='for _,e in ipairs(ents.FindByClass("md_microduck")) do e:Remove() end\nENT={}\n'+code+'\nscripted_ents.Register(ENT,"md_microduck");ENT=nil\n'+initial
(root/'tests/scale_probe.lua').write_text(out,encoding='utf-8')
