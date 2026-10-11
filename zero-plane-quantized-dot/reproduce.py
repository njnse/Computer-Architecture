"""Execute RTL, independent scoreboards, public replay, synthesis and analysis."""
import base64,csv,gzip,hashlib,json,os,platform,random,re,subprocess,sys
from pathlib import Path
import numpy as np
from sklearn.datasets import load_digits
from reference import dot,planes,pack
ROOT=Path(__file__).resolve().parent;BUILD=ROOT/'build';RESULTS=ROOT/'results'
BUILD.mkdir(exist_ok=True);RESULTS.mkdir(exist_ok=True)
IV=os.environ.get('IVERILOG',str(ROOT/'tools/iverilog/usr/bin/iverilog'))
BASE=os.environ.get('IVL_BASE',str(ROOT/'tools/iverilog/usr/lib/x86_64-linux-gnu/ivl'))
VVP=os.environ.get('VVP',str(ROOT/'tools/iverilog/usr/bin/vvp'))
YOSYS=os.environ.get('YOSYS',str(ROOT/'tools/venv/bin/yowasp-yosys'))
os.environ.setdefault('XDG_CACHE_HOME',str(BUILD/'cache'));os.environ.setdefault('MPLCONFIGDIR',str(BUILD/'mpl'))
COMMANDS=[];SIM=[];LOG=[];COMPILED={}

def run(args,timeout=600):
    result=subprocess.run([str(x) for x in args],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
    COMMANDS.append({'argv':[str(x).replace(str(ROOT),'.') for x in args],'returncode':result.returncode})
    with (RESULTS/'execution_trace.log').open('a') as f:f.write('COMMAND '+json.dumps([str(x) for x in args])+'\n'+result.stdout+'\n')
    if result.returncode:raise RuntimeError(result.stdout[-5000:])
    return result.stdout

def binary(width,lanes,mode,rtl=None,suffix=''):
    key=(width,lanes,mode,suffix)
    if key not in COMPILED:
        name=BUILD/f'sim_{width}_{lanes}_{mode}{suffix}.vvp'
        LOG.append(run([IV]+(['-DNETLIST'] if rtl and Path(rtl).suffix=='.v' else [])+['-B',BASE,'-g2012','-s','check',f'-Pcheck.W={width}',f'-Pcheck.N={lanes}',f'-Pcheck.MODE={mode}','-o',name,rtl or ROOT/'rtl/dot_engine.sv',ROOT/'tb/check.sv']))
        COMPILED[key]=name
    return COMPILED[key]

def execute(transactions,width,lanes,mode,name,traffic=0,resets=0,seed=7,rtl=None,suffix='',wave=False):
    stimulus=BUILD/(name+'.txt');out=BUILD/(name+'.csv')
    stimulus.write_text(''.join(f'{pack(x,width):x} {pack(w,width):x} {dot(x,w)}\n' for x,w in transactions))
    args=[VVP,binary(width,lanes,mode,rtl,suffix),f'+input={stimulus}',f'+output={out}',f'+seed={seed}',f'+traffic={traffic}',f'+resets={resets}']
    if wave:args.append(f'+wave={RESULTS}/protocol.vcd')
    log=run(args);LOG.append(name+'\n'+log)
    values={k:int(v) for k,v in re.findall(r'(\w+)=(-?\d+)',log)}
    if 'emitted' not in values:raise RuntimeError(log)
    assert values['emitted']+values['canceled']==len(transactions)
    records=list(csv.DictReader(out.open()))
    for row in records:
        ordinal=int(row['ordinal']);assert int(row['actual_sum'])==dot(*transactions[ordinal])
        if traffic==0 and not resets:
            assert int(row['latency'])==planes(transactions[ordinal][0],width,mode)+1
    if traffic==0 and not resets:
        predicted=sum(planes(x,width,mode)+1 for x,w in transactions[:-1])
        assert values['lastaccept']-values['firstaccept']==predicted
    values.update({'run':name,'width':width,'lanes':lanes,'mode':mode,'traffic':traffic,'seed':seed,'resets':resets,'stimulus_sha256':hashlib.sha256(stimulus.read_bytes()).hexdigest(),'output_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'mean_planes':sum(planes(x,width,mode) for x,w in transactions)/len(transactions),'mean_latency':values['total_latency']/values['emitted'],'accept_interval':(values['lastaccept']-values['firstaccept'])/(len(transactions)-1)})
    SIM.append(values)
    with (RESULTS/'simulation_incremental.jsonl').open('a') as f:f.write(json.dumps(values)+'\n')
    return records

def synthetic(width,lanes,workload,seed,count=512):
    rng=random.Random(seed);lo=-(1<<(width-1));hi=(1<<(width-1))-1
    result=[]
    directed=[[0]*lanes,[lo]*lanes,[hi]*lanes,[-1]*lanes]+[[1<<b if b<width-1 else lo]*lanes for b in range(width)]
    for i in range(count):
        if workload=='signed':x=[rng.randint(lo,hi) for _ in range(lanes)]
        elif workload=='unsigned':x=[rng.randint(0,hi) for _ in range(lanes)]
        elif workload=='low_range':x=[rng.randint(0,min(5,hi)) for _ in range(lanes)]
        elif workload=='zero_rich':x=[rng.randint(0,hi) if rng.random()<.2 else 0 for _ in range(lanes)]
        elif workload=='negative':x=[-1]*lanes
        elif workload=='phases':x=[rng.randint(0,min(3,hi)) if (i//64)%2==0 else rng.randint(lo,hi) for _ in range(lanes)]
        elif workload=='stress':x=directed[i] if i<len(directed) else [rng.randint(lo,hi) for _ in range(lanes)]
        else:raise ValueError(workload)
        w=[rng.randint(lo,hi) for _ in range(lanes)]
        if workload=='stress' and i<2:w=[lo]*lanes
        result.append((x,w))
    return result

def public_replay():
    provenance=json.loads((ROOT/'fixtures/provenance.json').read_text());models=json.loads((ROOT/'fixtures/checkpoints.json').read_text())
    digits=load_digits();pixels=digits.data.astype(np.uint8);labels=digits.target.astype(np.int64)
    assert hashlib.sha256(pixels.tobytes()).hexdigest()==provenance['dataset']['pixels_u8_sha256']
    assert hashlib.sha256(labels.astype('<i8').tobytes()).hexdigest()==provenance['dataset']['labels_i64le_sha256']
    application=[];density=[]
    for width in [4,8]:
        qmax=(1<<(width-1))-1
        for split in ['validation','test']:
            ids=provenance['dataset'][split]
            # Convert before multiplication to avoid uint8 overflow in dataset quantization.
            qx=np.rint(pixels[ids].astype(np.float64)*qmax/16.0).astype(np.int64)
            for lanes in [1,4,8]:
                for mode in [1,2,3,4]:
                    counts=[planes(row[g:g+lanes],width,mode) for row in qx for g in range(0,64,lanes)]
                    density.append({'width':width,'lanes':lanes,'mode':mode,'split':split,'groups':len(counts),'mean_planes':float(np.mean(counts)),'modeled_cycles_per_image_class':sum(v+1 for v in counts)/len(ids),'scope':'analytical from public quantized inputs; only N=4 test replayed in RTL'})
            for policy in ['dense','index']:
                model=models[f'7_{policy}_recovered'];fw=np.asarray(model['weights']);scales=np.maximum(np.abs(fw).max(axis=1),1e-30)/qmax
                qw=np.rint(fw/scales[:,None]).clip(-qmax,qmax).astype(np.int64);golden=qx@qw.T
                software_scores=golden*scales[None,:]/qmax+np.asarray(model['bias']);pred=software_scores.argmax(axis=1)
                if split=='test':
                    transactions=[(qx[i,g:g+4].tolist(),qw[c,g:g+4].tolist()) for i in range(len(ids)) for c in range(10) for g in range(0,64,4)]
                    for mode in [0,1,2,3,4]:
                        name=f'app_{width}_{policy}_{mode}';rows=execute(transactions,width,4,mode,name)
                        actual=np.asarray([int(row['actual_sum']) for row in rows]).reshape(len(ids),10,16).sum(axis=2)
                        assert np.array_equal(actual,golden)
                        actual_pred=(actual*scales[None,:]/qmax+np.asarray(model['bias'])).argmax(axis=1)
                        assert np.array_equal(actual_pred,pred)
                        application.append({'width':width,'policy':policy,'mode':mode,'samples':len(ids),'correct':int((actual_pred==labels[ids]).sum()),'block_outputs':len(rows),'prediction_changes':0,'raw_dots_sha256':hashlib.sha256(actual.astype('<i8').tobytes()).hexdigest(),'scope':'RTL block dots; class reduction and floating rescale/bias in Python'})
                        if name=='app_8_dense_3':(RESULTS/'application_blocks.csv').write_bytes((BUILD/(name+'.csv')).read_bytes())
    (RESULTS/'application.json').write_text(json.dumps(application,indent=2)+'\n');(RESULTS/'density.json').write_text(json.dumps(density,indent=2)+'\n')

def simulations():
    LOG.append(run([sys.executable,'-m','unittest','discover','-s','tests','-v']))
    for width in [4,8]:
        for lanes in [1,4,8]:
            for workload in ['signed','unsigned','low_range','zero_rich','negative','phases']:
                for seed in [7,31,97]:
                    transactions=synthetic(width,lanes,workload,seed)
                    for mode in [0,1,2,3,4]:execute(transactions,width,lanes,mode,f'{workload}_{width}_{lanes}_{seed}_{mode}')
            for mode in [0,1,2,3,4]:
                for traffic in [1,2]:execute(synthetic(width,lanes,'stress',4242),width,lanes,mode,f'stress_{width}_{lanes}_{mode}_{traffic}',traffic,1,4242,wave=(width==8 and lanes==4 and mode==3 and traffic==2))
    # Longer independent streams check controller startup/drain effects.
    for mode in [0,1,2,3,4]:execute(synthetic(8,4,'zero_rich',2718,4096),8,4,mode,f'convergence_{mode}')
    # Exhaust all signed W=4 single-lane operand pairs on every mechanism.
    exhaustive=[([x],[w]) for x in range(-8,8) for w in range(-8,8)]
    for mode in [0,1,2,3,4]:execute(exhaustive,4,1,mode,f'exhaustive_{mode}')
    public_replay()
    mutations=[]
    source=(ROOT/'rtl/dot_engine.sv').read_text()
    for name,old,new in [('wrong_sign','total=acc-shifted','total=acc+shifted'),('stalled_overwrite','(!out_valid||out_ready)','1\'b1')]:
        path=BUILD/(name+'.sv');path.write_text(source.replace(old,new));before=len(COMMANDS)
        try:execute(synthetic(8,4,'stress',4242,64),8,4,3,'mutation_'+name,1,0,4242,path,name)
        except RuntimeError as e:mutations.append({'mutation':name,'detected':True,'diagnostic':str(e)[-1500:]})
        else:raise RuntimeError('Mutation escaped detection')
    (RESULTS/'mutations.json').write_text(json.dumps(mutations,indent=2)+'\n')
    (RESULTS/'simulation.json').write_text(json.dumps(SIM,indent=2)+'\n');(RESULTS/'simulation.log').write_text('\n'.join(LOG))
    (RESULTS/'commands.json').write_text(json.dumps(COMMANDS,indent=2)+'\n')
    print('Simulation complete',len(SIM),sum(r['emitted'] for r in SIM),flush=True)

def synthesis():
    scripts=[];resources=[];netlists={};logs=[]
    for width in [4,8]:
        for mode in [0,1,2,3,4]:
            for flow in ['generic','xcup_nodsp']:
                name=f'w{width}_n4_m{mode}_{flow}';net=BUILD/(name+'.json');ver=BUILD/(name+'.v')
                script=f'read_verilog -sv rtl/dot_engine.sv\nchparam -set W {width} -set N 4 -set MODE {mode} dot_engine\n'
                script+=('synth -top dot_engine -flatten\n' if flow=='generic' else 'synth_xilinx -top dot_engine -family xcup -flatten -nodsp -noiopad\n')
                script+=f'check -assert\nstat\nwrite_json {net}\nwrite_verilog -noattr {ver}\n'
                path=BUILD/(name+'.ys');path.write_text(script);scripts.append({'configuration':name,'commands':script.replace(str(ROOT),'.')})
                print('Synthesis',name,flush=True);log=run([YOSYS,'-s',path],timeout=600);logs.append(name+'\n'+log)
                d=json.loads(net.read_text());cells=d['modules']['dot_engine']['cells'];types={}
                for cell in cells.values():types[cell['type']]=types.get(cell['type'],0)+1
                assert not any('LATCH' in t.upper() for t in types)
                resources.append({'width':width,'lanes':4,'mode':mode,'flow':flow,'cells':len(cells),'types':types,'latches':0,'netlist_sha256':hashlib.sha256(net.read_bytes()).hexdigest(),'lut':sum(v for k,v in types.items() if re.fullmatch(r'LUT[1-6]',k)) if flow!='generic' else None,'ff':sum(v for k,v in types.items() if k.startswith(('FDRE','FDSE','FDCE','FDPE'))) if flow!='generic' else None,'dsp':sum(v for k,v in types.items() if k.startswith('DSP')) if flow!='generic' else None})
                netlists[name]=d
                # Independent mapped generic-netlist simulation checks reset/backpressure/numerics.
                if flow=='generic':execute(synthetic(width,4,'stress',97),width,4,mode,f'gate_{width}_{mode}',2,1,97,ver,'gate')
    (RESULTS/'synthesis_scripts.json').write_text(json.dumps(scripts,indent=2)+'\n');(RESULTS/'resources.json').write_text(json.dumps(resources,indent=2)+'\n')
    (RESULTS/'netlists.json.gz.b64').write_text(base64.b64encode(gzip.compress(json.dumps(netlists,separators=(',',':')).encode(),mtime=0)).decode()+'\n')
    (RESULTS/'synthesis.log.gz.b64').write_text(base64.b64encode(gzip.compress('\n'.join(logs).encode(),mtime=0)).decode()+'\n')
    (RESULTS/'simulation.json').write_text(json.dumps(SIM,indent=2)+'\n');(RESULTS/'simulation.log').write_text('\n'.join(LOG));(RESULTS/'commands.json').write_text(json.dumps(COMMANDS,indent=2)+'\n')
    print('Synthesis complete',len(resources),flush=True)

def main():
    mode=sys.argv[1] if len(sys.argv)>1 else 'all'
    env={'python':sys.version,'platform':platform.platform(),'tools':{'icarus':run([IV,'-B',BASE,'-V']).splitlines()[0],'yosys':run([YOSYS,'-V']).strip()},'seeds':[7,31,97,4242,2718],'dependency_versions':{k:__import__('importlib.metadata',fromlist=['version']).version(k) for k in ['numpy','scipy','scikit-learn','matplotlib']},'uvm_executed':False,'vivado_executed':False,'timing_executed':False,'board_executed':False}
    (RESULTS/'environment.json').write_text(json.dumps(env,indent=2)+'\n')
    if mode in ['all','sim']:
        (RESULTS/'execution_trace.log').write_text('')
        (RESULTS/'simulation_incremental.jsonl').write_text('')
        simulations()
    if mode=='synth':
        SIM.extend(json.loads((RESULTS/'simulation.json').read_text()));COMMANDS.extend(json.loads((RESULTS/'commands.json').read_text()));LOG.append((RESULTS/'simulation.log').read_text())
    if mode in ['all','synth']:synthesis()
    sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob('*') if p.is_file() and not any(v in p.relative_to(ROOT).parts for v in ['build','results','__pycache__','venv','iverilog'])}
    (RESULTS/'source_hashes.json').write_text(json.dumps(sources,indent=2)+'\n')
if __name__=='__main__':main()
