import build_assets as b
import json
r=json.loads((b.ADDON/'materials/microduck/robot.txt').read_text())
r['model_dir']='microduck/'+b.REVISION
b.write_json(b.ADDON/'materials/microduck/robot.txt',r)
b.write_lua_data('robot',r)
for l in r['links']:
    p=b.BUILD/l['name']/'model.qc'
    lines=p.read_text().splitlines()
    lines[0]=f'$modelname "{r["model_dir"]}/{l["name"]}.mdl"'
    lines=[x for x in lines if not x.startswith('$origin')]
    lines.insert(1,'$origin 0 0 0 -90')
    p.write_text('\n'.join(lines)+'\n')
b.compile_models(r)
print('Recompiled',r['model_dir'])
