from pathlib import Path
s=Path('tests/benchmark_controller.lua').read_text()
a=s.index('local settings=');b=s.index('local results=',a)
s=s[:a]+'''local settings={
 {name="quarter",kp=.55,kd=.053,implicit=false,speed=.25},
 {name="quarter_implicit",kp=.55,kd=.053,implicit=true,speed=.25},
 {name="half",kp=.55,kd=.053,implicit=false,speed=.5},
 {name="quarter_rotor",kp=.55,kd=.053,implicit=false,speed=.25,root=.0018},
}
'''+s[b:]
s=s.replace('e.ControlTick=function(self,dt)','''local normalObserve=e.Observe
 e.Observe=function(self,q,qd)
  local obs=normalObserve(self,q,qd)
  for k=1,3 do obs[k]=obs[k]/cfg.speed end
  for k=21,34 do obs[k]=obs[k]/cfg.speed end
  return obs
 end
 e.ControlTick=function(self,dt)
  local realDt=dt;dt=dt*cfg.speed''')
s=s.replace('-9.81*R.units_per_m*ph:GetMass()*dt','-9.81*R.units_per_m*ph:GetMass()*realDt*cfg.speed*cfg.speed')
s=s.replace('local target=self.Targets[i]','local target=self.Targets[i];qd[i]=qd[i]/cfg.speed')
s=s.replace('R.mass_scale*dt)','R.mass_scale*realDt*cfg.speed*cfg.speed)')
s=s.replace('.1,60,function()', '.1,160,function()').replace('#report.frames==60','#report.frames==160')
s=s.replace('e.Command=t>3 and {.12,0,0} or {0,0,0}','e.Command=t*cfg.speed>3 and {.3,0,0} or {0,0,0}')
Path('build/benchmark_slow.lua').write_text(s)
