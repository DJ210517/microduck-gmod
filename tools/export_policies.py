"""Export the official normalized 61 -> 14 MLP without changing its weights.

Usage: .venv/Scripts/python.exe tools/export_policies.py [--fetch] [--check]
Downloads are pinned to a commit. This does not modify the walking policy.
"""
from pathlib import Path
import argparse, hashlib, json, urllib.request
import numpy as np
import onnx
from onnx import numpy_helper

ROOT=Path(__file__).resolve().parents[1]
REPO='pollen-robotics/microduck-policies'
REVISION='665ae4eb20bfe13bca1ef4ea6d4bb6b4a096e448'
POLICIES={'sitstand':'alpha_sitstand.onnx','roulade':'roulade.onnx',
          'kick_left':'ball_kick_left.onnx','kick_right':'ball_kick_right.onnx'}
EXPECTED={'sitstand':'a6f102d9fd655782ba85bfffe18175c34621da719cffcdd673be7982a06fc254',
          'roulade':'3d60da08fc13f29c1b57f41977aa898132c0d60042100149d8e775affcbca32b',
          'kick_left':'d6928284dccd3dd61e08bf2f760effa74309fbefd97b2b31afb2a60f526d196a',
          'kick_right':'147a32c388c6b19111b3ac3b550a9a6dc8b8bf267118af4d8c3712522eedb5af'}

def extract(path):
    model=onnx.load(path);onnx.checker.check_model(model)
    nodes=list(model.graph.node)
    assert [n.op_type for n in nodes]==['Sub','Div','Gemm','Elu','Gemm','Elu','Gemm','Elu','Gemm']
    arrays={x.name:numpy_helper.to_array(x) for x in model.graph.initializer}
    assert nodes[0].input[0]==model.graph.input[0].name and nodes[1].input[0]==nodes[0].output[0]
    mean=arrays[nodes[0].input[1]].ravel();divisor=arrays[nodes[1].input[1]].ravel()
    assert mean.shape==divisor.shape==(61,) and np.all(divisor>0)
    result={'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'mean':mean.tolist(),'divisor':divisor.tolist(),'layers':[]}
    previous=nodes[1].output[0];width=61
    for node in nodes[2:]:
        assert node.input[0]==previous
        attrs={a.name:onnx.helper.get_attribute_value(a) for a in node.attribute}
        if node.op_type=='Elu':assert attrs.get('alpha',1)==1
        else:
            assert attrs.get('transB',0)==1 and attrs.get('transA',0)==0
            assert attrs.get('alpha',1)==attrs.get('beta',1)==1
            w,b=arrays[node.input[1]],arrays[node.input[2]]
            assert w.shape[1]==width and b.shape==(w.shape[0],)
            assert np.isfinite(w).all() and np.isfinite(b).all()
            result['layers'].append({'inputs':int(w.shape[1]),'outputs':int(w.shape[0]),'w':w.ravel().tolist(),'b':b.tolist()})
            width=w.shape[0]
        previous=node.output[0]
    assert width==14 and previous==model.graph.output[0].name
    return result,{p.key:p.value for p in model.metadata_props}

def check_parity():
    """Compare the deployed Lua evaluator with ONNX Runtime on 100 states per skill."""
    import onnxruntime as ort
    from lupa import LuaRuntime
    lua=LuaRuntime(unpack_returned_tuples=True)
    def table(value):
        if isinstance(value,dict):return lua.table_from({k:table(v) for k,v in value.items()})
        if isinstance(value,list):return lua.table_from([table(v) for v in value])
        return value
    network=lua.execute((ROOT/'addon/lua/microduck/network.lua').read_text())
    rng=np.random.default_rng(2424);report={}
    for name,filename in POLICIES.items():
        weights=json.loads(lua.execute((ROOT/f'addon/lua/microduck/policy_{name}_data.lua').read_text()))
        assert weights['sha256']==EXPECTED[name]
        net=network.new(table(weights))
        session=ort.InferenceSession(str(ROOT/'assets'/filename),providers=['CPUExecutionProvider'])
        worst=0
        for i in range(100):
            obs=rng.normal(0,.3,61).astype(np.float32)
            obs[3:6]=rng.normal(size=3);obs[3:6]/=np.linalg.norm(obs[3:6])
            obs[20:34]*=10;obs[48:]=0
            if name=='sitstand':obs[48]=i%2
            expected=session.run(None,{'obs':obs[None]})[0][0]
            output=net.forward(net,table(obs.tolist()))
            error=float(np.max(np.abs(expected-[output[j] for j in range(1,15)])))
            worst=max(worst,error)
            assert error<2e-4,(name,i,error)
        report[name]={'cases':100,'max_absolute_error':worst,'sha256':weights['sha256'],
                      'layers':[(layer['inputs'],layer['outputs']) for layer in weights['layers']]}
    output=ROOT/'build/kick_policy_lua_parity.json';output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

def main(fetch=False,check=False):
    manifest_path=ROOT/'assets/skills_manifest.json'
    if fetch:
        manifest_path.write_bytes(urllib.request.urlopen(f'https://huggingface.co/{REPO}/resolve/{REVISION}/manifest.json').read())
    manifest=json.loads(manifest_path.read_text())
    assert manifest['obs_len']==61 and manifest['action_len']==14
    assert manifest['robot']['control_hz']==50
    _,walk_metadata=extract(ROOT/'assets/velstand.onnx')
    provenance={'repository':REPO,'revision':REVISION,'control_hz':50,'obs_len':61,'action_len':14,'policies':{},
        'manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        'runtime_sources':{'microduck_commit':'942e58e3aa6dbb28e7037203fff11866122c7567',
            'microduck_rl_commit':'b02fdea4902c2b93b7d34a83a6f05da4ececb7d3',
            'runtime':'robotd/src/control.rs','rehearsal':'scripts/infer_policy.py'},
        'gmod_runtime':{'sit_seconds':2,'rise_seconds':1,'roll_min_seconds':1,'roll_max_seconds':5,
            'kick_seconds':0.5,
            'kick_command':'All 13 command entries are zero; action scale 1.0. Start standing, preserve previous raw action, then return to zero-command velstand recovery. Both kicks use the pinned official manifest duration of 0.5s; the upstream infer_policy.py interactive rehearsal CLI independently defaults --kick-duration to 3s.',
            'kick_prop_placement':'Upstream rehearsal places a radius0.035m ball at yaw-frame offset x0.09m, y+0.042m for left / -0.042m for right. This is a blind one-shot policy: no prop perception or aiming command.',
            'roll_duration_note':'Manifest is 1s; official infer_policy.py rehearsal default is 2s. With the port servo 1s interrupts at155deg, and fixed2s can hand off while still inverted. End after measured unwrapped body-gravity pitch >=5.75rad and gravity z < -0.95, after at least1s; bounded5s fallback matches training episode length. A roll can include lateral twist and heading change. No servo changes.',
            'recovery':'Velstand receives zero command after skills or sustained walking fall until gravity z < -0.95, gyro magnitude < 0.8rad/s and vertical speed <0.2m/s for0.3s. Only neural commands are gated.',
            'previous_action':'Preserve raw previous policy output across policy switches.'}}
    for key,filename in POLICIES.items():
        path=ROOT/'assets'/filename
        url=f'https://huggingface.co/{REPO}/resolve/{REVISION}/{filename}'
        if fetch:path.write_bytes(urllib.request.urlopen(url).read())
        result,metadata=extract(path)
        assert result['sha256']==EXPECTED[key],f'{filename}: unexpected source hash'
        for field in ('joint_names','default_joint_pos','observation_names','action_scale'):
            assert metadata[field]==walk_metadata[field],f'{filename}: incompatible {field}'
        entry=next(p for p in manifest['policies'] if p['file']==filename)
        if key.startswith('kick_'):
            assert metadata['command_names']=='twist'
            assert entry['name']==key and entry['kind']=='episodic' and entry['duration_s']==0.5
            assert 'command' not in entry
        payload=json.dumps(result,separators=(',',':'))
        (ROOT/f'addon/lua/microduck/policy_{key}_data.lua').write_text('return [==['+payload+']==]\n',encoding='utf-8')
        (ROOT/f'addon/materials/microduck/policy_{key}.txt').write_text(payload,encoding='utf-8')
        provenance['policies'][key]={'file':filename,'url':url,'sha256':result['sha256'],'metadata':metadata,
                                  'manifest':entry}
    (ROOT/'assets/skills_provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    (ROOT/'addon/materials/microduck/skills_provenance.txt').write_text(json.dumps(provenance,indent=2)+'\n')
    packaged=ROOT/'addon/data_static/microduck_skills'
    packaged.mkdir(parents=True,exist_ok=True)
    (packaged/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    (packaged/'upstream_manifest.json').write_bytes(manifest_path.read_bytes())
    print(json.dumps({k:v['sha256'] for k,v in provenance['policies'].items()},indent=2))
    if check:check_parity()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--fetch',action='store_true');p.add_argument('--check',action='store_true')
    args=p.parse_args();main(args.fetch,args.check)
