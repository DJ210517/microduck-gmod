"""Lossless release-only LZMA packing; source weights remain untouched."""
from pathlib import Path
import hashlib,json,lzma,struct
POLICIES=('policy_data','policy_sitstand_data','policy_roulade_data','policy_kick_left_data','policy_kick_right_data','policy_roller_data','policy_roller_crouch_data')
def unpack(data):return lzma.decompress(data,format=lzma.FORMAT_ALONE)
def pack(source:Path,stage:Path):
    output=stage/'data_static/microduck_policies';output.mkdir(parents=True,exist_ok=True)
    report={}
    for name in POLICIES:
        original=(source/f'lua/microduck/{name}.lua').read_text(encoding='utf-8').encode('utf-8')
        prefix=b'return [==[';suffix=b']==]\n'
        assert original.startswith(prefix) and original.endswith(suffix),name
        raw=original[len(prefix):-len(suffix)];assert len(json.loads(raw)['layers'])==4
        compressed=lzma.compress(raw,format=lzma.FORMAT_ALONE,preset=9)
        compressed=compressed[:5]+struct.pack('<Q',len(raw))+compressed[13:]
        assert unpack(compressed)==raw
        digest=hashlib.sha256(raw).hexdigest();path=f'data_static/microduck_policies/{name}.dat'
        (stage/path).write_bytes(compressed)
        loader=f'''-- Lossless release payload; neural weights and normalization unchanged.
local packed=assert(file.Read("{path}","GAME"),"Missing MicroDuck policy: {name}")
local raw=assert(util.Decompress(packed,{len(raw)}),"Damaged MicroDuck policy: {name}")
assert(#raw=={len(raw)} and util.SHA256(raw)=="{digest}","MicroDuck policy checksum mismatch: {name}")
return raw
'''
        (stage/f'lua/microduck/{name}.lua').write_text(loader,encoding='utf-8')
        report[name]={'original_json_bytes':len(raw),'packed_bytes':len(compressed),'json_sha256':digest,'packed_sha256':hashlib.sha256(compressed).hexdigest()}
    (output/'manifest.json').write_text(json.dumps({'format':'LZMA-alone; original JSON; no quantization','policies':report},indent=2))
    return report
