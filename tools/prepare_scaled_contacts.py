"""Generate an isolated, enlarged MicroDuck class; never execute it in GMod.

Usage: python tools/prepare_scaled_contacts.py 2|4|8 [--variant contact_prism]

The parent test harness must Spawn() the root WITHOUT Activate() afterward:
Activate can recreate model-based physics after custom colliders were installed.
"""
from pathlib import Path
import argparse
import json

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('scale',type=int,choices=[2,4,8])
parser.add_argument('--variant',choices=['contact_prism','outline_prism'],default='contact_prism')
args=parser.parse_args()
scale=args.scale
robot=json.loads((ROOT/'addon/materials/microduck/robot.txt').read_text())
soles=json.loads((ROOT/'build/contact_candidates/colliders.json').read_text())['variants'][args.variant]
code=(ROOT/'addon/lua/entities/md_microduck/init.lua').read_text(encoding='utf-8')

def replace_once(old,new):
    global code
    assert code.count(old)==1,(old,code.count(old))
    code=code.replace(old,new,1)

replace_once('include("shared.lua")','include("entities/md_microduck/shared.lua")')
# SpawnFunction is separate from the per-link Spawn/Activate below. All model
# activation is complete before a link gets its scaled custom convex collider.
replace_once('    e:Spawn(); e:Activate()\n    ply.MicroDuck=e',
             '    e:Spawn() -- custom convex physics already initialized\n    ply.MicroDuck=e')
replace_once('''        -- StudioMDL discards collision hulls this small on some links. Build the
        -- curated convex hull directly, preserving the robot's actual size.''',
'''        -- Scale the render model after child Spawn/Activate, then install the
        -- independently scaled convex physics mesh with the true COM at zero.
        e:SetModelScale(R.diagnostic_length_scale,0)
        -- Never Activate this entity after custom physics initialization.''')
start=code.index('        local initialized=e:PhysicsInit(SOLID_VPHYSICS,vector_origin)')
end=code.index('        e:SetMoveType(MOVETYPE_VPHYSICS)',start)
code=code[:start]+'''        e:SetSolid(SOLID_VPHYSICS)
        local initialized=e:PhysicsInitConvex(vertices,MD.SoleHulls[l.name] and "rubbertire" or "rubber",vector_origin)
        assert(initialized,"Scaled convex collider failed: "..l.name)
'''+code[end:]
replace_once('ph:SetMaterial("rubber")','ph:SetMaterial(MD.SoleHulls[l.name] and "rubbertire" or "rubber")')
replace_once('self:SetNWFloat("MicroDuckRate",.25)','self:SetNWFloat("MicroDuckRate",1)')
code=code.replace('self:GetNWFloat("MicroDuckRate",.25)','self:GetNWFloat("MicroDuckRate",1)')
code=code.replace('tonumber(args[1]) or .25','tonumber(args[1]) or 1')
replace_once('''    -- Uniformly slow this robot's physical time: force scales with rate^2,
    -- measured speeds with 1/rate, and its policy clock with rate. Source's
    -- constraints then get four solver steps per trained 15 ms interval.''',
'''    -- Diagnostic defaults to normal time (rate=1). Physical length, gravity
    -- and linear velocity units scale by s; body inertia and motor torque
    -- conversion scale by s^2. Link masses and learned observations are unchanged.''')

prefix='''-- Diagnostic class only. Physical enlargement; no time slowdown.
-- Spawn the root without a subsequent Activate() call.
for _,e in ipairs(ents.FindByClass("md_microduck")) do e:Remove() end
MicroDuck=MicroDuck or {}
MicroDuck.Robot=nil
'''
prefix+='MicroDuck.SoleHulls=util.JSONToTable([==['+json.dumps(soles,separators=(',',':'))+']==],true)\n'
prefix+='local scaled=util.JSONToTable([==['+json.dumps(robot,separators=(',',':'))+']==],true)\n'
prefix+=f'local lengthScale={scale}\n'
prefix+='''scaled.diagnostic_length_scale=lengthScale
scaled.original_mass_scale=scaled.mass_scale
scaled.units_per_m=scaled.units_per_m*lengthScale
scaled.floor_offset=scaled.floor_offset*lengthScale
-- This scale is the motor torque conversion factor. Link masses stay unchanged.
scaled.mass_scale=scaled.mass_scale*lengthScale*lengthScale
local function scaleVector(t,s)
 for k=1,3 do t[k]=t[k]*s end
end
for _,link in ipairs(scaled.links) do
 local sole=MicroDuck.SoleHulls[link.name]
 if sole then link.collision_vertices=table.Copy(sole.vertices) end
 scaleVector(link.pos,lengthScale)
 scaleVector(link.inertia,lengthScale*lengthScale)
 for _,point in ipairs(link.collision_vertices) do scaleVector(point,lengthScale) end
end
for _,joint in ipairs(scaled.joints) do
 scaleVector(joint.pivot_p,lengthScale)
 scaleVector(joint.pivot_c,lengthScale)
end
MicroDuck.Robot=scaled
ENT={}
'''
suffix='\nscripted_ents.Register(ENT,"md_microduck");ENT=nil\n'
dest=ROOT/'build'/f'dev_scaled_contacts_s{scale}.lua'
dest.write_text(prefix+code+suffix,encoding='utf-8')
print(dest)
print(f'Generated only: scale={scale}, robot time=1, variant={args.variant}; no game calls.')
