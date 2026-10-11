"""Independently reload every actual netlist and cross-check printed cell statistics."""
import base64,gzip,json,os,re,subprocess
from pathlib import Path
root=Path(__file__).resolve().parent;r=root/'results';b=root/'build';records=json.loads((r/'resources.json').read_text());logs=[];checks=[]
nets=json.loads(gzip.decompress(base64.b64decode((r/'netlists.json.gz.b64').read_text())))
for row in records:
 name=f"w{row['width']}_n4_m{row['mode']}_{row['flow']}"
 compact=b/(name+'_retained.json');compact.write_text(json.dumps(nets[name]))
 script=f'read_json build/{name}_retained.json\n'
 if row['flow']!='generic':script+='read_verilog -lib -overwrite +/xilinx/cells_sim.v +/xilinx/cells_xtra.v\n'
 script+='hierarchy -top dot_engine\ncheck -assert\nstat\n'
 path=b/(name+'_readback.ys');path.write_text(script)
 result=subprocess.run([os.environ.get('YOSYS',str(root/'tools/venv/bin/yowasp-yosys')),'-s',str(path)],cwd=root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
 assert result.returncode==0,result.stdout[-3000:]
 assert 'Found and reported 0 problems.' in result.stdout
 assert '=== dot_engine ===' in result.stdout
 section=result.stdout.split('=== dot_engine ===')[-1].split('=== design hierarchy ===')[0]
 counts={name:int(count) for count,name in re.findall(r'^\s*(\d+)\s+(\S+)\s*$',section,re.M)}
 for kind,count in row['types'].items():
  if kind!='$scopeinfo':assert counts.get(kind)==count,(name,kind,count,counts)
 checks.append({'configuration':name,'passed':True,'printed_cell_types':{k:v for k,v in counts.items() if k in row['types']},'commands':script})
 logs.append(name+'\n'+result.stdout)
(r/'netlist_readback.json').write_text(json.dumps(checks,indent=2)+'\n');(r/'netlist_readback.log.gz.b64').write_text(base64.b64encode(gzip.compress('\n'.join(logs).encode(),mtime=0)).decode()+'\n')
print('Thirty netlist structural/statistics readbacks passed')
