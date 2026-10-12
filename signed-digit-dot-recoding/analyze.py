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
    pairs=[('tc_bitmap','sm_bitmap'),('tc_counter','sm_counter'),('sm_counter','sm_bitmap'),('booth_bitmap','sm_bitmap'),('booth_counter','booth_bitmap'),('tc_bitmap','booth_bitmap'),('parallel','sm_bitmap')]
    rng=np.random.default_rng(991)
    boot=rng.integers(0,360,size=(4000,360))
    for width,lanes in [(8,4),(4,4),(8,8)]:
        for activation in ['tanh','relu']:
            for baseline,candidate in pairs:
                seed_rows=[]
                before=[];after=[]
                for model_seed in [7,31,97]:
                    b=next(x for x in app if (x['width'],x['lanes'],x['activation'],x['model_seed'],x['variant'])==(width,lanes,activation,model_seed,baseline))
                    c=next(x for x in app if (x['width'],x['lanes'],x['activation'],x['model_seed'],x['variant'])==(width,lanes,activation,model_seed,candidate))
                    ratio=b['mean_cycles_per_block']/c['mean_cycles_per_block']
                    seed_rows.append(dict(model_seed=model_seed,baseline_cycles=b['mean_cycles_per_block'],candidate_cycles=c['mean_cycles_per_block'],equal_clock_throughput_ratio=ratio))
                    arrays=[]
                    for variant in [baseline,candidate]:
                        rows=[x for x in records if (int(x['width']),int(x['lanes']),x['activation'],int(x['model_seed']),x['variant'])==(width,lanes,activation,model_seed,variant)]
                        assert len(rows)==360
                        arrays.append(np.array([int(x['service_cycles']) for x in rows],dtype=np.int64))
                    before.append(arrays[0]);after.append(arrays[1])
                # Pair by image and keep all model seeds together, rather than treating class blocks as independent.
                b=np.mean(before,axis=0);c=np.mean(after,axis=0)
                ratio=float(b.sum()/c.sum())
                estimates=b[boot].sum(axis=1)/c[boot].sum(axis=1)
                ci=np.quantile(estimates,[.025,.975]).tolist()
                entry=dict(width=width,lanes=lanes,activation=activation,baseline=baseline,candidate=candidate,
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
        fields=['width','lanes','activation','baseline','candidate','baseline_cycles_per_block','candidate_cycles_per_block',
                'equal_clock_throughput_ratio','cycles_saved_percent','baseline_lut','candidate_lut','baseline_ff','candidate_ff',
                'equal_clock_throughput_per_lut_ratio','break_even_candidate_over_baseline_frequency']
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(effects)
    fig,axes=plt.subplots(1,3,figsize=(15,4.7))
    variants=['parallel','tc_fixed','tc_counter','sm_counter','booth_counter','tc_bitmap','sm_bitmap','booth_bitmap']
    short=['Parallel','Fixed','TC-span','SM-span','B4-span','TC-bit','SM-bit','B4-bit']
    for i,activation in enumerate(['tanh','relu']):
        heights=[np.mean([x['mean_cycles_per_block'] for x in app if x['width']==8 and x['lanes']==4 and x['activation']==activation and x['variant']==v]) for v in variants]
        axes[0].bar(np.arange(8)+(i-.5)*.38,heights,width=.38,label=activation)
    axes[0].set_xticks(range(8),short,rotation=45,ha='right');axes[0].set_ylabel('RTL service cycles / block');axes[0].legend()
    axes[0].set_title('New MLP output-layer traces, W8/N4')
    for bound,style in [(3,'-'),(31,'--'),(127,':')]:
        gains=[]
        for fraction in [0,50,100]:
            select=lambda v:[x['mean_latency'] for x in sim if x['run'].startswith(f'sweep_b{bound}_neg{fraction}_zero0_') and x['variant']==v]
            gains.append(np.mean(select('tc_bitmap'))/np.mean(select('sm_bitmap')))
        axes[1].plot([0,50,100],gains,style,marker='o',label=f'max magnitude {bound}')
    axes[1].set_xlabel('Generated negative-sign probability (%)');axes[1].set_ylabel('Equal-clock SM / TC throughput ratio');axes[1].legend();axes[1].set_title('Nonzero-weight sign/range sensitivity')
    for v in ['tc_bitmap','tc_counter','sm_bitmap','sm_counter','booth_bitmap','booth_counter']:
        resource=next(x for x in resources if x['width']==8 and x['lanes']==4 and x['variant']==v and x['flow']=='xcup_nodsp')
        c=np.mean([x['mean_cycles_per_block'] for x in app if x['width']==8 and x['lanes']==4 and x['activation']=='tanh' and x['variant']==v])
        axes[2].scatter(resource['lut'],c)
        is_counter=v.endswith('counter')
        offset=((-10,12) if is_counter else (10,-18)) if v.startswith('sm_') else ((-6,-12) if is_counter else (6,6))
        axes[2].annotate(v,(resource['lut'],c),xytext=offset,
                         ha='right' if is_counter else 'left',textcoords='offset points',fontsize=7,
                         arrowprops={'arrowstyle':'-','color':'0.4','lw':.6})
    axes[2].margins(x=.3,y=.2)
    axes[2].set_xlabel('Yosys xcup logical LUT count');axes[2].set_ylabel('RTL service cycles / block');axes[2].set_title('Tanh: conversion cost vs cycle benefit')
    for ax in axes:ax.grid(alpha=.2)
    fig.suptitle('Exact signed recoding: TC, magnitude and radix-4 Booth; no routed timing or board measurements')
    fig.tight_layout();fig.savefig(R/'tradeoffs.svg',metadata={'Date':None});fig.savefig(ROOT/'build/tradeoffs.png',dpi=120);plt.close(fig)
    summary=dict(simulation_runs=len(sim),checked_outputs=sum(x['emitted'] for x in sim),checked_cycles=sum(x['cycles'] for x in sim),
                 reset_canceled=sum(x['canceled'] for x in sim),synthesis_configurations=len(resources),
                 generic_netlist_replays=sum(x['scope']=='generic netlist' for x in sim),
                 application_runs=len(app),application_outputs=sum(x['block_outputs'] for x in app),
                 coverage={k:sum(x[k] for x in sim) for k in ['busyreset','outputreset','outstalls','installs','zero_groups','negative_groups','zero_weights','excluded_nonzero','qualified_zero','reduced_planes']},
                 primary=[x for x in effects if x['width']==8 and x['lanes']==4 and x['activation']=='tanh'],
                 claims='Exact signed block-dot RTL evidence and logical mapping; new small-MLP workloads, not hardware-aware learning; no end-to-end FPGA inference, timing or power')
    (R/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    config={'primary':{'width':8,'lanes':4,'activation':'tanh','model_seeds':[7,31,97]},
            'public_cases':[[8,4],[4,4],[8,8]],'activation_controls':['tanh','relu'],
            'synthetic':{'magnitude_limits':[3,31,127],'negative_sign_probability':[0,.5,1],
                         'zero_weight_probability':[0,.5],'stimulus_seeds':[7,31,97],'groups':256},
            'seed_roles':{'simulation_seed_field':'SV readiness-driver seed; distinct from workload/model generation',
                          'default_driver_seed':7,'stress_stimulus_and_driver':4242,'odd_width_stimulus':313,
                          'startup_drain_stimulus':2718,'generic_netlist_stimulus_and_driver':97,
                          'gradient_test':119,'image_bootstrap':991},
            'confidence':'Paired image bootstrap, 4000 resamples, all three checkpoints fixed',
            'all_mapped_bram_cells':sum(n for row in resources if row['flow']!='generic' for kind,n in row['types'].items() if kind.startswith('RAMB'))}
    (R/'experiment_config.json').write_text(json.dumps(config,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
