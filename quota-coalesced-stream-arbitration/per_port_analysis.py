"""Replay simulator-validated vectors to expose per-source latency and censoring."""
import csv,hashlib,json
from collections import deque
from pathlib import Path
from reference import make_vectors,traffic

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"results"

def main():
    records=[];checked=[]
    for raw in csv.DictReader((OUT/"simulation.csv").open()):
        if raw["flow"]!="rtl" or raw["n"]!="4" or raw["width"]!="16" or raw["scenario"]=="protocol":continue
        if raw["quota"]=="2":continue
        n,w,q,f,seed,cycles,warmup=[int(raw[k]) for k in ("n","width","quota","fixed","seed","cycles","warmup")]
        vf=ROOT/"build/per_port_vectors.txt"
        make_vectors(vf,n,w,q,f,raw["scenario"],seed,cycles,warmup)
        assert hashlib.sha256(vf.read_bytes()).hexdigest()==raw["vector_sha256"],"replay differs from simulator-checked vectors"
        arrivals,_,_=traffic(n,raw["scenario"],seed,cycles)
        queues=[deque() for _ in range(n)];latencies=[[] for _ in range(n)];head_wait=[0]*n;waits=[[] for _ in range(n)]
        for t,line in enumerate(vf.read_text().splitlines()):
            fields=line.split();reset=int(fields[0]);req=int(fields[2],16);grant=int(fields[6],16)
            if reset:queues=[deque() for _ in range(n)];head_wait=[0]*n
            for i,count in enumerate(arrivals[t]):queues[i].extend([t]*count)
            for i in range(n):
                if not (req & (1<<i)):head_wait[i]=0
                elif grant & (1<<i):
                    birth=queues[i].popleft()
                    if t>=warmup:latencies[i].append(t-birth);waits[i].append(head_wait[i])
                    head_wait[i]=0
                elif grant:head_wait[i]+=1
        assert [len(a) for a in latencies]==json.loads(raw["service_counts"])
        checked.append(raw["vector_sha256"])
        for i in range(n):
            values=sorted(latencies[i]);opportunities=sorted(waits[i])
            def p99(a):return a[int((len(a)-1)*.99)] if a else None
            records.append(dict(scenario=raw["scenario"],seed=seed,quota=q,fixed=f,port=i,
                completed=len(values),queue_latency_p99=p99(values),queue_latency_max=max(values,default=None),
                head_wait_p99=p99(opportunities),head_wait_max=max(opportunities,default=None),
                pending_at_end=len(queues[i]),oldest_pending_age=(cycles-1-queues[i][0]) if queues[i] else None))
    with (OUT/"per_port.csv").open("w",newline="") as h:
        writer=csv.DictWriter(h,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    (OUT/"per_port_validation.json").write_text(json.dumps(dict(
        passed=True,matched_vector_replays=len(checked),port_records=len(records),
        method="Replay of exact vectors already checked cycle-by-cycle by Icarus; no new hardware measurements",
        vector_hashes=checked,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2)+"\n")
    print("Validated per-port vector replays:",len(checked))

if __name__=="__main__":main()
