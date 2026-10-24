"""Summarize recorded in-game evidence, without driving or modifying the game."""
from pathlib import Path
import json, math, struct, statistics

root=Path(__file__).resolve().parents[1]
data=Path(r'E:/SteamLibrary/steamapps/common/GarrysMod/garrysmod/data/microduck_mj')
raw=json.loads((data/'release_live.json').read_text())
samples=raw['samples']
assert samples[-1]['phase']=='complete' and not raw.get('error')
assert all(not s.get('error') for s in samples)
summary={'map':raw['map'],'server_tickrate':1/raw['tick'],
    'simulation_seconds':samples[-1]['simtime'], 'game_seconds':samples[-1]['time'],
    'wall_seconds':samples[-1]['wall'],'neural_steps':samples[-1]['steps'],
    'minimum_trunk_height_m':min(s['pos'][2] for s in samples),
    'maximum_tilt_degrees':math.degrees(math.acos(max(-1,min(1,min(-s['gravity'][2] for s in samples))))),
    'mean_inference_ms':statistics.mean(s['inference_ms'] for s in samples),
    'phases':{},'model_vertices':{}}
for phase in dict.fromkeys(s['phase'] for s in samples):
    group=[s for s in samples if s['phase']==phase]
    if len(group)<2: continue
    first,last=group[0],group[-1]
    duration=last['time']-first['time']
    displacement=math.dist(first['pos'][:2],last['pos'][:2])
    tail=[s for s in group if s['time']>=last['time']-2]
    r=last['rotation'];yaw=math.atan2(r[3],r[0]);err=(yaw-last['heading_target']+math.pi)%(2*math.pi)-math.pi
    summary['phases'][phase]={'seconds':duration,'net_distance_m':displacement,
        'mean_net_speed_m_s':displacement/duration,
        'last_2s_displacement_m':math.dist(tail[0]['pos'][:2],tail[-1]['pos'][:2]),
        'last_2s_mean_speed_m_s':statistics.mean(math.hypot(*s['velocity'][:2]) for s in tail),
        'ending_heading_error_degrees':math.degrees(err)}
for p in (root/'addon/models/microduck/detailed_v5').glob('*.vvd'):
    count=struct.unpack_from('<i',p.read_bytes(),16)[0]
    assert 0<count<65536,(p.name,count)
    summary['model_vertices'][p.stem]=count
summary['maximum_model_vertices']=max(summary['model_vertices'].values())
summary['passed']=summary['minimum_trunk_height_m']>.09 and summary['maximum_tilt_degrees']<15
assert summary['passed'],summary
(root/'build/mujoco_release_final_66.json').write_text(json.dumps(raw,indent=2))
(root/'build/release_qa.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
