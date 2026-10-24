"""Build the tiny Windows x64 VPhysics timestep module without a system SDK."""
from pathlib import Path
import hashlib,json,subprocess
root=Path(__file__).resolve().parents[1]
zig=root/'build/toolchain/zig-x86_64-windows-0.17.0/zig.exe'
src=root/'native/physics_step'
out=root/'build/native'
out.mkdir(exist_ok=True)
(out/'kernel32.def').write_text('LIBRARY KERNEL32.dll\nEXPORTS\n GetModuleHandleA\n GetProcAddress\n')
def run(*args):
    subprocess.run([str(zig),*map(str,args)],cwd=out,check=True)
run('dlltool','-m','i386:x86-64','-d','kernel32.def','-l','kernel32.lib')
run('c++','-target','x86_64-windows-msvc','-O2','-fno-exceptions','-fno-rtti',
    '-fno-stack-protector','-fno-threadsafe-statics','-fno-builtin','-nostdinc','-nostdlib','-nostdinc++',
    '-c',src/'module.cpp','-o','physics_step.obj')
run('lld-link','/dll','/noentry','/nodefaultlib','/machine:x64',
    '/out:gmsv_microduck_physics_win64.dll','physics_step.obj','kernel32.lib')
dll=out/'gmsv_microduck_physics_win64.dll'
print(json.dumps({'dll':str(dll),'bytes':dll.stat().st_size,'sha256':hashlib.sha256(dll.read_bytes()).hexdigest()}))
