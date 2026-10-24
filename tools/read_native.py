from pathlib import Path
import json,statistics
p=Path(r'E:/SteamLibrary/steamapps/common/GarrysMod/garrysmod/data/microduck_dev/native.json')
f=json.loads(p.read_text());z=f[0]['pos'][2]
fall=next((r['t'] for r in f if r['gravity'][2]>-.7 or r['pos'][2]<z-2),None)
out={'seconds':f[-1]['t'],'steps':f[-1]['steps'],'first_fall_s':fall,'median_inference_ms':statistics.median(r['ms'] for r in f),'max_anchor_gap':max(r['gap'] for r in f),'min_live_bodies':min(r['links'] for r in f),'model':f[-1]['model'],'rate':f[-1]['rate'],'start':f[0]['pos'],'finish':f[-1]['pos'],'gravity_final':f[-1]['gravity']}
Path('build/native_verification.json').write_text(json.dumps(out,indent=2))
Path('build/native_frames.json').write_text(json.dumps(f))
print(json.dumps(out,indent=2))
