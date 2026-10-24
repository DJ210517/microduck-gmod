from pathlib import Path
import json,subprocess,sys
root=Path(__file__).resolve().parents[1]
data=json.loads((root/'build/contact_candidates/colliders.json').read_text())['variants'][sys.argv[1] if len(sys.argv)>1 else 'contact_prism']
code=(root/'addon/lua/entities/md_microduck/init.lua').read_text(encoding='utf-8').replace('include("shared.lua")','include("entities/md_microduck/shared.lua")')
code=code.replace('local initialized=e:PhysicsInit(SOLID_VPHYSICS,vector_origin)', '''local initialized
        if MD.SoleHulls[l.name] then
            local hull={};for _,point in ipairs(MD.SoleHulls[l.name].vertices) do hull[#hull+1]=vec(point) end
            e:SetSolid(SOLID_VPHYSICS)
            initialized=e:PhysicsInitConvex(hull,"rubbertire",vector_origin)
            assert(initialized,"New sole hull failed: "..l.name)
        else initialized=e:PhysicsInit(SOLID_VPHYSICS,vector_origin) end''')
code=code.replace('ph:SetMaterial("rubber")','ph:SetMaterial(MD.SoleHulls[l.name] and "rubbertire" or "rubber")')
if '--physical' in sys.argv:
    physical=json.loads((root/'build/audit_physical_inertia.json').read_text())
    if isinstance(physical,dict):
        raise ValueError('Inspect physical tensor input schema')
    start=code.index('        local inertia=vec(l.inertia)')
    end=code.index('        ph:SetDamping(0,0)',start)
    code=code[:start]+'        ph:SetInertia(vec(MD.PhysicalInertia[i].diagonal))\n'+code[end:]
if '--native-gravity' in sys.argv:
    code=code.replace('ph:EnableGravity(false)','ph:EnableGravity(true)')
    code=code.replace('ph:ApplyForceCenter(Vector(0,0,-9.81*R.units_per_m*ph:GetMass()*dt*rate*rate))','-- Native environment gravity for this diagnostic.')
prefix='for _,e in ipairs(ents.FindByClass("md_microduck")) do e:Remove() end\nMicroDuck.Robot=nil\nMicroDuck.SoleHulls=util.JSONToTable([==['+json.dumps(data)+']==],true)\nENT={}\n'
if '--physical' in sys.argv:
    prefix='MicroDuck.PhysicalInertia=util.JSONToTable([==['+json.dumps(physical)+']==],true)\n'+prefix
suffix='\nscripted_ents.Register(ENT,"md_microduck");ENT=nil\n'
dest=root/'build/dev_contacts_reload.lua';dest.write_text(prefix+code+suffix,encoding='utf-8')
subprocess.run([sys.executable,str(root/'tools/send_test.py'),str(dest)],check=True)
