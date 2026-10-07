"""Execute vector scoreboards, actual synthesis, netlist checks, and bounded proofs."""
import base64,csv,gzip,hashlib,json,os,platform,re,shutil,subprocess,sys
from pathlib import Path
from reference import make_vectors,self_test,SCENARIOS,EVALUATION_SEEDS

ROOT=Path(__file__).resolve().parent
BUILD=ROOT/"build"
OUT=ROOT/"results"
COMMANDS=[]

def command(args, log=None, allow_failure=False):
    p=subprocess.run([str(x) for x in args],cwd=ROOT,text=True,capture_output=True,timeout=240)
    COMMANDS.append(dict(argv=[str(x) for x in args],returncode=p.returncode))
    if log: Path(log).write_text(p.stdout+p.stderr)
    if p.returncode and not allow_failure:
        raise RuntimeError(f"Command failed: {args}\n{p.stdout[-2500:]}\n{p.stderr[-1000:]}")
    return p

def compressed(path, content):
    path.write_text(base64.b64encode(gzip.compress(content.encode(),mtime=0)).decode()+"\n")

def configurations():
    return [(n,16,q,f) for n in (1,3,4,8) for q,f in ((1,1),(1,0),(4,0),(8,0))] + [
        (4,w,q,0) for w in (1,8,32) for q in (1,4)] + [(4,16,2,0)]

def name(cfg):
    n,w,q,f=cfg
    return f"n{n}_w{w}_"+("fixed" if f else f"q{q}")

def tools():
    def locate(env,rel,fallback):
        return os.environ.get(env,str(ROOT/rel) if (ROOT/rel).exists() else shutil.which(fallback) or "")
    iv=locate("IVERILOG","tools/iverilog/usr/bin/iverilog","iverilog")
    vv=locate("VVP","tools/iverilog/usr/bin/vvp","vvp")
    ys=locate("YOSYS","tools/venv/bin/yowasp-yosys","yosys")
    assert iv and vv and ys, "Toolchain missing: run python3 tools/setup.py or configure IVERILOG,VVP,YOSYS"
    base=os.environ.get("IVL_BASE",str(ROOT/"tools/iverilog/usr/lib/x86_64-linux-gnu/ivl"))
    flags=["-B",base] if Path(base).exists() else []
    os.environ.setdefault("XDG_CACHE_HOME",str(BUILD/"cache"))
    return iv,vv,ys,flags

def compile_sim(iv,flags,cfg,rtl,tag,gate=False):
    n,w,q,f=cfg
    sim=BUILD/f"{tag}.vvp"
    args=[iv,*flags,"-g2012",f"-DN={n}",f"-DWIDTH={w}",f"-DQUOTA={q}",f"-DFIXED={f}"]
    if gate: args.append("-DPOST_SYNTH")
    command([*args,"-s","tb","-o",sim,rtl,"tb/check_vectors.sv"],BUILD/f"{tag}_compile.log")
    return sim

def execute(vv,sim,cfg,scenario,seed,flow="rtl",cycles=4096,warmup=512,wave=False):
    vf=BUILD/"vectors.txt"
    expected=make_vectors(vf,*cfg,scenario,seed,cycles,warmup)
    p=command([vv,sim,f"+VECTORS={vf}",f"+WARMUP={warmup}",*(["+WAVE"] if wave else [])])
    got=re.search(r"PASS cycles=(\d+) fires=(\d+) stalls=(\d+) eval_fires=(\d+) switches=(\d+) wait_max=(\d+)",p.stdout)
    assert got,"missing simulation completion"
    assert list(map(int,got.groups()))==[cycles,expected["total_fires"],expected["total_stalls"],expected["fires"],expected["switches"],expected["serviced_wait_max"]]
    svc=list(map(int,re.search(r"SERVICE([0-9 ]+)",p.stdout).group(1).split()))
    assert svc==expected["service_counts"],"independent service counters disagree"
    expected["flow"]=flow
    expected["vector_sha256"]=hashlib.sha256(vf.read_bytes()).hexdigest()
    return expected,f"=== {name(cfg)} {scenario} seed={seed} flow={flow} cycles={cycles} warmup={warmup} ===\n"+p.stdout+p.stderr

def write_csv(path,rows):
    with path.open("w",newline="") as h:
        writer=csv.DictWriter(h,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)

def main():
    BUILD.mkdir(exist_ok=True);OUT.mkdir(exist_ok=True)
    iv,vv,ys,flags=tools()
    case_count=self_test()
    simulation_logs=[];synthesis_logs=[];scripts=[];resources=[];netlists={}
    rows=[];coverage=[];convergence=[];formal_logs=[];formal_scripts=[];representative=[]
    sims={}
    def save_result(r,log,collection):
        trace=r.pop("trace"); cov=r.pop("coverage")
        coverage.append(dict(configuration=name((r["n"],r["width"],r["quota"],r["fixed"])),scenario=r["scenario"],seed=r["seed"],flow=r["flow"],counts=cov))
        r["service_counts"]=json.dumps(r["service_counts"])
        collection.append(r);simulation_logs.append(log)
        return trace
    for cfg in configurations():
        label=name(cfg);n,w,q,f=cfg
        print("Evaluating",label,flush=True)
        sim=compile_sim(iv,flags,cfg,"rtl/stream_arbiter.sv",label)
        sims[cfg]=sim
        r,log=execute(vv,sim,cfg,"protocol",7,cycles=128,warmup=0,wave=(cfg==(4,16,4,0)))
        trace=save_result(r,log,rows)
        if cfg==(4,16,4,0):
            shutil.move(str(ROOT/"wave.vcd"),str(OUT/"protocol.vcd"));representative=trace
        for scenario in SCENARIOS:
            for seed in EVALUATION_SEEDS:
                r,log=execute(vv,sim,cfg,scenario,seed)
                save_result(r,log,rows)
        for flow in ("generic","ice40"):
            script=f"read_verilog -sv rtl/stream_arbiter.sv; chparam -set N {n} -set WIDTH {w} -set QUOTA {q} -set FIXED {f} stream_arbiter; "
            script+=("synth -top stream_arbiter" if flow=="generic" else "synth_ice40 -device hx -top stream_arbiter")
            script+=f"; check -assert; tee -o build/{flow}_{label}.json stat -json"
            if flow=="generic": script+=f"; write_verilog -noattr build/{label}_netlist.v"
            command([ys,"-l",BUILD/f"{flow}_{label}.log","-p",script])
            module=json.loads((BUILD/f"{flow}_{label}.json").read_text())["modules"]["\\stream_arbiter"]
            assert not any("latch" in k.lower() for k in module["num_cells_by_type"]),"unintended latch"
            resources.append(dict(n=n,width=w,quota=q,fixed=f,flow=flow,**module))
            scripts.append(f"# {flow} {label}\ndesign -reset;\n{script}\n")
            synthesis_logs.append(f"=== {flow} {label} ===\n"+(BUILD/f"{flow}_{label}.log").read_text())
        netlist=BUILD/f"{label}_netlist.v"
        netlists[label]=netlist.read_text()
        gate=compile_sim(iv,flags,cfg,netlist,f"gate_{label}",gate=True)
        for scenario in ("protocol","sink_stalls","phase_change"):
            r,log=execute(vv,gate,cfg,scenario,7 if scenario=="protocol" else 29,
                          flow="generic-netlist",cycles=128 if scenario=="protocol" else 4096,warmup=0 if scenario=="protocol" else 512)
            save_result(r,log,rows)
    # Longer runs and alternative warmups check stability, not independent samples.
    for cfg in ((4,16,1,0),(4,16,4,0)):
        for scenario in ("saturated","sink_stalls","light"):
            for cycles,warmup in ((2048,256),(4096,0),(4096,1024),(8192,1024)):
                r,log=execute(vv,sims[cfg],cfg,scenario,29,cycles=cycles,warmup=warmup)
                save_result(r,log,convergence)
    # Fault injection checks both data scoreboarding and stalled-selection protection.
    mutations={"data_corruption":("m_data=s_data[selected*WIDTH +: WIDTH];","m_data=s_data[selected*WIDTH +: WIDTH] ^ 1'b1;"),
               "missing_stall_lock":("if (locked) selected=lock_owner;","// Intentionally removed for fault injection.")}
    mutation_logs=[]
    for tag,(old,new) in mutations.items():
        mutant=BUILD/f"{tag}.sv"
        source=(ROOT/"rtl/stream_arbiter.sv").read_text();assert old in source
        mutant.write_text(source.replace(old,new))
        cfg=(4,16,4,0);sim=compile_sim(iv,flags,cfg,mutant,tag)
        vf=BUILD/"mutant_vectors.txt";make_vectors(vf,*cfg,"protocol",7,128,0)
        p=command([vv,sim,f"+VECTORS={vf}","+WARMUP=0"],allow_failure=True)
        assert p.returncode and "scoreboard mismatch" in p.stdout,"fault escaped scoreboard"
        mutation_logs.append(f"=== Expected failure: {tag} ===\n"+p.stdout+p.stderr)
    # Bounded safety/fairness for arbitrary legal traffic, not just workload vectors.
    for q,f in ((1,0),(4,0),(1,1)):
        script=f"read_verilog -formal -sv rtl/stream_arbiter.sv formal/properties.sv; chparam -set N 3 -set WIDTH 2 -set QUOTA {q} -set FIXED {f} formal_top; prep -top formal_top -flatten; async2sync; chformal -lower; opt_clean; sat -seq 20 -prove-asserts -verify -set-assumes -set-init-zero -set-at 1 rst 1"
        logpath=BUILD/f"formal_q{q}_f{f}.log"
        print("Proving bounded properties",q,f,flush=True)
        command([ys,"-l",logpath,"-p",script])
        assert "SUCCESS!" in logpath.read_text()
        # Establish reachability of the stalled state under the same source assumptions.
        witness="sat -seq 4 -set-assumes -set-init-zero -set-at 1 rst 1 -set-at 2 rst 0 -set-at 3 rst 0 -set-at 4 rst 0 -set-at 4 m_valid 1 -set-at 4 m_ready 0 -show-inputs"
        command([ys,"-l",BUILD/f"witness_q{q}_f{f}.log","-p",script.split("; sat -seq")[0]+"; "+witness])
        assert "model found" in (BUILD/f"witness_q{q}_f{f}.log").read_text()
        formal_logs.append(f"=== N=3 WIDTH=2 QUOTA={q} FIXED={f} bound=20 ===\n"+logpath.read_text()+"\n"+(BUILD/f"witness_q{q}_f{f}.log").read_text())
        formal_scripts.append("design -reset;\n"+script+"; "+witness+"\n")
    write_csv(OUT/"simulation.csv",rows)
    write_csv(OUT/"warmup_sensitivity.csv",convergence)
    write_csv(OUT/"protocol_trace.csv",representative)
    (OUT/"coverage.json").write_text(json.dumps(coverage,indent=2)+"\n")
    (OUT/"resources.json").write_text(json.dumps(resources,indent=2)+"\n")
    (OUT/"simulation.log").write_text("\n".join(simulation_logs))
    (OUT/"mutation.log").write_text("\n".join(mutation_logs))
    (OUT/"synthesis_commands.ys").write_text("\n".join(scripts))
    (OUT/"formal_commands.ys").write_text("\n".join(formal_scripts))
    compressed(OUT/"synthesis.log.gz.b64","\n".join(synthesis_logs))
    compressed(OUT/"formal.log.gz.b64","\n".join(formal_logs))
    compressed(OUT/"generic_netlists.json.gz.b64",json.dumps(netlists,indent=2))
    (OUT/"environment.json").write_text(json.dumps(dict(
        python=platform.python_version(),os=platform.system(),machine=platform.machine(),
        configured_tools=dict(iverilog=iv,vvp=vv,yosys=ys,ivl_base=flags),
        plotting_dependencies={line.split("==")[0]:__import__("importlib.metadata",fromlist=["version"]).version(line.split("==")[0])
                               for line in (ROOT/"analysis-requirements.txt").read_text().splitlines() if line},
        optional_tools_on_path={x:shutil.which(x) for x in ("verilator","nextpnr-ice40","vivado","vsim","vcs")},
        iverilog=command([iv,*flags,"-V"]).stdout.splitlines()[0],yosys=command([ys,"-V"]).stdout.strip(),
        evaluation_seeds=EVALUATION_SEEDS,diagnostic_seed=7,configurations=configurations(),
        traffic="Generated open-loop arrivals in reference.py; no downloaded traces or third-party RTL",
        simulation_records=len(rows),convergence_records=len(convergence),
        reference_self_tests=case_count,mutations_detected=list(mutations),
        formal=dict(n=3,width=2,bound=20,initial_state="zero; first step reset",cases=[[1,0],[4,0],[1,1]]),
        uvm_executed=False,place_route_executed=False,physical_board=False,
        synthesis_target=dict(family="iCE40 HX",device_capacity=None,clock_constraint=None,
                              mapping="Yosys synth_ice40 -device hx; bundled primitive library; no place-and-route"),
        source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                       [ROOT/p for p in ("rtl/stream_arbiter.sv","tb/check_vectors.sv","formal/properties.sv","reference.py","reproduce.py",
                                        "analyze_results.py","verify_results.py","run_project.py","analysis-requirements.txt",
                                        "tools/setup.py","tools/requirements.txt")]}),indent=2)+"\n")
    command([sys.executable,"analyze_results.py"])
    (OUT/"commands.json").write_text(json.dumps(COMMANDS,indent=2)+"\n")
    print("Completed",len(rows),"simulation records and",len(resources),"synthesis records",flush=True)

if __name__=="__main__":main()
