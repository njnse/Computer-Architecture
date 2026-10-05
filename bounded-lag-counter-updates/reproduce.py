"""Compile, validate, benchmark, and report bounded-lag counters on Linux."""
import csv
import hashlib
import itertools
import json
import os
import platform
import random
import re
import statistics
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
MODES=[("packed","packed",1),("padded","padded",1),("shared","shared",1),
       ("batch-16","packed",16),("batch-64","packed",64)]
MASK=(1<<64)-1


def execute(mode,threads,n,work,batch):
    p=subprocess.run([str(ROOT/"bench"),mode,str(threads),str(n),str(work),str(batch)],
                     capture_output=True,text=True,check=True,timeout=60)
    return json.loads(p.stdout)


def reference(threads,n,work):
    checksum=0
    for t in range(threads):
        x=t+1
        for _ in range(n*work):
            x=(x*6364136223846793005+1442695040888963407)&MASK
        checksum=(checksum+x)&MASK
    return checksum


def bootstrap(values,seed=19):
    rng=random.Random(seed)
    estimates=sorted(statistics.median(rng.choices(values,k=len(values))) for _ in range(2000))
    return estimates[49],estimates[1949]


def run():
    os.chdir(ROOT)
    out=ROOT/"results";out.mkdir(exist_ok=True)
    cgroup_before=Path("/sys/fs/cgroup/cpu.stat").read_text() if Path("/sys/fs/cgroup/cpu.stat").exists() else "unavailable"
    flags=["-O3","-std=c11","-pthread","-Wall","-Wextra"]
    subprocess.run(["gcc",*flags,"bench.c","-o","bench"],check=True)
    disassembly=subprocess.check_output(["objdump","-d","bench"],text=True)
    locked_lines=[l for l in disassembly.splitlines() if re.search(r"\slock\s",l)]
    assert locked_lines,"no atomic locked instruction in inspected binary"
    (out/"assembly_evidence.txt").write_text("\n".join(locked_lines)+"\n")
    checks=[]
    for label,mode,batch in MODES:
        for threads,n,work in [(1,0,0),(1,65,3),(2,129,2)]:
            r=execute(mode,threads,n,work,batch)
            assert r["total"]==threads*n
            assert r["checksum"]==reference(threads,n,work)
            assert r["flushes"]==threads*((n+batch-1)//batch)
            assert r["counter_stride"]==(64 if mode=="padded" else 8)
            assert r["packed_alignment_mod64"]==r["padded_alignment_mod64"]==0
            checks.append(dict(policy=label,threads=threads,iterations=n,work=work,status="passed"))
    (out/"validation.json").write_text(json.dumps(dict(checks=checks,assembly_lock_check=True),indent=2)+"\n")
    # Separate warmup/pilot from retained evaluation; no setting selected using measured outcomes.
    workloads=[(0,2000000),(32,250000),(256,100000)]
    configs=list(itertools.product([1,2],workloads,MODES))
    pilot=[]
    for threads,(work,n),(label,mode,batch) in configs:
        r=execute(mode,threads,n,work,batch)
        pilot.append(dict(threads=threads,work=work,policy=label,**r))
    rows=[]
    for repeat in range(9):
        order=configs.copy();random.Random(100+repeat).shuffle(order)
        for position,(threads,(work,n),(label,mode,batch)) in enumerate(order):
            r=execute(mode,threads,n,work,batch)
            assert r["total"]==threads*n
            rows.append(dict(repeat=repeat,position=position,threads=threads,
                work=work,iterations=n,policy=label,batch=batch,
                updates=threads*n,ns_per_update=r["seconds"]*1e9/(threads*n),
                logical_counter_bytes=(threads*64 if label=="padded" else 8 if label=="shared" else threads*8),
                maximum_buffered_updates_per_thread=batch,**r))
    for threads,(work,n) in itertools.product([1,2],workloads):
        group=[r for r in rows if r["threads"]==threads and r["work"]==work]
        assert len({r["checksum"] for r in group})==1
    with (out/"raw.csv").open("w",newline="") as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    (out/"pilot.json").write_text(json.dumps(pilot,indent=2)+"\n")
    empty=[execute("packed",2,0,0,1)["seconds"] for _ in range(9)]
    convergence=[]
    for repeat in range(5):
        settings=list(itertools.product([500000,2000000,8000000],["packed","padded","batch-64"]))
        random.Random(500+repeat).shuffle(settings)
        for n,label in settings:
            batch=64 if label=="batch-64" else 1
            r=execute("padded" if label=="padded" else "packed",2,n,0,batch)
            assert r["total"]==n*2
            convergence.append(dict(repeat=repeat,iterations=n,policy=label,
                                    ns_per_update=r["seconds"]*1e9/(2*n),**r))
    with (out/"convergence.csv").open("w",newline="") as h:
        w=csv.DictWriter(h,fieldnames=list(convergence[0]));w.writeheader();w.writerows(convergence)
    summary=[]
    for threads,(work,n),label in itertools.product([1,2],workloads,[x[0] for x in MODES]):
        group=[r for r in rows if r["threads"]==threads and r["work"]==work and r["policy"]==label]
        base={r["repeat"]:r for r in rows if r["threads"]==threads and r["work"]==work and r["policy"]=="padded"}
        ratios=[base[r["repeat"]]["seconds"]/r["seconds"] for r in group]
        low,high=bootstrap(ratios)
        summary.append(dict(threads=threads,work=work,policy=label,
            median_ns=statistics.median(r["ns_per_update"] for r in group),
            median_speedup_vs_padded=statistics.median(ratios),
            bootstrap_median_low=low,bootstrap_median_high=high,
            minimum_seconds=min(r["seconds"] for r in group),
            maximum_seconds=max(r["seconds"] for r in group)))
    sysfiles={}
    for f in ["/sys/fs/cgroup/cpu.max","/sys/fs/cgroup/cpu.stat",
              "/sys/devices/system/cpu/cpu1/topology/core_id",
              "/sys/devices/system/cpu/cpu2/topology/core_id",
              "/sys/devices/system/cpu/cpu1/cache/index0/coherency_line_size"]:
        if Path(f).exists():sysfiles[f]=Path(f).read_text().strip()
    cpu=next((l for l in Path("/proc/cpuinfo").read_text().splitlines() if l.startswith("model name")),"unknown")
    meta=dict(command="python3 reproduce.py",python=platform.python_version(),
        platform=platform.platform(),cpu=cpu,allowed_cpus=sorted(os.sched_getaffinity(0)),
        cpu_placement="main on first allowed CPU; workers on next allowed CPUs",
        gcc=subprocess.check_output(["gcc","--version"],text=True).splitlines()[0],
        flags=flags,source_sha256=hashlib.sha256((ROOT/"bench.c").read_bytes()).hexdigest(),
        perf_available=False,pilot_runs=len(pilot),evaluation_runs=len(rows),
        convergence_runs=len(convergence),repeats=9,cgroup_before=cgroup_before,
        random_order_seeds=list(range(100,109)),empty_two_thread_median_seconds=statistics.median(empty),
        sysfs=sysfiles,summary=summary)
    (out/"summary.json").write_text(json.dumps(meta,indent=2)+"\n")
    lines=["# Hardware Measurements","",
        "Linux cloud-host wall-clock results; median of nine repetitions. Speedup is paired against padded counters. Intervals bootstrap the median paired ratio, conditional on this run.","",
        "| Threads | Work steps | Policy | ns/update | Speedup vs padded | Bootstrap interval |",
        "| --- | --- | --- | ---: | ---: | --- |"]
    for s in summary:
        lines.append(f'| {s["threads"]} | {s["work"]} | {s["policy"]} | {s["median_ns"]:.3f} | {s["median_speedup_vs_padded"]:.3f} | {s["bootstrap_median_low"]:.3f}–{s["bootstrap_median_high"]:.3f} |')
    (out/"MEASUREMENTS.md").write_text("\n".join(lines)+"\n")
    subset=[s for s in summary if s["threads"]==2 and s["work"]==0]
    maxval=max(s["median_ns"] for s in subset)*1.15
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="450">',
        '<rect width="900" height="450" fill="white"/>',
        '<text x="25" y="30" font-family="sans-serif" font-size="20">Two-worker counter updates on the measured host</text>',
        '<text x="25" y="55" font-family="sans-serif" font-size="13">Zero arithmetic work; median ns/update; nine randomized repetitions</text>']
    for i,s in enumerate(subset):
        x=60+i*165;h=s["median_ns"]/maxval*280
        svg.append(f'<rect x="{x}" y="{360-h:.2f}" width="90" height="{h:.2f}" fill="#297da9"/>')
        svg.append(f'<text x="{x}" y="{350-h:.2f}" font-family="sans-serif" font-size="14">{s["median_ns"]:.2f}</text>')
        svg.append(f'<text x="{x}" y="395" font-family="sans-serif" font-size="14">{s["policy"]}</text>')
    svg.append("</svg>")
    (out/"comparison.svg").write_text("\n".join(svg)+"\n")
    print(json.dumps(dict(validation_cases=len(checks),runs=len(rows),empty_median=meta["empty_two_thread_median_seconds"],
                         two_thread_results=[s for s in summary if s["threads"]==2]),indent=2))


if __name__=="__main__":
    run()
