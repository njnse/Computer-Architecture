"""Execute the exact RTL experiment, scoreboards, synthesis, and bounded checks."""
import base64
import csv
import gzip
import hashlib
import itertools
import json
import os
import platform
import random
import re
import subprocess
import sys
from pathlib import Path

for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
import numpy as np
from reference import VARIANTS,cycles,dot,pack
from train_models import CONFIG,forward,load_workload

ROOT = Path(__file__).resolve().parent
B = ROOT / 'build'
R = ROOT / 'results'
B.mkdir(exist_ok=True)
R.mkdir(exist_ok=True)
os.environ.setdefault('XDG_CACHE_HOME', str(B / 'cache'))
os.environ.setdefault('MPLCONFIGDIR', str(B / 'mpl'))
IV = os.environ.get('IVERILOG', str(ROOT/'tools/iverilog/usr/bin/iverilog'))
BASE = os.environ.get('IVL_BASE', str(ROOT/'tools/iverilog/usr/lib/x86_64-linux-gnu/ivl'))
VVP = os.environ.get('VVP', str(ROOT/'tools/iverilog/usr/bin/vvp'))
YOSYS = os.environ.get('YOSYS', str(ROOT/'tools/venv/bin/yowasp-yosys'))
SIM, COMMANDS, COMPILED = [], [], {}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, value):
    (R/name).write_text(json.dumps(value, indent=2)+'\n')


def run(args, timeout=600, allow_failure=False):
    args = list(map(str, args))
    p = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, timeout=timeout)
    COMMANDS.append({'argv':[x.replace(str(ROOT), '.') for x in args], 'returncode':p.returncode})
    with (R/'execution.log').open('a') as f:
        f.write('COMMAND '+json.dumps(COMMANDS[-1])+'\n'+p.stdout+'\n')
    if p.returncode and not allow_failure:
        raise RuntimeError(p.stdout[-6000:])
    return p


def source(variant):
    return ROOT/('rtl/booth_engine.sv' if VARIANTS[variant][2]=='booth' else ('rtl/counter_engine.sv' if VARIANTS[variant][0]==5 else 'rtl/dot_engine.sv'))


def binary(width, lanes, variant, rtl=None, suffix=''):
    key = (width, lanes, variant, suffix)
    if key not in COMPILED:
        mode,magnitude,representation=VARIANTS[variant]
        path = B/f'sim_w{width}_n{lanes}_{variant}{suffix}.vvp'
        netlist = rtl and Path(rtl).suffix == '.v'
        run([IV]+(['-DNETLIST'] if netlist else [])+['-B',BASE,'-g2012','-s','check',
             f'-Pcheck.W={width}',f'-Pcheck.N={lanes}',f'-Pcheck.MODE={mode}',
             f'-Pcheck.MAGNITUDE={magnitude}','-o',path,rtl or source(variant),'tb/check.sv'])
        COMPILED[key] = path
    return COMPILED[key]


def execute(transactions, width, lanes, variant, name, traffic=0, resets=0, seed=7,
            rtl=None, suffix='', wave=False, expected_failure=False):
    stimulus, output = B/(name+'.txt'), B/(name+'.csv')
    stimulus.write_text(''.join(f'{pack(x,width):x} {pack(w,width):x} {dot(x,w)}\n' for x,w in transactions))
    args = [VVP,binary(width,lanes,variant,rtl,suffix),f'+input={stimulus}',f'+output={output}',
            f'+seed={seed}',f'+traffic={traffic}',f'+resets={resets}']
    if wave:
        args.append(f'+wave={R}/protocol.vcd')
    p = run(args, allow_failure=expected_failure)
    if expected_failure:
        if not p.returncode or not re.search(r'(score mismatch|stalled output changed|unsolicited result)',p.stdout):
            raise AssertionError('Mutation was not rejected by a functional checker: '+p.stdout[-1000:])
        return {'detected':True,'diagnostic':p.stdout[-1800:],'returncode':p.returncode}
    values = {k:int(v) for k,v in re.findall(r'(\w+)=(-?\d+)',p.stdout)}
    assert 'PASS' in p.stdout and values['emitted']+values['canceled']==len(transactions)
    rows = list(csv.DictReader(output.open()))
    mode,magnitude,representation=VARIANTS[variant]
    for row in rows:
        ordinal = int(row['ordinal'])
        xs, ws = transactions[ordinal]
        assert int(row['actual_sum']) == dot(xs,ws)
        if traffic==0 and not resets:
            assert int(row['latency'])==cycles(xs,ws,width,variant), (name,ordinal,row)
    if traffic==0 and not resets:
        predicted = sum(cycles(x,w,width,variant) for x,w in transactions[:-1])
        assert values['lastaccept']-values['firstaccept']==predicted
    values.update(run=name,width=width,lanes=lanes,variant=variant,traffic=traffic,resets=resets,seed=seed,
                  stimulus_sha256=sha(stimulus),output_sha256=sha(output),
                  mean_latency=values['total_latency']/values['emitted'],
                  accept_interval=(values['lastaccept']-values['firstaccept'])/(len(transactions)-1),
                  scope='RTL' if rtl is None else 'generic netlist')
    SIM.append(values)
    with (R/'simulation.jsonl').open('a') as f:
        f.write(json.dumps(values)+'\n')
    return rows


def synthetic(width,lanes,bound,negative,sparsity,seed,count=256,directed=False):
    rng=random.Random(seed);low=-(1<<(width-1));high=(1<<(width-1))-1
    bound=min(bound,high);result=[]
    if directed:
        result=[([low]*lanes,[low]*lanes),([-1]*lanes,[1]*lanes),([high]*lanes,[1]*lanes),
                ([0]*lanes,[low]*lanes),([-1]*lanes,[0]*lanes),([low]*lanes,[0]+[low]*(lanes-1))]
        result += [([1<<b if b<width-1 else low]*lanes,[low]*lanes) for b in range(width)]
    while len(result)<count:
        xs=[]
        for _ in range(lanes):
            m=rng.randrange(bound+1);xs.append(-m if rng.random()<negative else m)
        ws=[0 if rng.random()<sparsity else rng.choice(list(range(low,0))+list(range(1,high+1))) for _ in range(lanes)]
        result.append((xs,ws))
    return result


def simulations():
    p=run([sys.executable,'-m','unittest','discover','-s','tests','-v'])
    (R/'python_tests.log').write_text(p.stdout)
    for bound,negative,sparsity,seed in itertools.product([3,31,127],[0,.5,1],[0,.5],[7,31,97]):
        tx=synthetic(8,4,bound,negative,sparsity,seed)
        for variant in VARIANTS:
            name=f'sweep_b{bound}_neg{int(100*negative)}_zero{int(100*sparsity)}_s{seed}_{variant}'
            execute(tx,8,4,variant,name)
    for width,lanes in itertools.product([4,8],[1,4,8]):
        tx=synthetic(width,lanes,127,.5,.5,4242,512,True)
        for variant in VARIANTS:
            for traffic in [1,2]:
                execute(tx,width,lanes,variant,f'stress_w{width}_n{lanes}_{variant}_t{traffic}',traffic,1,4242,
                        wave=(width==8 and lanes==4 and variant=='sm_bitmap' and traffic==2))
    exhaustive=[([x0,x1],[w0,w1]) for x0,x1,w0,w1 in itertools.product(range(-4,4),repeat=4)]
    for variant in VARIANTS:
        execute(exhaustive,3,2,variant,'exhaustive_'+variant)
        execute(synthetic(5,2,15,.5,.5,313,512,True),5,2,variant,'odd5_'+variant)
        for count in [512,4096]:
            execute(synthetic(8,4,31,.5,.5,2718,count),8,4,variant,f'length_{count}_{variant}')
    mutations=[]
    faults=[('sm_sign_plane','sm_bitmap','if(!MAGNITUDE&&plane==W-1)','if(plane==W-1)',8,4),
            ('sm_narrow_weight','sm_bitmap','SW=W+MAGNITUDE','SW=W',8,4),
            ('stalled_overwrite','sm_bitmap','(!out_valid||out_ready)',"1'b1",8,4),
            ('booth_double_digit','booth_bitmap',"3'b011:digit=3'sd2;","3'b011:digit=3'sd1;",8,4),
            ('booth_top_extension','booth_bitmap','else if(pos>=W)get_bit=x[W-1];','else if(pos>=W)get_bit=0;',3,2)]
    for name,variant,old,new,width,lanes in faults:
        text=source(variant).read_text();assert old in text
        path=B/(name+'.sv');path.write_text(text.replace(old,new))
        r=execute(synthetic(width,lanes,127,.5,.5,4242,128,True),width,lanes,variant,'mutation_'+name,
                  traffic=1,rtl=path,suffix=name,expected_failure=True)
        mutations.append(dict(mutation=name,**r))
    save('mutations.json',mutations)
    print('Directed, randomized, exhaustive, odd-width and mutation checks complete',flush=True)


def public_replay():
    x,y,splits=load_workload();ids=splits['test']
    models=json.loads((R/'models.json').read_text());application=[];image_records=[];profiles=[]
    for width,lanes in [(8,4),(4,4),(8,8)]:
        qmax=(1<<(width-1))-1
        for activation,seed in itertools.product(['tanh','relu'],[7,31,97]):
            model=models[f'{activation}_{seed}'];p={k:np.asarray(v) for k,v in model['parameters'].items()}
            hidden=forward(x[ids],p,activation)[1]
            hscale=model['activation_bound']/qmax
            qx=np.rint(hidden/hscale).clip(-qmax,qmax).astype(np.int64)
            fw=p['w2'].T;wscale=np.maximum(np.abs(fw).max(axis=1),1e-30)/qmax
            qw=np.rint(fw/wscale[:,None]).clip(-qmax,qmax).astype(np.int64)
            golden=qx@qw.T;predicted=(golden*hscale*wscale[None,:]+p['b2']).argmax(axis=1)
            tx=[(qx[i,g:g+lanes].tolist(),qw[c,g:g+lanes].tolist()) for i in range(len(ids)) for c in range(10) for g in range(0,32,lanes)]
            profiles.append(dict(width=width,lanes=lanes,activation=activation,seed=seed,
                                 negative_fraction=float((qx<0).mean()),activation_zero_fraction=float((qx==0).mean()),
                                 weight_zero_fraction=float((qw==0).mean()),hidden_clipped_fraction=float((np.abs(hidden)>model['activation_bound']).mean()),
                                 hidden_quantized_sha256=hashlib.sha256(qx.astype('<i8').tobytes()).hexdigest(),
                                 weight_quantized_sha256=hashlib.sha256(qw.astype('<i8').tobytes()).hexdigest()))
            for variant in VARIANTS:
                name=f'app_w{width}_n{lanes}_{activation}_s{seed}_{variant}'
                rows=execute(tx,width,lanes,variant,name)
                actual=np.asarray([int(row['actual_sum']) for row in rows]).reshape(len(ids),10,32//lanes).sum(axis=2)
                assert np.array_equal(actual,golden)
                actual_pred=(actual*hscale*wscale[None,:]+p['b2']).argmax(axis=1)
                assert np.array_equal(actual_pred,predicted)
                elapsed=np.asarray([int(row['latency']) for row in rows]).reshape(len(ids),-1).sum(axis=1)
                application.append(dict(width=width,lanes=lanes,activation=activation,model_seed=seed,variant=variant,
                                        samples=len(ids),correct=int((actual_pred==y[ids]).sum()),floating_correct=model['floating_test_correct'],
                                        block_outputs=len(rows),mean_cycles_per_block=float(elapsed.sum()/len(rows)),
                                        mean_cycles_per_image=float(elapsed.mean()),prediction_changes=0,
                                        raw_dots_sha256=hashlib.sha256(actual.astype('<i8').tobytes()).hexdigest(),
                                        scope='RTL output-layer block dots; floating first layer/activation and reduction/rescale/bias on host'))
                for image_id,c in zip(ids,elapsed):
                    image_records.append(dict(width=width,lanes=lanes,model_seed=seed,activation=activation,variant=variant,
                                              image_id=int(image_id),service_cycles=int(c)))
                if name=='app_w8_n4_tanh_s7_sm_bitmap':(R/'application_blocks.csv').write_bytes((B/(name+'.csv')).read_bytes())
            print('Public hidden-layer replay',width,lanes,activation,seed,flush=True)
    save('application.json',application);save('activation_profiles.json',profiles)
    with (R/'image_cycles.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(image_records[0]));writer.writeheader();writer.writerows(image_records)


def synthesis():
    resources=[];scripts=[];nets={};readbacks=[]
    configs=[(w,4,v,f) for w,v,f in itertools.product([4,8],VARIANTS,['generic','xcup_nodsp'])]
    configs += [(8,8,v,f) for v,f in itertools.product(['tc_bitmap','sm_bitmap','tc_counter','sm_counter','booth_bitmap','booth_counter'],['generic','xcup_nodsp'])]
    configs += [(8,4,'parallel','xcup_dsp')]
    for width,lanes,variant,flow in configs:
        mode,magnitude,representation=VARIANTS[variant]
        name=f'w{width}_n{lanes}_{variant}_{flow}'
        net,ver=B/(name+'.json'),B/(name+'.v')
        script=f'read_verilog -sv {source(variant).relative_to(ROOT)}\nchparam -set W {width} -set N {lanes} -set MODE {mode} -set MAGNITUDE {magnitude} dot_engine\n'
        script+=('synth -top dot_engine -flatten\n' if flow=='generic' else
                 'synth_xilinx -top dot_engine -family xcup -flatten -noiopad'+(' -nodsp' if flow=='xcup_nodsp' else '')+'\n')
        script+=f'check -assert\nstat\nwrite_json build/{net.name}\nwrite_verilog -noattr build/{ver.name}\n'
        path=B/(name+'.ys');path.write_text(script);scripts.append(dict(configuration=name,commands=script))
        print('Synthesis',name,flush=True)
        p=run([YOSYS,'-s',path]);(R/(name+'.log')).write_text(p.stdout)
        design=json.loads(net.read_text());top=design['modules']['dot_engine'];types={}
        for cell in top['cells'].values():types[cell['type']]=types.get(cell['type'],0)+1
        assert not any('LATCH' in t.upper() for t in types)
        retained={'creator':design.get('creator'), 'modules':{'dot_engine':top}}
        retained_bytes=json.dumps(retained,sort_keys=True,separators=(',',':')).encode()
        nets[name]=retained
        row=dict(configuration=name,width=width,lanes=lanes,variant=variant,flow=flow,cells=len(top['cells']),types=types,
                 latches=0,netlist_sha256=sha(net),retained_design_sha256=hashlib.sha256(retained_bytes).hexdigest(),
                 lut=sum(v for k,v in types.items() if re.fullmatch(r'LUT[1-6]',k)) if flow!='generic' else None,
                 ff=sum(v for k,v in types.items() if k.startswith(('FDRE','FDSE','FDCE','FDPE'))) if flow!='generic' else None,
                 dsp=sum(v for k,v in types.items() if k.startswith('DSP')) if flow!='generic' else None)
        resources.append(row)
        read=B/(name+'_read.json');read.write_bytes(retained_bytes)
        check=f'read_json build/{read.name}\n'
        if flow!='generic':check+='read_verilog -lib -overwrite +/xilinx/cells_sim.v +/xilinx/cells_xtra.v\n'
        check+='hierarchy -top dot_engine\ncheck -assert\nstat\n'
        ys=B/(name+'_read.ys');ys.write_text(check)
        result=run([YOSYS,'-s',ys]);assert 'Found and reported 0 problems.' in result.stdout
        section=result.stdout.split('=== dot_engine ===')[-1].split('=== design hierarchy ===')[0]
        printed={k:int(v) for v,k in re.findall(r'^\s*(\d+)\s+(\S+)\s*$',section,re.M)}
        for kind,count in types.items():
            if kind!='$scopeinfo':assert printed.get(kind)==count,(name,kind,count,printed)
        readbacks.append(dict(configuration=name,passed=True,commands=check,printed_cell_types={k:printed[k] for k in types if k!='$scopeinfo'}))
        (R/(name+'_readback.log')).write_text(result.stdout)
        if flow=='generic':
            execute(synthetic(width,lanes,127,.5,.5,97,512,True),width,lanes,variant,'gate_'+name,
                    traffic=2,resets=1,seed=97,rtl=ver,suffix='gate')
        save('resources.json',resources)
    save('synthesis_scripts.json',scripts);save('netlist_readback.json',readbacks)
    (R/'netlists.json.gz.b64').write_text(base64.b64encode(gzip.compress(json.dumps(nets,sort_keys=True,separators=(',',':')).encode(),mtime=0)).decode()+'\n')


def formal():
    records=[]
    for variant in VARIANTS:
        mode,magnitude,representation=VARIANTS[variant]
        script=f'read_verilog -formal -sv {source(variant).relative_to(ROOT)} formal/numeric.sv\nchparam -set MODE {mode} -set MAGNITUDE {magnitude} proof\nprep -top proof -flatten\nasync2sync\nchformal -lower\ndffunmap\nsat -seq 12 -set-init-zero -prove-asserts -verify\n'
        path=B/('formal_'+variant+'.ys');path.write_text(script)
        print('Bounded formal',variant,flush=True)
        p=run([YOSYS,'-s',path],timeout=600)
        assert 'SUCCESS' in p.stdout,p.stdout[-3000:]
        (R/('formal_'+variant+'.log')).write_text(p.stdout)
        records.append(dict(variant=variant,passed=True,width=3,lanes=2,steps=12,commands=script,
                            scope='Bounded arbitrary inputs, tags, reset and sink readiness; zero-initialized state; no unbounded or full-parameter proof'))
    save('formal.json',records)


def main():
    mode=sys.argv[1] if len(sys.argv)>1 else 'all'
    if mode in ['all','reuse-models']:
        (R/'execution.log').write_text('');(R/'simulation.jsonl').write_text('')
        env=dict(python=sys.version,platform=platform.platform(),machine=platform.machine(),
                 processor=platform.processor(),cpu_count=os.cpu_count(),
                 tools=dict(icarus=run([IV,'-B',BASE,'-V']).stdout.splitlines()[0],yosys=run([YOSYS,'-V']).stdout.strip()),
                 dependencies={p:__import__('importlib.metadata',fromlist=['version']).version(p) for p in ['numpy','scipy','scikit-learn','matplotlib']},
                 seeds=[7,31,97,4242,2718],uvm_executed=False,vivado_executed=False,board_executed=False,timing_executed=False)
        save('environment.json',env)
        if mode=='all':
            training=run([sys.executable,'train_models.py']);(R/'training.log').write_text(training.stdout)
        save('trained_models_sha256.json',{'sha256':sha(R/'models.json'),'configuration':CONFIG,'execution':mode})
        simulations();public_replay()
    else:
        SIM.extend(json.loads(line) for line in (R/'simulation.jsonl').read_text().splitlines())
        COMMANDS.extend(json.loads((R/'commands.json').read_text()))
    save('simulation.json',SIM);save('commands.json',COMMANDS)
    if mode in ['all','reuse-models','synth']:
        synthesis();formal()
    save('simulation.json',SIM);save('commands.json',COMMANDS)
    print('Executed simulation runs',len(SIM),'checked outputs',sum(x['emitted'] for x in SIM),flush=True)


if __name__=='__main__':
    main()
