from pathlib import Path
p=Path('tests/benchmark_controller.lua');s=p.read_text()
a=s.index('local settings=');b=s.index('local results=',a)
s=s[:a]+'''local settings={
 {name="tight_02_4",kp=.55,kd=.053,implicit=false,beta=.2,iterations=4},
 {name="tight_05_8",kp=.55,kd=.053,implicit=false,beta=.5,iterations=8},
 {name="tight_08_12",kp=.55,kd=.053,implicit=false,beta=.8,iterations=12},
 {name="tight_implicit",kp=.55,kd=.053,implicit=true,beta=.5,iterations=8},
 {name="tight_rotor",kp=.55,kd=.053,implicit=false,root=.0018,beta=.5,iterations=8},
}
'''+s[b:]
s=s.replace(' local report={case=cfg', ' local raw=e.ControlTick; e.ControlTick=function(self,dt) raw(self,dt); if self:GetMotorsEnabled() then MicroDuckTighten(self,dt,cfg.beta,cfg.iterations) end end\n local report={case=cfg')
Path('build/benchmark_tight.lua').write_text(Path('tests/constraint_solver.lua').read_text()+'\n'+s)
