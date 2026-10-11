"""Compute paired effects, workload uncertainty and figures from executed metrics."""
import csv,hashlib,json,os
from pathlib import Path
import numpy as np
from sklearn.datasets import load_digits
from reference import planes
root=Path(__file__).resolve().parent;r=root/'results';os.environ.setdefault('MPLCONFIGDIR',str(root/'build/mpl'))
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
rows=json.loads((r/'simulation.json').read_text());resources=json.loads((r/'resources.json').read_text())
lookup={row['run']:row for row in rows};effects=[]
for row in rows:
 if row['mode']!=3 or row['run'].startswith(('stress','gate','exhaustive','convergence')):continue
 prefix=row['run'].rsplit('_',1)[0]
 for baseline in [0,1,2,4,5]:
  br=lookup[prefix+'_'+str(baseline)]
  candidate=(row['lastemit']-row['firstaccept'])/row['emitted'];base=(br['lastemit']-br['firstaccept'])/br['emitted']
  effects.append({'run':row['run'],'baseline':baseline,'width':row['width'],'lanes':row['lanes'],'baseline_cycles_per_group':base,'candidate_cycles_per_group':candidate,'speedup_at_equal_clock':base/candidate,'cycle_reduction_percent':100*(1-candidate/base),'scope':'measured continuous RTL stream; equal-clock ratio, not measured Fmax'})
(r/'effects.json').write_text(json.dumps(effects,indent=2)+'\n')
# Bootstrap independent held-out images, not deterministic duplicate executions.
p=json.loads((root/'fixtures/provenance.json').read_text());images=load_digits().data[np.asarray(p['dataset']['test'])]
rng=np.random.default_rng(991);uncertainty=[];image_rows=[]
for width in [4,8]:
 qx=np.rint(images*((1<<(width-1))-1)/16).astype(np.int64)
 for n in [1,4,8]:
  cycle={m:np.asarray([sum(planes(x[g:g+n],width,m)+1 for g in range(0,64,n)) for x in qx]) for m in [0,1,2,3,4,5]}
  indices=rng.integers(0,len(images),(4000,len(images)))
  for m in [0,1,2,4,5]:
   ratios=cycle[m][indices].mean(axis=1)/cycle[3][indices].mean(axis=1)
   uncertainty.append({'width':width,'lanes':n,'baseline':m,'mean_speedup_at_equal_clock':float(cycle[m].mean()/cycle[3].mean()),'bootstrap_image_95_percent_interval':np.quantile(ratios,[.025,.975]).tolist(),'seed':991,'resamples':4000,'scope':'finite-image sampling uncertainty under fixed checkpoint/data split; analytical for N!=4, independent exact RTL cross-check for N=4; not hardware timing or training uncertainty'})
  for image in range(len(images)):
   image_rows.append({'image':image,'dataset_index':p['dataset']['test'][image],'width':width,'lanes':n,**{f'mode{m}_cycles':int(cycle[m][image]) for m in cycle}})
with (r/'image_cycles.csv').open('w',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=list(image_rows[0]));writer.writeheader();writer.writerows(image_rows)
(r/'uncertainty.json').write_text(json.dumps(uncertainty,indent=2)+'\n')
labels=['Parallel','Fixed serial','Leading only','Zero planes','Bitmap span','Counter span']
fig,axes=plt.subplots(1,3,figsize=(15,4.6))
for m in [1,2,3,4,5]:
 values=[]
 for workload in ['unsigned','low_range','zero_rich','negative']:
  selected=[v for v in rows if v['run'].startswith(workload+'_8_4_') and v['mode']==m]
  values.append(np.mean([(v['lastemit']-v['firstaccept'])/v['emitted'] for v in selected]))
 axes[0].plot(range(4),values,marker='o',label=labels[m])
axes[0].set_xticks(range(4),['Uniform +','Low range','Zero rich','Negative -1'],rotation=20);axes[0].set_ylabel('Measured cycles / four-lane group');axes[0].legend(fontsize=8);axes[0].set_title('Equal-clock service; three input seeds')
for m in [1,2,3,4,5]:
 selected=sorted([d for d in json.loads((r/'density.json').read_text()) if d['width']==8 and d['mode']==m and d['split']=='test'],key=lambda d:d['lanes'])
 axes[1].plot([d['lanes'] for d in selected],[d['mean_planes']+1 for d in selected],marker='o',label=labels[m])
axes[1].set_xlabel('Shared activation lanes');axes[1].set_ylabel('Cycles / group (input-derived)');axes[1].set_title('Digits grouping boundary; N=4 checked in RTL');axes[1].legend(fontsize=8)
selected=sorted([d for d in resources if d['width']==8 and d['flow']=='xcup_dsp'],key=lambda d:d['mode'])
axes[2].bar(range(6),[v['lut'] for v in selected]);axes[2].set_xticks(range(6),[labels[i] for i in range(6)],rotation=35,ha='right');axes[2].set_ylabel('Mapped LUT1–LUT6 cells');axes[2].set_title('Logical Xilinx mapping; no routed timing')
axes[2].set_ylim(0,max(d['lut'] for d in selected)*1.28)
for i,d in enumerate(selected):axes[2].text(i,d['lut']+6,f"FF {d['ff']}\nDSP {d['dsp']}",ha='center',fontsize=8)
fig.tight_layout();fig.savefig(r/'tradeoffs.svg');fig.savefig(root/'build/tradeoffs.png',dpi=150);plt.close(fig)
summary={'rtl_runs':len(rows),'outputs_checked':sum(x['emitted'] for x in rows),'cycles_checked':sum(x['cycles'] for x in rows),'reset_canceled':sum(x['canceled'] for x in rows),'input_stalls':sum(x['installs'] for x in rows),'output_stalls':sum(x['outstalls'] for x in rows),'reset_busy':sum(x['busyreset'] for x in rows),'reset_pending_output':sum(x['outputreset'] for x in rows),'simultaneous_handshakes':sum(x['simultaneous'] for x in rows),'zero_groups':sum(x['zero_groups'] for x in rows),'negative_groups':sum(x['negative_groups'] for x in rows),'synthesis_configurations':len(resources),'latches':sum(x['latches'] for x in resources),'application':json.loads((r/'application.json').read_text()),'main_resources':[x for x in resources if x['width']==8],'application_effects':[x for x in effects if x['run'].startswith('app_8_dense_')],'formal':json.loads((r/'formal.json').read_text())}
(r/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k not in ['application','formal']},indent=2))
