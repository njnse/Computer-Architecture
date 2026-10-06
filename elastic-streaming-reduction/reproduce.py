"""Execute RTL/gate verification and synthesize a matched pipeline comparison."""
import csv,hashlib,json,os,random,re,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT/"results"
BUILD=ROOT/"build"
FIELDS="width pipe seed scenario accepted retired dropped cycles latency_min latency_max latency_sum source_stalls sink_stalls simultaneous reset_pending first_output last_output max_output_gap".split()


def run(cmd,log=None):
    p=subprocess.run(list(map(str,cmd)),cwd=ROOT,text=True,capture_output=True,timeout=180)
    if log:Path(log).write_text(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError(f"Command failed: {cmd}\n{p.stdout[-1000:]}\n{p.stderr[-1000:]}")
    return p.stdout


def main():
    OUT.mkdir(exist_ok=True);BUILD.mkdir(exist_ok=True)
    local_iv=ROOT/"tools/iverilog/usr/bin/iverilog"
    local_vvp=ROOT/"tools/iverilog/usr/bin/vvp"
    local_yosys=ROOT/"tools/venv/bin/yowasp-yosys"
    iv=os.environ.get("IVERILOG",str(local_iv) if local_iv.exists() else shutil.which("iverilog") or "")
    vvp=os.environ.get("VVP",str(local_vvp) if local_vvp.exists() else shutil.which("vvp") or "")
    yosys=os.environ.get("YOSYS",str(local_yosys) if local_yosys.exists() else shutil.which("yowasp-yosys") or shutil.which("yosys") or "")
    assert iv and vvp and yosys,"set IVERILOG, VVP and YOSYS or install tools"
    ivflags=["-B",os.environ["IVL_BASE"]] if os.environ.get("IVL_BASE") else []
    if not ivflags and Path(iv)==local_iv:ivflags=["-B",str(ROOT/"tools/iverilog/usr/lib/x86_64-linux-gnu/ivl")]
    os.environ.setdefault("XDG_CACHE_HOME",str(BUILD/"cache"))
    rows=[]
    for width in [1,8,16,32]:
        rng=random.Random(412+width);maximum=(1<<width)-1
        vectors=[(0,0,0,0),(maximum,)*4,(maximum,0,maximum,0),(1,1,1,1)]
        vectors += [tuple(rng.randrange(maximum+1) for _ in range(4)) for _ in range(508)]
        vf=BUILD/f"vectors{width}.hex";af=BUILD/f"answers{width}.hex"
        vf.write_text("\n".join(f"{(a<<(3*width))|(b<<(2*width))|(c<<width)|d:0{width}x}" for a,b,c,d in vectors)+"\n")
        af.write_text("\n".join(f"{sum(v):x}" for v in vectors)+"\n")
        for pipe in [1,2]:
            sim=BUILD/f"rtl_{width}_{pipe}.vvp"
            run([iv,*ivflags,"-g2012",f"-DWIDTH={width}",f"-DPIPE={pipe}","-s","tb","-o",sim,"rtl/stream_sum.sv","tb/tb.sv"])
            for seed in [7,31,101]:
                for scenario in [0,1,2]:
                    text=run([vvp,sim,f"+VECTORS={vf}",f"+ANSWERS={af}",f"+SEED={seed}",f"+SCENARIO={scenario}"],
                        OUT/f"rtl_{width}_{pipe}_{seed}_{scenario}.log")
                    vals=list(map(int,re.search(r"RESULT ([0-9 ]+)",text).group(1).split()))
                    rows.append(dict(flow="rtl",**dict(zip(FIELDS,vals))))
            script=f"read_verilog -sv rtl/stream_sum.sv; chparam -set WIDTH {width} -set PIPE {pipe} stream_sum; synth -top stream_sum; check -assert; tee -o results/generic_{width}_{pipe}.json stat -json; ltp -noff; write_verilog -noattr build/generic_{width}_{pipe}.v"
            (OUT/f"generic_{width}_{pipe}.ys").write_text(script+"\n")
            run([yosys,"-l",OUT/f"generic_{width}_{pipe}.log","-p",script])
            gate=BUILD/f"gate_{width}_{pipe}.vvp"
            run([iv,*ivflags,"-g2012",f"-DWIDTH={width}",f"-DPIPE={pipe}","-DPOST_SYNTH","-s","tb","-o",gate,BUILD/f"generic_{width}_{pipe}.v","tb/tb.sv"])
            for scenario in [0,1,2]:
                text=run([vvp,gate,f"+VECTORS={vf}",f"+ANSWERS={af}","+SEED=31",f"+SCENARIO={scenario}"],OUT/f"gate_{width}_{pipe}_{scenario}.log")
                vals=list(map(int,re.search(r"RESULT ([0-9 ]+)",text).group(1).split()))
                rows.append(dict(flow="generic-netlist",**dict(zip(FIELDS,vals))))
            ice=f"read_verilog -sv rtl/stream_sum.sv; chparam -set WIDTH {width} -set PIPE {pipe} stream_sum; synth_ice40 -top stream_sum; check -assert; tee -o results/ice40_{width}_{pipe}.json stat -json"
            (OUT/f"ice40_{width}_{pipe}.ys").write_text(ice+"\n")
            run([yosys,"-l",OUT/f"ice40_{width}_{pipe}.log","-p",ice])
    with (OUT/"simulation.csv").open("w",newline="") as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    # Verify an intentionally corrupted output is detected by the independent scoreboard.
    mutant=BUILD/"mutant.sv"
    mutant.write_text((ROOT/"rtl/stream_sum.sv").read_text().replace("assign m_data = value;","assign m_data = value ^ 1;"))
    sim=BUILD/"mutation.vvp"
    run([iv,*ivflags,"-g2012","-DWIDTH=8","-DPIPE=1","-s","tb","-o",sim,mutant,"tb/tb.sv"])
    bad=subprocess.run([vvp,str(sim),f"+VECTORS={BUILD/'vectors8.hex'}",f"+ANSWERS={BUILD/'answers8.hex'}","+SEED=7","+SCENARIO=0"],
                       capture_output=True,text=True,cwd=ROOT)
    assert bad.returncode and "scoreboard mismatch" in bad.stdout,"scoreboard failed to detect mutation"
    (OUT/"mutation.log").write_text(bad.stdout+bad.stderr)
    # Retain one representative waveform, not every randomized trace.
    run([vvp,BUILD/"rtl_8_2.vvp",f"+VECTORS={BUILD/'vectors8.hex'}",f"+ANSWERS={BUILD/'answers8.hex'}",
         "+SEED=31","+SCENARIO=2","+WAVE"],OUT/"waveform.log")
    shutil.move(str(ROOT/"wave.vcd"),str(OUT/"wave.vcd"))
    resources=[]
    synthesis_bundle=[]
    scripts=[]
    for width in [1,8,16,32]:
        for pipe in [1,2]:
            item=dict(width=width,pipe=pipe)
            for flow in ["generic","ice40"]:
                stats=json.loads((OUT/f"{flow}_{width}_{pipe}.json").read_text())
                module=stats["modules"]["\\stream_sum"]
                item[flow]=module
                assert not any("latch" in x.lower() or "dlatch" in x.lower() for x in module["num_cells_by_type"])
                synthesis_bundle.append(f"=== {flow} WIDTH={width} PIPE={pipe} ===\n"+(OUT/f"{flow}_{width}_{pipe}.log").read_text())
                scripts.append(f"# {flow} WIDTH={width} PIPE={pipe}\ndesign -reset;\n"+(OUT/f"{flow}_{width}_{pipe}.ys").read_text())
            resources.append(item)
    (OUT/"resources.json").write_text(json.dumps(resources,indent=2)+"\n")
    (OUT/"generic_netlists.json").write_text(json.dumps(
        {f"width{width}_pipe{pipe}.v":(BUILD/f"generic_{width}_{pipe}.v").read_text()
         for width in [1,8,16,32] for pipe in [1,2]},indent=2)+"\n")
    (OUT/"synthesis.log").write_text("\n".join(synthesis_bundle))
    (OUT/"synthesis_commands.ys").write_text("\n".join(scripts))
    (OUT/"simulation.log").write_text("\n".join(f"=== {p.name} ===\n"+p.read_text() for p in sorted(OUT.glob("rtl_*.log"))+sorted(OUT.glob("gate_*.log"))))
    for r in rows:
        assert r["accepted"]==r["retired"]+r["dropped"]
        if r["scenario"]==0:assert r["max_output_gap"]==1 and r["latency_min"]==r["latency_max"]==r["pipe"]
        if r["flow"]=="generic-netlist":
            ref=next(x for x in rows if x["flow"]=="rtl" and all(x[k]==r[k] for k in ["width","pipe","seed","scenario"]))
            assert all(r[k]==ref[k] for k in FIELDS),"RTL/netlist trace statistics differ"
    (OUT/"toolchain.json").write_text(json.dumps(dict(
        iverilog=run([iv,*ivflags,"-V"]).splitlines()[0],yosys=run([yosys,"-V"]).strip(),
        python=__import__("platform").python_version(),simulations=len(rows),
        mutation_detected=True,netlist_checks=24,
        source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                       [ROOT/"rtl/stream_sum.sv",ROOT/"tb/tb.sv",ROOT/"formal/properties.sv"]}),indent=2)+"\n")
    for pipe in [1,2]:
        script=f"read_verilog -formal -sv rtl/stream_sum.sv formal/properties.sv; chparam -set WIDTH 4 -set PIPE {pipe} formal_top; prep -top formal_top -flatten; async2sync; chformal -lower; opt_clean; sat -seq 16 -prove-asserts -verify -set-init-zero -set-at 1 rst 1"
        script+=f"; sat -seq 4 -set-init-zero -set-at 1 rst 1 -set-at 2 rst 0 -set-at 3 rst 0 -set-at 4 rst 0 -set-at 4 m_valid 1 -set-at 4 m_ready 0 -set-at 4 balance {pipe} -show-inputs"
        (OUT/f"formal_{pipe}.ys").write_text(script+"\n")
        run([yosys,"-p",script],OUT/f"formal_{pipe}.log")
        assert "model found" in (OUT/f"formal_{pipe}.log").read_text(),"full stalled state was not reachable"
    (OUT/"formal.log").write_text("\n".join(f"=== PIPE={pipe}, WIDTH=4, BOUND=16 ===\n"+(OUT/f"formal_{pipe}.log").read_text() for pipe in [1,2]))
    (OUT/"formal_commands.ys").write_text("\n".join("design -reset;\n"+(OUT/f"formal_{pipe}.ys").read_text() for pipe in [1,2]))
    run([__import__("sys").executable,"analyze_results.py"])
    print("Simulation records:",len(rows))


if __name__=="__main__":
    main()
