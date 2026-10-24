"""Build the native MuJoCo bridge using the existing portable Zig toolchain."""
from pathlib import Path
import argparse,hashlib,json,subprocess

ROOT=Path(__file__).resolve().parents[2]
SRC=Path(__file__).resolve().parent
ZIGROOT=ROOT/'build/toolchain/zig-x86_64-windows-0.17.0'
ZIG=ZIGROOT/'zig.exe'
MUJOCO=ROOT/'.venv/Lib/site-packages/mujoco'
parser=argparse.ArgumentParser()
parser.add_argument('--module-name',default='microduck_mujoco4')
args=parser.parse_args()
assert args.module_name.replace('_','').isalnum()
OUT=ROOT/'build/native'/args.module_name
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'kernel32.def').write_text('LIBRARY KERNEL32.dll\nEXPORTS\n LoadLibraryA\n GetProcAddress\n FreeLibrary\n GetModuleHandleExA\n GetModuleFileNameA\n')
(OUT/'msvcrt.def').write_text('LIBRARY msvcrt.dll\nEXPORTS\n memcpy\n memset\n memmove\n sqrt\n')
def run(*args):
    subprocess.run([str(ZIG),*map(str,args)],cwd=OUT,check=True)
for name in ('kernel32','msvcrt'):
    run('dlltool','-m','i386:x86-64','-d',name+'.def','-l',name+'.lib')
for name in ('core','module'):
    run('c++','-target','x86_64-windows-msvc','-O2','-ffreestanding','-fno-exceptions','-fno-rtti',
        '-fno-stack-protector','-fno-threadsafe-statics','-fno-builtin','-nostdinc','-nostdlib','-nostdinc++',
        '-isystem',ZIGROOT/'lib/include','-I',MUJOCO/'include','-I',OUT,
        '-c',SRC/(name+'.cpp'),'-o',name+'.obj')
DLL=OUT/('gmsv_'+args.module_name+'_win64.dll')
run('lld-link','/dll','/noentry','/nodefaultlib','/machine:x64','/out:'+str(DLL),'core.obj','module.obj','kernel32.lib','msvcrt.lib')
manifest={'dll':str(DLL),'bytes':DLL.stat().st_size,'sha256':hashlib.sha256(DLL.read_bytes()).hexdigest(),
          'mujoco_runtime':str(MUJOCO/'mujoco.dll'),'mujoco_version_required':'3.17.0','installed':False}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest))
