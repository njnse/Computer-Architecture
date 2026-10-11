"""Retain actual flattened designs; tool-pinned primitive libraries are reloaded."""
import base64,gzip,hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent;r=root/'results';p=r/'netlists.json.gz.b64'
nets=json.loads(gzip.decompress(base64.b64decode(p.read_text())))
nets={k:{'creator':v.get('creator'),'modules':{'dot_engine':v['modules']['dot_engine']}} for k,v in nets.items()}
p.write_text(base64.b64encode(gzip.compress(json.dumps(nets,separators=(',',':')).encode(),mtime=0)).decode()+'\n')
resources=json.loads((r/'resources.json').read_text())
for row in resources:
 key=f"w{row['width']}_n4_m{row['mode']}_{row['flow']}"
 row['retained_design_sha256']=hashlib.sha256(json.dumps(nets[key],sort_keys=True,separators=(',',':')).encode()).hexdigest()
(r/'resources.json').write_text(json.dumps(resources,indent=2)+'\n')
print('Thirty flattened design netlists retained without redundant tool libraries')
