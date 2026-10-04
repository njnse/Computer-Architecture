"""Reproduce tests and synthetic single-bank scheduling experiments."""
import csv
import json
import math
import platform
import random
import statistics
import unittest
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Request:
    ident: int
    client: int
    arrival: float
    row: int


def simulate(requests, policy, age_limit=128, hit=12, miss=36):
    if policy not in ["fcfs", "row-first", "age-bounded"]:
        raise ValueError("invalid policy")
    incoming=sorted(requests,key=lambda r:(r.arrival,r.ident))
    pending=[]
    i=0
    time=0.0
    opened=None
    records=[]
    while i<len(incoming) or pending:
        if not pending:
            time=max(time,incoming[i].arrival)
        while i<len(incoming) and incoming[i].arrival<=time:
            pending.append(incoming[i])
            i+=1
        oldest=lambda r:(r.arrival,r.ident)
        aged=[r for r in pending if time-r.arrival>=age_limit]
        hits=[r for r in pending if r.row==opened]
        choices=pending if policy=="fcfs" else (aged if policy=="age-bounded" and aged else hits or pending)
        req=min(choices,key=oldest)
        pending.remove(req)
        row_hit=req.row==opened
        start=time
        time+=hit if row_hit else miss
        records.append(dict(ident=req.ident,client=req.client,arrival=req.arrival,
            start=start,finish=time,row=req.row,row_hit=row_hit,latency=time-req.arrival))
        opened=req.row
    return records


def workload(seed, locality, interval, count=1000):
    rng=random.Random(seed)
    requests=[]
    t=0.0
    for i in range(count):
        t+=rng.uniform(.5,1.5)*interval
        requests.append(Request(i,0,t,0 if rng.random()<locality else rng.randrange(1,16)))
    t=0.0
    for i in range(count//5):
        t+=rng.uniform(.5,1.5)*interval*5
        requests.append(Request(count+i,1,t,rng.randrange(16,32)))
    return requests


def percentile(values,q):
    return sorted(values)[max(0,math.ceil(q*len(values))-1)]


class Tests(unittest.TestCase):
    def test_single_request_miss(self):
        r=simulate([Request(0,0,5,1)],"fcfs")[0]
        self.assertEqual((r["start"],r["finish"],r["latency"]),(5,41,36))

    def test_row_hit_service(self):
        r=simulate([Request(0,0,0,1),Request(1,0,0,1)],"fcfs")
        self.assertEqual([x["finish"]-x["start"] for x in r],[36,12])

    def test_age_protects_old_miss(self):
        req=[Request(0,0,0,0),Request(1,1,1,1),Request(2,0,2,0)]
        self.assertEqual([r["ident"] for r in simulate(req,"row-first")],[0,2,1])
        self.assertEqual([r["ident"] for r in simulate(req,"age-bounded",16)],[0,1,2])

    def test_zero_age_equals_fcfs(self):
        req=workload(3,.95,24,30)
        self.assertEqual(simulate(req,"fcfs"),simulate(req,"age-bounded",0))

    def test_infinite_age_equals_row_first(self):
        req=workload(3,.95,24,30)
        self.assertEqual(simulate(req,"row-first"),simulate(req,"age-bounded",float("inf")))

    def test_conservation_causality_nonoverlap(self):
        req=workload(4,.95,8,60)
        for policy in ["fcfs","row-first","age-bounded"]:
            records=simulate(req,policy)
            self.assertEqual({r.ident for r in req},{r["ident"] for r in records})
            self.assertEqual(len(records),len(req))
            previous=0
            for r in records:
                self.assertGreaterEqual(r["start"],r["arrival"])
                self.assertGreaterEqual(r["start"],previous)
                previous=r["finish"]

    def test_trace_reproducibility(self):
        self.assertEqual(workload(8,.5,8),workload(8,.5,8))


def run():
    out=Path(__file__).resolve().parent/"results"
    out.mkdir(exist_ok=True)
    rows=[]
    for seed in range(10):
        for locality in [.5,.95]:
            for interval in [8,24,64]:
                requests=workload(seed,locality,interval)
                for name,policy,limit in [("fcfs","fcfs",0),("row-first","row-first",0),
                                          ("age-64","age-bounded",64),("age-256","age-bounded",256)]:
                    records=simulate(requests,policy,limit)
                    duration=records[-1]["finish"]-min(r.arrival for r in requests)
                    sensitive=[r["latency"] for r in records if r["client"]==1]
                    rows.append(dict(seed=seed,locality=locality,interval=interval,policy=name,
                        requests=len(records),duration=duration,throughput=len(records)/duration,
                        hit_rate=sum(r["row_hit"] for r in records)/len(records),
                        mean_latency=statistics.mean(r["latency"] for r in records),
                        sensitive_mean=statistics.mean(sensitive),sensitive_p95=percentile(sensitive,.95),
                        sensitive_max=max(sensitive)))
    with (out/"raw.csv").open("w",newline="") as h:
        w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary={}
    for name in ["fcfs","row-first","age-64","age-256"]:
        sub=[r for r in rows if r["locality"]==.95 and r["interval"]==24 and r["policy"]==name]
        summary[name]={k:statistics.mean(r[k] for r in sub) for k in
                       ["throughput","hit_rate","sensitive_p95","sensitive_max","mean_latency"]}
    meta=dict(model="synthetic event-driven nonpreemptive single-bank model",
        units="abstract time units; no hardware calibration",python=platform.python_version(),
        platform=platform.platform(),command="python3 reproduce.py",rows=len(rows),
        seeds=list(range(10)),localities=[.5,.95],intervals=[8,24,64],
        requests_per_seed=1200,hit_service=12,miss_service=36,
        summary_slice=dict(locality=.95,interval=24),summary=summary)
    (out/"summary.json").write_text(json.dumps(meta,indent=2)+"\n")
    # Save a fully replayable small trace and its observed schedules.
    example=workload(0,.95,24,40)
    with (out/"example_trace.csv").open("w",newline="") as h:
        w=csv.writer(h);w.writerow(["ident","client","arrival","row"])
        w.writerows((r.ident,r.client,r.arrival,r.row) for r in example)
    example_records=[]
    for p in ["fcfs","row-first","age-bounded"]:
        example_records.extend(dict(policy=p,**r) for r in simulate(example,p,64))
    with (out/"example_schedules.csv").open("w",newline="") as h:
        w=csv.DictWriter(h,fieldnames=list(example_records[0]));w.writeheader();w.writerows(example_records)
    lines=["# Measured Results","","Summary slice: locality 0.95 and stream interarrival 24; means across ten seeds. Time units are abstract.","",
           "| Policy | Throughput | Hit rate | Sensitive p95 | Sensitive maximum |",
           "| --- | ---: | ---: | ---: | ---: |"]
    for name,s in summary.items():
        lines.append(f'| {name} | {s["throughput"]:.5f} | {s["hit_rate"]:.3f} | {s["sensitive_p95"]:.2f} | {s["sensitive_max"]:.2f} |')
    (out/"MEASUREMENTS.md").write_text("\n".join(lines)+"\n")
    maximum=max(s["sensitive_p95"] for s in summary.values())*1.15
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="800" height="430">',
         '<rect width="800" height="430" fill="white"/>',
         '<text x="30" y="30" font-family="sans-serif" font-size="20">Sensitive-client p95 latency</text>',
         '<text x="30" y="55" font-family="sans-serif" font-size="13">Locality 0.95; interarrival 24; ten-seed mean; abstract time units</text>']
    for i,(name,s) in enumerate(summary.items()):
        x=70+i*180;height=s["sensitive_p95"]/maximum*280
        svg.append(f'<rect x="{x}" y="{350-height:.2f}" width="95" height="{height:.2f}" fill="#287caf"/>')
        svg.append(f'<text x="{x}" y="{340-height:.2f}" font-family="sans-serif" font-size="14">{s["sensitive_p95"]:.1f}</text>')
        svg.append(f'<text x="{x}" y="380" font-family="sans-serif" font-size="14">{name}</text>')
    svg.append("</svg>")
    (out/"tail_latency.svg").write_text("\n".join(svg)+"\n")
    print(json.dumps(meta,indent=2))


if __name__=="__main__":
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    if not result.wasSuccessful():
        raise SystemExit(1)
    run()
