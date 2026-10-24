from pathlib import Path
import subprocess, sys
root=Path(__file__).resolve().parents[1]
s=(root/'tests/audit_servo_benchmark.lua').read_text()
s=s.replace('e:Spawn();e:Activate()','e:Spawn()')
s=s.replace('''if IsValid(MDTestDuck) then
    origin = Vector(MDTestDuck.SpawnOrigin.x,MDTestDuck.SpawnOrigin.y,MDTestDuck.SpawnOrigin.z)
end''','')
a=s.index('local cases = {');b=s.index('local results, index',a)
s=s[:a]+'''local cases = {
 {name="floor001_j0018", physical=true, floor=.001, scale=1, J=.0018},
 {name="floor001_j0036", physical=true, floor=.001, scale=1, J=.0036},
 {name="physical10_j0018", physical=true, floor=0, scale=10, J=.0018},
 {name="physical10_j0036", physical=true, floor=0, scale=10, J=.0036},
}
'''+s[b:]
s=s.replace('if cfg.physical then ph:SetInertia(v(physical[i].diagonal)) end','''if cfg.physical then
            local iv=v(physical[i].diagonal)*cfg.scale
            for k=1,3 do iv[k]=math.max(iv[k],cfg.floor) end
            ph:SetInertia(iv)
        end''')
heading=(root/'addon/lua/microduck/heading.lua').read_text()
s='hook.Remove("Tick","MicroDuckStaticChainAudit")\nlocal Heading=(function()\n'+heading+'\nend)()\n'+s
s=s.replace('local cfg=cases[index]','local cfg=cases[index]')
s=s.replace('e.ControlTick=function(self,dt)','''Heading.reset(e,0)
    e.ControlTick=function(self,dt)''')
s=s.replace('local obs=self:Observe(q,qd)','''local forward=self:LocalToWorld(v(R.links[1].trunk_axes[1]))-self:GetPos()
            local gyro=self:GetPhysicsObject():LocalToWorldVector(self:GetPhysicsObject():GetAngleVelocity())
            local request=self.Command
            self.Command=Heading.update(self,.02,request,math.atan2(forward.y,forward.x),math.rad(gyro.z))
            local obs=self:Observe(q,qd)
            self.Command=request''')
s=s.replace('audit_servo_benchmark.json','servo_candidates.json').replace('audit_servo_done.json','servo_candidates_done.json')
if '--scaled' in sys.argv:
    a=s.index('local cases = {');b=s.index('local results, index',a)
    s=s[:a]+'''local cases = {
 {name="scaled_physical_j0018", physical=true, floor=0, scale=1, J=.0018},
 {name="scaled_physical_j0036", physical=true, floor=0, scale=1, J=.0036},
}
'''+s[b:]
    s=s.replace('v(physical[i].diagonal)*cfg.scale','v(physical[i].diagonal)*cfg.scale*(R.diagnostic_length_scale or 1)^2')
    s=s.replace('report.initial_z-2','report.initial_z-2*(R.diagnostic_length_scale or 1)')
    s=s.replace('servo_candidates.json','scaled_servo_candidates.json').replace('servo_candidates_done.json','scaled_servo_candidates_done.json')
if '--prephysical' in sys.argv:
    a=s.index('local cases = {');b=s.index('local results, index',a)
    s=s[:a]+'''local cases = {
 {name="prephysical_j0018", physical=false, J=.0018},
 {name="prephysical_j0036", physical=false, J=.0036},
}
'''+s[b:]
    s=s.replace('servo_candidates.json','prephysical_servo.json').replace('servo_candidates_done.json','prephysical_servo_done.json')
p=root/'build/servo_candidates.lua';p.write_text(s)
subprocess.run([sys.executable,str(root/'tools/send_test.py'),str(p)],check=True)
