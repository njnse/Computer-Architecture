"""Derive matched comparisons and a standalone SVG from executed raw observations."""
import csv,json,math,os,statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"results"

def load():
    rows=list(csv.DictReader((OUT/"simulation.csv").open()))
    for r in rows:
        for k in r:
            if k not in ("scenario","flow","vector_sha256","service_counts"):
                r[k]=float(r[k]) if "." in r[k] or "e-" in r[k] else int(r[k])
    return rows

def main():
    rows=load();resources=json.loads((OUT/"resources.json").read_text())
    selected=[r for r in rows if r["flow"]=="rtl" and r["n"]==4 and r["width"]==16 and r["scenario"]!="protocol"]
    summary=[];effects=[]
    metrics=["throughput","switches_per_transfer","serviced_wait_max","jain","queue_latency_p99","max_pending_age","unserved_ports"]
    for scenario in sorted(set(r["scenario"] for r in selected)):
        for q,f in ((1,1),(1,0),(2,0),(4,0),(8,0)):
            group=[r for r in selected if r["scenario"]==scenario and r["quota"]==q and r["fixed"]==f]
            record=dict(scenario=scenario,quota=q,fixed=f,seed_count=len(group))
            for m in metrics:
                values=[r[m] for r in group]
                record[m+"_mean"]=statistics.mean(values)
                record[m+"_min"]=min(values);record[m+"_max"]=max(values)
            summary.append(record)
        baseline={r["seed"]:r for r in selected if r["scenario"]==scenario and r["quota"]==1 and not r["fixed"]}
        candidate={r["seed"]:r for r in selected if r["scenario"]==scenario and r["quota"]==4 and not r["fixed"]}
        for m in metrics:
            differences=[candidate[s][m]-baseline[s][m] for s in sorted(baseline)]
            mean=statistics.mean(differences)
            # Five stochastic seeds, paired by identical open-loop arrival/ready sequences.
            half=2.776*statistics.stdev(differences)/math.sqrt(5)
            effects.append(dict(scenario=scenario,metric=m,delta_mean=mean,
                                paired_seed_t95_low=mean-half,paired_seed_t95_high=mean+half,
                                interpretation="Seed variability only; saturated workload duplicates are not independent evidence"))
    def write_csv(path,records):
        with path.open("w",newline="") as h:
            wr=csv.DictWriter(h,fieldnames=list(records[0]));wr.writeheader();wr.writerows(records)
    write_csv(OUT/"comparison.csv",summary)
    (OUT/"paired_effects.json").write_text(json.dumps(effects,indent=2)+"\n")
    mapped=[]
    for r in resources:
        if r["flow"]!="ice40":continue
        cells=r["num_cells_by_type"]
        mapped.append(dict(n=r["n"],width=r["width"],quota=r["quota"],fixed=r["fixed"],
                           lut4=cells.get("SB_LUT4",0),ff=sum(v for k,v in cells.items() if k.startswith("SB_DFF")),
                           carry=cells.get("SB_CARRY",0),bram=cells.get("SB_RAM40_4K",0),total_cells=r["num_cells"]))
    write_csv(OUT/"fpga_resources.csv",mapped)
    sat=[r for r in summary if r["scenario"]=="saturated" and not r["fixed"]]
    sat.sort(key=lambda r:r["quota"])
    area=[r for r in mapped if r["n"]==4 and r["width"]==16 and not r["fixed"]];area.sort(key=lambda r:r["quota"])
    os.environ.setdefault("MPLCONFIGDIR",str(ROOT/"build/matplotlib"))
    os.environ.setdefault("XDG_CACHE_HOME",str(ROOT/"build/cache"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    matplotlib.rcParams["svg.hashsalt"]="quota-coalesced-stream-arbitration"
    fig,ax=plt.subplots(2,2,figsize=(11,7),constrained_layout=True)
    qs=[r["quota"] for r in sat]
    for axis in ax.flat:
        axis.set_xscale("log",base=2);axis.set_xticks(qs,labels=[str(q) for q in qs])
        axis.set_xlabel("Accepted-beat quota Q");axis.grid(alpha=.25)
    ax[0,0].plot(qs,[r["throughput_mean"] for r in sat],"o-",color="#1876d2")
    ax[0,0].set_ylim(0,1.2);ax[0,0].set_ylabel("Accepted beats / clock")
    ax[0,0].set_title("Saturated throughput: no improvement")
    ax[0,1].plot(qs,[r["switches_per_transfer_mean"] for r in sat],"o-",color="#008c75")
    ax[0,1].set_ylabel("Source changes / accepted beat");ax[0,1].set_title("Transitions, not power")
    ax[1,0].plot(qs,[r["serviced_wait_max_mean"] for r in sat],"o-",color="#bb4a37")
    ax[1,0].set_ylabel("Other accepted beats before service")
    ax[1,0].set_title("Maximum serviced head wait")
    ax[1,1].plot(qs,[r["lut4"] for r in area],"o-",label="SB_LUT4",color="#1876d2")
    ax[1,1].plot(qs,[r["ff"] for r in area],"s-",label="Mapped flip-flops",color="#bb4a37")
    ax[1,1].set_ylabel("Mapped cells");ax[1,1].set_title("iCE40 mapping: no placement/timing")
    ax[1,1].legend()
    for axis,values in [(ax[0,1],[r["switches_per_transfer_mean"] for r in sat]),
                        (ax[1,0],[r["serviced_wait_max_mean"] for r in sat])]:
        for x,y in zip(qs,values):axis.annotate(f"{y:.3g}",(x,y),xytext=(3,7),textcoords="offset points")
    fig.suptitle("Quota coalescing: fewer source changes, longer waits\n4 sources, 16-bit beats; executed RTL simulation and Yosys mapping")
    fig.savefig(OUT/"tradeoffs.svg",metadata={"Date":None})
    fig.savefig(ROOT/"build/tradeoffs_preview.png",dpi=130)
    plt.close(fig)
    from per_port_analysis import main as per_port
    per_port()
    print(json.dumps(dict(saturated=sat,area=area),indent=2))

if __name__=="__main__":main()
