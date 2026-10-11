"""Bounded reduced-width numerical, ordering and tag checks on actual RTL."""
import base64,gzip,json,os,subprocess
from pathlib import Path
root=Path(__file__).resolve().parent;logs=[];records=[]
for mode in range(6):
 design='rtl/counter_engine.sv' if mode==5 else 'rtl/dot_engine.sv'
 script=f'read_verilog -formal -sv {design} formal/numeric.sv\nchparam -set MODE {mode} proof\nprep -top proof -flatten\nasync2sync\nchformal -lower\ndffunmap\nsat -seq 12 -set-init-zero -prove-asserts -verify\n'
 path=root/f'build/proof_{mode}.ys';path.write_text(script)
 r=subprocess.run([os.environ.get('YOSYS',str(root/'tools/venv/bin/yowasp-yosys')),'-s',str(path)],cwd=root,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
 logs.append(r.stdout);assert r.returncode==0,r.stdout[-4000:]
 assert 'SUCCESS!' in r.stdout
 records.append({'mode':mode,'width':3,'lanes':1,'steps':12,'passed':True,'commands':script,'scope':'bounded numeric output/tag and outstanding-work correctness; arbitrary reset, input and ready; zero initial state'})
(root/'results/formal.json').write_text(json.dumps(records,indent=2)+'\n')
(root/'results/formal.log.gz.b64').write_text(base64.b64encode(gzip.compress('\n'.join(logs).encode(),mtime=0)).decode()+'\n')
print('Six bounded numerical checks passed')
