"""Map the main point with DSP inference enabled as a target-resource sensitivity."""
import base64,gzip,hashlib,json,os,re,subprocess
from pathlib import Path
root=Path(__file__).resolve().parent;r=root/'results';b=root/'build'
resources=json.loads((r/'resources.json').read_text());scripts=json.loads((r/'synthesis_scripts.json').read_text())
netlists=json.loads(gzip.decompress(base64.b64decode((r/'netlists.json.gz.b64').read_text())));logs=gzip.decompress(base64.b64decode((r/'synthesis.log.gz.b64').read_text())).decode()
for mode in range(5):
 name=f'w8_n4_m{mode}_xcup_dsp';net=b/(name+'.json')
 script=f'read_verilog -sv rtl/dot_engine.sv\nchparam -set W 8 -set N 4 -set MODE {mode} dot_engine\nsynth_xilinx -top dot_engine -family xcup -flatten -noiopad\ncheck -assert\nstat\nwrite_json {net}\n'
 path=b/(name+'.ys');path.write_text(script);print(name,flush=True)
 result=subprocess.run([os.environ.get('YOSYS',str(root/'tools/venv/bin/yowasp-yosys')),'-s',str(path)],cwd=root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=600)
 assert result.returncode==0,result.stdout[-5000:];logs+='\n'+name+'\n'+result.stdout
 d=json.loads(net.read_text());types={}
 for cell in d['modules']['dot_engine']['cells'].values():types[cell['type']]=types.get(cell['type'],0)+1
 assert not any('LATCH' in t.upper() for t in types)
 resources.append({'width':8,'lanes':4,'mode':mode,'flow':'xcup_dsp','cells':sum(types.values()),'types':types,'latches':0,'netlist_sha256':hashlib.sha256(net.read_bytes()).hexdigest(),'lut':sum(v for k,v in types.items() if re.fullmatch(r'LUT[1-6]',k)),'ff':sum(v for k,v in types.items() if k.startswith(('FDRE','FDSE','FDCE','FDPE'))),'dsp':sum(v for k,v in types.items() if k.startswith('DSP'))})
 scripts.append({'configuration':name,'commands':script.replace(str(root),'.')});netlists[name]=d
(r/'resources.json').write_text(json.dumps(resources,indent=2)+'\n');(r/'synthesis_scripts.json').write_text(json.dumps(scripts,indent=2)+'\n')
(r/'netlists.json.gz.b64').write_text(base64.b64encode(gzip.compress(json.dumps(netlists,separators=(',',':')).encode(),mtime=0)).decode()+'\n')
(r/'synthesis.log.gz.b64').write_text(base64.b64encode(gzip.compress(logs.encode(),mtime=0)).decode()+'\n')
# Execute the independently implemented counter baseline before final analysis.
import sys
subprocess.run([sys.executable,root/'counter_comparison.py'],check=True,cwd=root)
