"""Generate paired effects and figures from actual emitted RTL measurements."""
import csv
import json
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parent
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'build/mpl'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

R=ROOT/'results'


def main():
    sim=json.loads((R/'simulation.json').read_text())
    app=json.loads((R/'application.json').read_text())
    resources=json.loads((R/'resources.json').read_text())
    records=list(csv.DictReader((R/'image_cycles.csv').open()))
    effects=[]
    pairs=[('bitmap','qualified_bitmap'),('counter','qualified_counter'),
           ('qualified_counter','qualified_bitmap'),('counter','qualified_bitmap'),
           ('parallel','qualified_bitmap')]
    rng=np.random.default_rng(991)
    boot=rng.integers(0,360,size=(4000,360))
    for width,lanes in [(8,4),(4,4),(8,8)]:
        for policy in ['dense','index']:
            for baseline,candidate in pairs:
                seed_rows=[]
                before=[];after=[]
                for model_seed in [7,31,97]:
                    b=next(x for x in app if (x['width'],x['lanes'],x['policy'],x['model_seed'],x['variant'])==(width,lanes,policy,model_seed,baseline))
                    c=next(x for x in app if (x['width'],x['lanes'],x['policy'],x['model_seed'],x['variant'])==(width,lanes,policy,model_seed,candidate))
                    ratio=b['mean_cycles_per_block']/c['mean_cycles_per_block']
                    seed_rows.append(dict(model_seed=model_seed,baseline_cycles=b['mean_cycles_per_block'],candidate_cycles=c['mean_cycles_per_block'],equal_clock_throughput_ratio=ratio))
                    arrays=[]
                    for variant in [baseline,candidate]:
                        rows=[x for x in records if (int(x['width']),int(x['lanes']),x['policy'],int(x['model_seed']),x['variant'])==(width,lanes,policy,model_seed,variant)]
                        assert len(rows)==360
                        arrays.append(np.array([int(x['service_cycles']) for x in rows],dtype=np.int64))
                    before.append(arrays[0]);after.append(arrays[1])
                # Pair by image and keep all model seeds together, rather than treating class blocks as independent.
                b=np.mean(before,axis=0);c=np.mean(after,axis=0)
                ratio=float(b.sum()/c.sum())
                estimates=b[boot].sum(axis=1)/c[boot].sum(axis=1)
                ci=np.quantile(estimates,[.025,.975]).tolist()
                entry=dict(width=width,lanes=lanes,policy=policy,baseline=baseline,candidate=candidate,
                           baseline_cycles_per_block=float(np.mean([x['baseline_cycles'] for x in seed_rows])),
                           candidate_cycles_per_block=float(np.mean([x['candidate_cycles'] for x in seed_rows])),
                           equal_clock_throughput_ratio=ratio,cycles_saved_percent=100*(1-1/ratio),
                           fixed_checkpoint_image_bootstrap_95=ci,seed_results=seed_rows,
                           seed_ratio_range=[min(x['equal_clock_throughput_ratio'] for x in seed_rows),max(x['equal_clock_throughput_ratio'] for x in seed_rows)],
                           bootstrap_seed=991,resamples=4000,
                           uncertainty_scope='Paired image resampling, all three checkpoints fixed; not a writer-independent, training-population or board-timing confidence interval')
                if width in [4,8] and lanes in [4,8] and baseline!='parallel':
                    f=lambda variant:next(x for x in resources if (x['width'],x['lanes'],x['variant'],x['flow'])==(width,lanes,variant,'xcup_nodsp'))
                    br,cr=f(baseline),f(candidate)
                    entry.update(baseline_lut=br['lut'],candidate_lut=cr['lut'],baseline_ff=br['ff'],candidate_ff=cr['ff'],
                                 equal_clock_throughput_per_lut_ratio=ratio*br['lut']/cr['lut'],
                                 break_even_candidate_over_baseline_frequency=1/ratio)
                effects.append(entry)
    (R/'effects.json').write_text(json.dumps(effects,indent=2)+'\n')
    with (R/'comparison.csv').open('w') as f:
        fields=['width','lanes','policy','baseline','candidate','baseline_cycles_per_block','candidate_cycles_per_block',
                'equal_clock_throughput_ratio','cycles_saved_percent','baseline_lut','candidate_lut','baseline_ff','candidate_ff',
                'equal_clock_throughput_per_lut_ratio','break_even_candidate_over_baseline_frequency']
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(effects)
    fig,axes=plt.subplots(1,3,figsize=(15,4.5))
    variants=['parallel','fixed','counter','qualified_counter','bitmap','qualified_bitmap']
    short=['Parallel','Fixed','Span','Q-span','Bitmap','Q-bitmap']
    for i,policy in enumerate(['dense','index']):
        heights=[np.mean([x['mean_cycles_per_block'] for x in app if x['width']==8 and x['lanes']==4 and x['policy']==policy and x['variant']==v]) for v in variants]
        axes[0].bar(np.arange(6)+(i-.5)*.38,heights,width=.38,label='Dense' if policy=='dense' else 'Pruned')
    axes[0].set_xticks(range(6),short,rotation=35,ha='right');axes[0].set_ylabel('RTL service cycles / block (lower is better)');axes[0].legend()
    axes[0].set_title('Public digits, W8/N4, three checkpoints')
    for kind,style in [('unsigned','-'),('signed','--'),('negative',':')]:
        gains=[]
        for p in [0,25,50,75,100]:
            select=lambda v:[x['mean_latency'] for x in sim if x['run'].startswith(f'sweep_{kind}_p{p}_') and x['variant']==v]
            gains.append(np.mean(select('bitmap'))/np.mean(select('qualified_bitmap')))
        axes[1].plot([0,25,50,75,100],gains,style,marker='o',label=kind)
    axes[1].set_xlabel('Generated zero-weight percentage');axes[1].set_ylabel('Equal-clock throughput ratio vs bitmap');axes[1].legend();axes[1].set_title('Synthetic failure-boundary sweep')
    for v in ['counter','qualified_counter','bitmap','qualified_bitmap']:
        resource=next(x for x in resources if x['width']==8 and x['lanes']==4 and x['variant']==v and x['flow']=='xcup_nodsp')
        c=np.mean([x['mean_cycles_per_block'] for x in app if x['width']==8 and x['lanes']==4 and x['policy']=='index' and x['variant']==v])
        axes[2].scatter(resource['lut'],c);axes[2].annotate(v.replace('qualified_','Q-'),(resource['lut'],c),xytext=(4,4),textcoords='offset points',fontsize=8)
    axes[2].set_xlabel('Yosys xcup logical LUT count');axes[2].set_ylabel('RTL service cycles / block');axes[2].set_title('Pruned workloads: cost vs service cycles')
    for ax in axes:ax.grid(alpha=.2)
    fig.suptitle('Weight-qualified bit-plane scheduling; no routed timing or physical-board measurement')
    fig.tight_layout();fig.savefig(R/'tradeoffs.svg',metadata={'Date':None});plt.close(fig)
    summary=dict(simulation_runs=len(sim),checked_outputs=sum(x['emitted'] for x in sim),checked_cycles=sum(x['cycles'] for x in sim),
                 reset_canceled=sum(x['canceled'] for x in sim),synthesis_configurations=len(resources),
                 generic_netlist_replays=sum(x['scope']=='generic netlist' for x in sim),
                 application_runs=len(app),application_outputs=sum(x['block_outputs'] for x in app),
                 coverage={k:sum(x[k] for x in sim) for k in ['busyreset','outputreset','outstalls','installs','zero_groups','negative_groups','zero_weights','excluded_nonzero','qualified_zero','reduced_planes']},
                 primary=[x for x in effects if x['width']==8 and x['lanes']==4 and x['policy']=='index'],
                 claims='Exact signed block-dot RTL evidence and logical mapping; no end-to-end FPGA inference, timing, power, or new training results')
    (R/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
