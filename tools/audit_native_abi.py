"""Read-only ABI evidence for the installed Windows x64 VPhysics031 build.

Requires pefile and capstone. Never loads or executes the inspected DLL.
RVAs below were traced from CreateInterface's VPhysics031 registration, its
factory, singleton and environment constructor. Changed builds must be retraced.
"""
from pathlib import Path
import hashlib
import json
import struct
import capstone
import pefile

ROOT = Path(__file__).resolve().parents[1]
DLL = Path(r"E:\SteamLibrary\steamapps\common\GarrysMod\bin\win64\vphysics.dll")
pe = pefile.PE(str(DLL))
base = pe.OPTIONAL_HEADER.ImageBase
cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
cs.detail = True


def instructions(rva, size=64, stop=True):
    output = []
    for item in cs.disasm(pe.get_data(rva, size), base + rva):
        output.append({"rva": hex(item.address - base), "instruction": f"{item.mnemonic} {item.op_str}".strip()})
        if stop and item.mnemonic in {"ret", "jmp"}:
            break
    return output


def pointer(rva):
    return struct.unpack("<Q", pe.get_data(rva, 8))[0] - base


physics_table = pointer(0x11F020)
assert physics_table == 0xE4758, "Installed VPhysics singleton changed; retrace its factory"
expected = {9: 0xBAC0, 10: 0xBB60, 11: 0xBBF0}
for slot, rva in expected.items():
    assert pointer(physics_table + 8 * slot) == rva
environment_table = 0xE5FC0
environment_slots = {35: 0x1C0A0, 36: 0x1B700, 37: 0x1DBD0}
for slot, rva in environment_slots.items():
    assert pointer(environment_table + 8 * slot) == rva
# Confirm semantics, not only pointer positions: index lookup, getter, setter.
assert pe.get_data(0xBBF0, 2) == bytes.fromhex("85d2")  # test edx,edx
assert pe.get_data(0xBBFD, 8) == bytes.fromhex("4863d2488b04d0c3")
assert pe.get_data(0x1B700, 13) == bytes.fromhex("488b4108f30f108004010000c3")
assert pe.get_data(0x90305, 8) == bytes.fromhex("f30f118904010000")

report = {
    "path": str(DLL),
    "sha256": hashlib.sha256(DLL.read_bytes()).hexdigest(),
    "pe_timestamp": pe.FILE_HEADER.TimeDateStamp,
    "image_size": pe.OPTIONAL_HEADER.SizeOfImage,
    "interface": "VPhysics031",
    "physics_singleton_rva": "0x11f020",
    "physics_vtable_rva": hex(physics_table),
    "physics_vtable_slots": {str(i): {"function_rva": hex(pointer(physics_table + i * 8)), "instructions": instructions(pointer(physics_table + i * 8))} for i in range(12)},
    "environment_constructor": instructions(0x18C60, 48, False),
    "environment_vtable_rva": hex(environment_table),
    "environment_vtable_slots": {str(i): {"function_rva": hex(rva), "instructions": instructions(rva)} for i, rva in environment_slots.items()},
    "native_timestep_setter": instructions(0x902F0, 80),
    "conclusion": "Installed IPhysics uses 9 inherited methods: GetActiveEnvironmentByIndex slot11. Environment IsInSimulation35/GetTimestep36/SetTimestep37 match SDK2013.",
}
output = ROOT / "build/audit_installed_vphysics_abi.json"
output.write_text(json.dumps(report, indent=2))
print(json.dumps({"report": str(output), "sha256": report["sha256"], "get_environment_slot": 11, "get_timestep_slot": 36, "set_timestep_slot": 37}))
