"""Reexecute the statically cleaned parallel baseline and replace its measurements."""
import reproduce as e
import base64,gzip,hashlib,json,re
import numpy as np
from sklearn.datasets import load_digits
from pathlib import Path
r=e.RESULTS;b=e.BUILD;rtl=e.ROOT/'rtl/dot_engine.sv'
e.SIM.extend([x for x in json.loads((r/'simulation.json').read_text()) if x['mode']!=0]);e.COMMANDS.extend(json.loads((r/'commands.json').read_text()));e.LOG.append((r/'simulation.log').read_text())
for width in [4,8]:
 for lanes in [1,4,8]:
  for workload in ['signed','unsigned','low_range','zero_rich','negative','phases']:
   for seed in [7,31,97]:e.execute(e.synthetic(width,lanes,workload,seed),width,lanes,0,f'{workload}_{width}_{lanes}_{seed}_0',rtl=rtl,suffix='parallelclean')
  for traffic in [1,2]:e.execute(e.synthetic(width,lanes,'stress',4242),width,lanes,0,f'stress_{width}_{lanes}_0_{traffic}',traffic,1,4242,rtl,'parallelclean')
e.execute(e.synthetic(8,4,'zero_rich',2718,4096),8,4,0,'convergence_0',rtl=rtl,suffix='parallelclean')
e.execute([([x],[w]) for x in range(-8,8) for w in range(-8,8)],4,1,0,'exhaustive_0',rtl=rtl,suffix='parallelclean')
models=json.loads((e.ROOT/'fixtures/checkpoints.json').read_text());p=json.loads((e.ROOT/'fixtures/provenance.json').read_text());digits=load_digits();ids=p['dataset']['test'];application=[x for x in json.loads((r/'application.json').read_text()) if x['mode']!=0]
for width in [4,8]:
 qmax=(1<<(width-1))-1;qx=np.rint(digits.data[ids]*qmax/16).astype(np.int64)
 for policy in ['dense','index']:
  m=models[f'7_{policy}_recovered'];fw=np.asarray(m['weights']);scales=np.maximum(np.abs(fw).max(axis=1),1e-30)/qmax;qw=np.rint(fw/scales[:,None]).clip(-qmax,qmax).astype(np.int64)
  transactions=[(qx[i,g:g+4].tolist(),qw[c,g:g+4].tolist()) for i in range(360) for c in range(10) for g in range(0,64,4)]
  rows=e.execute(transactions,width,4,0,f'app_{width}_{policy}_0',rtl=rtl,suffix='parallelclean');actual=np.asarray([int(x['actual_sum']) for x in rows]).reshape(360,10,16).sum(axis=2);assert np.array_equal(actual,qx@qw.T)
  pred=(actual*scales[None,:]/qmax+np.asarray(m['bias'])).argmax(axis=1)
  application.append({'width':width,'policy':policy,'mode':0,'samples':360,'correct':int((pred==digits.target[ids]).sum()),'block_outputs':len(rows),'prediction_changes':0,'raw_dots_sha256':hashlib.sha256(actual.astype('<i8').tobytes()).hexdigest(),'scope':'clean parallel RTL block dots; host class reduction/scaling/bias'})
resources=[x for x in json.loads((r/'resources.json').read_text()) if x['mode']!=0];scripts=[x for x in json.loads((r/'synthesis_scripts.json').read_text()) if '_m0_' not in x['configuration']];nets=json.loads(gzip.decompress(base64.b64decode((r/'netlists.json.gz.b64').read_text())));logs=gzip.decompress(base64.b64decode((r/'synthesis.log.gz.b64').read_text())).decode()
pieces=re.split(r'(?m)^(w[48]_n4_m[0-5]_(?:generic|xcup_nodsp|xcup_dsp))\n',logs)
log_sections={pieces[i]:pieces[i+1] for i in range(1,len(pieces),2) if '_m0_' not in pieces[i]}
for width,flow in [(4,'generic'),(4,'xcup_nodsp'),(8,'generic'),(8,'xcup_nodsp'),(8,'xcup_dsp')]:
 name=f'w{width}_n4_m0_{flow}';net=b/(name+'.json');ver=b/(name+'.v');script=f'read_verilog -sv rtl/dot_engine.sv\nchparam -set W {width} -set N 4 -set MODE 0 dot_engine\n'
 script+=('synth -top dot_engine -flatten\n' if flow=='generic' else 'synth_xilinx -top dot_engine -family xcup -flatten -noiopad '+('-nodsp' if flow=='xcup_nodsp' else '')+'\n')
 script+=f'check -assert\nstat\nwrite_json {net}\nwrite_verilog -noattr {ver}\n';path=b/(name+'.ys');path.write_text(script);print(name,flush=True);log_sections[name]=e.run([e.YOSYS,'-s',path]);d=json.loads(net.read_text());types={}
 for cell in d['modules']['dot_engine']['cells'].values():types[cell['type']]=types.get(cell['type'],0)+1
 assert not any('LATCH' in t.upper() for t in types)
 resources.append({'width':width,'lanes':4,'mode':0,'flow':flow,'cells':sum(types.values()),'types':types,'latches':0,'netlist_sha256':hashlib.sha256(net.read_bytes()).hexdigest(),'lut':sum(v for k,v in types.items() if re.fullmatch(r'LUT[1-6]',k)) if flow!='generic' else None,'ff':sum(v for k,v in types.items() if k.startswith(('FDRE','FDSE','FDCE','FDPE'))) if flow!='generic' else None,'dsp':sum(v for k,v in types.items() if k.startswith('DSP')) if flow!='generic' else None})
 scripts.append({'configuration':name,'commands':script.replace(str(e.ROOT),'.')});nets[name]=d
 if flow=='generic':e.execute(e.synthetic(width,4,'stress',97),width,4,0,f'gate_{width}_0',2,1,97,ver,'parallelcleangate')
for filename,obj in [('simulation.json',e.SIM),('commands.json',e.COMMANDS),('resources.json',resources),('synthesis_scripts.json',scripts),('application.json',application)]: (r/filename).write_text(json.dumps(obj,indent=2)+'\n')
(r/'simulation.log').write_text('\n'.join(e.LOG));(r/'netlists.json.gz.b64').write_text(base64.b64encode(gzip.compress(json.dumps(nets,separators=(',',':')).encode(),mtime=0)).decode()+'\n');(r/'synthesis.log.gz.b64').write_text(base64.b64encode(gzip.compress(''.join(k+'\n'+v for k,v in log_sections.items()).encode(),mtime=0)).decode()+'\n')
