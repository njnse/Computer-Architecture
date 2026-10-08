"""Execute training, RTL, synthesis, formal checks, and analysis; no invented metrics."""
import base64,collections,csv,gzip,hashlib,json,os,platform,re,shutil,subprocess,sys
from pathlib import Path
import numpy as np
from reference import NAMES,exhaustive_transactions,random_transactions,write_vectors
from workload import train_workload,replay_transactions

ROOT=Path(__file__).resolve().parent
os.chdir(ROOT)
BUILD=ROOT/'build';RESULTS=ROOT/'results'
BUILD.mkdir(exist_ok=True);RESULTS.mkdir(exist_ok=True)
IV=os.environ.get('IVERILOG',str(ROOT/'tools/iverilog/usr/bin/iverilog'))
VVP=os.environ.get('VVP',str(ROOT/'tools/iverilog/usr/bin/vvp'))
YOSYS=os.environ.get('YOSYS',str(ROOT/'tools/venv/bin/yowasp-yosys'))
BASE=os.environ.get('IVL_BASE',str(ROOT/'tools/iverilog/usr/lib/x86_64-linux-gnu/ivl'))
os.environ.setdefault('XDG_CACHE_HOME',str(BUILD/'cache'))
commands=[];simulations=[];all_logs=[]

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def archive(path,data):
    if isinstance(data,str):data=data.encode()
    path.write_text(base64.b64encode(gzip.compress(data,mtime=0)).decode()+'\n')
def run(args,allow_failure=False):
    p=subprocess.run([str(a) for a in args],capture_output=True,text=True,cwd=ROOT)
    out=p.stdout+p.stderr
    commands.append({'argv':[str(a).replace(str(ROOT),'PROJECT') for a in args],'returncode':p.returncode})
    if p.returncode and not allow_failure:raise RuntimeError(f'Command failed {args}:\n{out[-5000:]}')
    return p.returncode,out
def csv_write(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def compile_rtl(width,mode,netlist=None,source=None):
    exe=BUILD/f'dot_{width}_{mode}_{"gate" if netlist else "rtl"}.vvp'
    args=[IV]
    if BASE and Path(BASE).exists():args+=['-B',BASE]
    args+=['-g2012','-s','tb',f'-DWIDTH={width}',f'-DMODE={mode}']
    if netlist:args+=['-DNETLIST']
    if netlist and 'xcup_lut_' in str(netlist):
        candidates=list((Path(YOSYS).resolve().parent.parent/'lib').glob('python*/site-packages/yowasp_yosys/share/xilinx/cells_sim.v'))
        candidates+=[Path('/usr/share/yosys/xilinx/cells_sim.v'),Path('/usr/local/share/yosys/xilinx/cells_sim.v')]
        if os.environ.get('YOSYS_XILINX_SIM'):candidates.insert(0,Path(os.environ['YOSYS_XILINX_SIM']))
        library=next((p for p in candidates if p.exists()),None)
        if library is None:raise RuntimeError('Cannot locate Yosys Xilinx functional primitive library; set YOSYS_XILINX_SIM.')
        args+=[library]
    args+=['-o',exe,netlist or source or ROOT/'rtl/sparse_dot.sv',ROOT/'tb/check_vectors.sv']
    _,log=run(args)
    if log:all_logs.append(log)
    return exe

def simulate(width,mode,label,transactions,traffic='continuous',seed=7,resets=False,netlist=None,outputs=False,wave=False,source=None,expect_failure=False):
    path=BUILD/'vectors.txt'
    rows=write_vectors(path,width,mode,transactions,traffic,seed,resets)
    exe=compile_rtl(width,mode,netlist,source)
    output_path=BUILD/'outputs.txt'
    args=[VVP,exe,f'+vectors={path}']
    if outputs:args+=[f'+outputs={output_path}']
    if wave:args+=[f'+wave={RESULTS/"protocol.vcd"}']
    rc,log=run(args,allow_failure=expect_failure)
    all_logs.append(f'CASE {label} WIDTH {width} MODE {mode}\n{log}')
    if expect_failure:
        if rc==0 or 'mismatch' not in log.lower() and 'changed while stalled' not in log.lower():raise RuntimeError('Mutation did not trigger intended detection')
        return {'mutation':label,'detected':True,'returncode':rc,'diagnostic':log.split('FATAL:')[-1].strip()[:350]}
    match=re.search(r'PASS (.*)',log)
    if not match:raise RuntimeError('Simulator did not report PASS')
    measured={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',match[1])}
    assert measured['cycles']==rows
    assert measured['accepted']==measured['emitted']+measured['canceled']
    hist={int(k):int(v) for k,v in re.findall(r'LATENCY (\d+) (\d+)',log)}
    assert sum(hist.values())==measured['emitted']
    ordered=sorted(hist);total=measured['emitted']
    def percentile(p):
        count=0
        for key in ordered:
            count+=hist[key]
            if count>=p*total:return key
        return 0
    entry={'label':label,'width':width,'mode':NAMES[mode],'netlist':bool(netlist),'seed':seed,'traffic':traffic,**measured,'latency_p50':percentile(.5),'latency_p99':percentile(.99),'latency_max':max(hist,default=0),'vector_sha256':digest(path),'metadata_coverage':json.dumps({int(k):int(v) for k,v in re.findall(r'META (\d+) (\d+)',log)},sort_keys=True),'latency_histogram':json.dumps(hist,sort_keys=True)}
    simulations.append(entry)
    return entry,(np.loadtxt(output_path,dtype=np.int64).reshape(-1,2) if outputs else None)

def synthesize():
    lines=[]
    def flows(mode):return ['generic','xcup_lut','xcup_dsp']+(['xcup_lut_unchecked'] if mode in [1,2] else [])
    for width in [2,4,6,8,12]:
        for mode in range(5):
            for flow in flows(mode):
                prefix=f'{flow}_{width}_{mode}'
                lines+=['design -reset','read_verilog -sv rtl/sparse_dot.sv',f'chparam -set WIDTH {width} -set MODE {mode} sparse_dot','hierarchy -check -top sparse_dot']
                if flow=='xcup_lut_unchecked':lines+=["chparam -set CHECK_META 0 sparse_dot"]
                if flow=='generic':lines+=['synth -top sparse_dot']
                else:lines+=[f'synth_xilinx -family xcup -noiopad -noclkbuf {"-nodsp" if flow.startswith("xcup_lut") else ""} -top sparse_dot']
                lines+=['check -assert',f'write_json build/{prefix}.json']
                if flow in ['generic','xcup_lut']:lines+=[f'write_verilog -noattr build/{prefix}.v']
    script=RESULTS/'synthesis_commands.ys';script.write_text('\n'.join(lines)+'\n')
    _,log=run([YOSYS,'-Q','-T','-s',script])
    archive(RESULTS/'synthesis.log.gz.b64',log)
    resources=[];netlists={}
    for width in [2,4,6,8,12]:
        for mode in range(5):
            for flow in flows(mode):
                prefix=f'{flow}_{width}_{mode}'
                data=json.loads((BUILD/(prefix+'.json')).read_text())
                cells=data['modules']['sparse_dot']['cells']
                types=dict(sorted(collections.Counter(c['type'] for c in cells.values()).items()))
                if any('LATCH' in k.upper() or 'DLATCH' in k.upper() for k in types):raise RuntimeError('Unexpected latch')
                resources.append({'width':width,'mode':NAMES[mode],'flow':flow,'cell_count':sum(types.values()),'cell_types':types,'lut':sum(v for k,v in types.items() if re.fullmatch('LUT[1-6]',k)),'ff':sum(v for k,v in types.items() if k.startswith('FD') or 'DFF' in k),'dsp':sum(v for k,v in types.items() if k.startswith('DSP')),'carry':sum(v for k,v in types.items() if k.startswith('CARRY')),'bram':sum(v for k,v in types.items() if k.startswith('RAMB')),'netlist_json_sha256':digest(BUILD/(prefix+'.json'))})
                if flow=='generic':netlists[f'{width}_{mode}']=(BUILD/(prefix+'.v')).read_text()
    (RESULTS/'resources.json').write_text(json.dumps(resources,indent=2)+'\n')
    archive(RESULTS/'generic_netlists.json.gz.b64',json.dumps(netlists,sort_keys=True))
    return resources

def formal():
    lines=[]
    for mode in range(5):
        lines+=['design -reset','read_verilog -formal -sv rtl/sparse_dot.sv formal/properties.sv',f'chparam -set WIDTH 2 -set MODE {mode} formal_top','prep -top formal_top -flatten','async2sync','dffunmap','sat -seq 10 -prove-asserts -set-assumes -verify']
    script=RESULTS/'formal_commands.ys';script.write_text('\n'.join(lines)+'\n')
    _,log=run([YOSYS,'-Q','-T','-s',script]);archive(RESULTS/'formal.log.gz.b64',log)
    proved=log.count('SAT proof finished - no model found: SUCCESS!')
    if proved!=5:raise RuntimeError(f'Expected five bounded proofs, got {proved}')
    return {'proved_configurations':proved,'width':2,'steps':10,'unbounded_proof':False}

def main():
    print('Training fixed protocol on public digits',flush=True)
    _,unitlog=run([sys.executable,'-m','unittest','discover','-s','tests','-v'])
    (RESULTS/'unit_tests.log').write_text(unitlog)
    x,y,models,metrics,history,predictions=train_workload(RESULTS)
    csv_write(RESULTS/'classification.csv',metrics);csv_write(RESULTS/'training.csv',history)
    print('Running exhaustive arithmetic and randomized protocol checks',flush=True)
    for mode in range(5):simulate(2,mode,'exhaustive',exhaustive_transactions(mode))
    for width in [2,4,6,8,12]:
        for mode in range(5):
            for seed in [7,31,97]:
                simulate(width,mode,'random',random_transactions(width,seed,1600),'mixed',seed,True,wave=width==4 and mode==3 and seed==7)
            simulate(width,mode,'saturation',random_transactions(width,123,2000),'continuous',123)
    print('Synthesizing matched generic and UltraScale+ configurations',flush=True)
    resources=synthesize()
    print('Cross-checking generic netlists and bounded formal properties',flush=True)
    for width in [2,4,6,8,12]:
        for mode in range(5):simulate(width,mode,'netlist_random',random_transactions(width,211,800),'mixed',211,True,netlist=BUILD/f'generic_{width}_{mode}.v')
    for width in [4,8]:
        for mode in range(5):simulate(width,mode,'mapped_random',random_transactions(width,317,800),'mixed',317,True,netlist=BUILD/f'xcup_lut_{width}_{mode}.v')
    bounded=formal()
    print('Replaying every held-out group through RTL',flush=True)
    replays=[]
    for width in [4,8]:
        for mode in range(5):
            policy='index' if mode==2 else NAMES[mode]
            model=models[f'7_{policy}_recovered']
            stream,sums,scale,bias,expected_pred=replay_transactions(x,model,width,mode)
            entry,out=simulate(width,mode,'digits_replay',stream,outputs=True)
            assert not out[:,1].any()
            observed=out[:,0].reshape(len(y),10,16).sum(axis=2)
            if not np.array_equal(observed,sums):raise RuntimeError('Independent matrix-vs-RTL replay mismatch')
            pred=(observed*scale[None,:]/((1<<(width-1))-1)+bias).argmax(axis=1)
            assert np.array_equal(pred,expected_pred)
            assert pred.tolist()==predictions[f'7_{policy}_recovered_{width}']
            h=hashlib.sha256(out.astype('<i8').tobytes()).hexdigest()
            replays.append({'width':width,'mode':NAMES[mode],'images':len(y),'group_outputs':len(out),'test_correct':int((pred==y).sum()),'rtl_equals_independent_integer_matmul':True,'prediction_matches_classification_csv':True,'output_i64le_sha256':h,'vector_sha256':entry['vector_sha256']})
    (RESULTS/'replay.json').write_text(json.dumps(replays,indent=2)+'\n')
    print('Injecting two deliberate RTL faults',flush=True)
    original=(ROOT/'rtl/sparse_dot.sv').read_text()
    mutations=[]
    for name,old,new in [('wrong_pair','assign i1={1\'b1,s_meta[1]};','assign i1={1\'b0,s_meta[1]};'),('unstable_output','end else if (s_ready) begin','end else if (1\'b1) begin')]:
        assert old in original
        mutant=BUILD/f'{name}.sv';mutant.write_text(original.replace(old,new))
        mutations.append(simulate(4,3,name,random_transactions(4,997,1000),'mixed',997,True,source=mutant,expect_failure=True))
    csv_write(RESULTS/'simulation.csv',simulations)
    (RESULTS/'simulation.log').write_text('\n'.join(all_logs))
    validation={'unit_tests':7,'rtl_and_netlist_runs':len(simulations),'cycles':sum(s['cycles'] for s in simulations),'accepted':sum(s['accepted'] for s in simulations),'emitted':sum(s['emitted'] for s in simulations),'reset_canceled':sum(s['canceled'] for s in simulations),'synthesis_configurations':len(resources),'latches':0,'formal':bounded,'mutations':mutations,'public_workload_replays':len(replays),'uvm_executed':False,'vivado_executed':False,'placed_timing_executed':False,'board_executed':False}
    (RESULTS/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    _,iverilog_version=run([IV,*(['-B',BASE] if Path(BASE).exists() else []),'-V'])
    _,yosys_version=run([YOSYS,'-V'])
    import importlib.metadata
    packages={name:importlib.metadata.version(name) for name in ['numpy','scipy','scikit-learn','matplotlib','joblib','threadpoolctl']}
    source_hashes={str(p.relative_to(ROOT)):digest(p) for suffix in ['*.py','*.sv','*.txt'] for p in ROOT.rglob(suffix) if 'build' not in p.parts and 'results' not in p.parts and 'venv' not in p.parts and 'iverilog' not in p.parts}
    env={'python':platform.python_version(),'platform':platform.platform(),'machine':platform.machine(),'iverilog':iverilog_version.splitlines()[0],'yosys':yosys_version.strip(),'packages':packages,'source_sha256':source_hashes,'runtime':'Python 3.12 on Linux x86-64','simulation_timescale':'Cycle checks use arbitrary testbench delays, not physical clock timing.','family_mapping':'Yosys synth_xilinx -family xcup; no exact-device implementation, placement, or timing.','threads':'NumPy training uses threadpoolctl limits=1; no GPU training.','commands':'python3 run_project.py with optional explicit tool paths','available_remote_resources':'User-reported KV260 and HiPerGator are not attached to this execution environment.'}
    (RESULTS/'environment.json').write_text(json.dumps(env,indent=2)+'\n')
    from analyze import analyze
    analyze(RESULTS)
    (RESULTS/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    print(json.dumps(validation,indent=2),flush=True)

if __name__=='__main__':main()
