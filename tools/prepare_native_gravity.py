from pathlib import Path
p=Path(r'E:/SteamLibrary/steamapps/common/GarrysMod/garrysmod/data/microduck_dev/normal_benchmark.json')
Path('build/normal_prism_benchmark.json').write_bytes(p.read_bytes())
c=Path('tests/normal_benchmark.lua').read_text()
a=c.index('local cases={');b=c.index('local results=',a)
c=c[:a]+'''local oldGravity=physenv.GetGravity()
physenv.SetGravity(Vector(0,0,-9.81*R.units_per_m))
local cases={{name="native_gravity",iterations=4,mass=1,inertia=1,minmass=10}}
'''+c[b:]
c=c.replace('R.mass_scale=originalMass\n  physenv','physenv.SetGravity(oldGravity)\n  R.mass_scale=originalMass\n  physenv')
c=c.replace('normal_benchmark.json','native_gravity_benchmark.json')
Path('build/native_gravity_test.lua').write_text(c)
