"""Synthetic committed-branch trace experiment; not a CPU simulator."""
import csv
import json
import platform
import random
import statistics
from pathlib import Path


class Predictor:
    def __init__(self, entries, history_bits, mode, threads=4):
        if entries < threads or entries & (entries - 1):
            raise ValueError("entries must be a power of two and cover all threads")
        if mode not in ("shared-global", "shared-local", "partitioned-local"):
            raise ValueError("unknown mode")
        self.table = [1] * entries
        self.histories = [0] * threads
        self.global_history = 0
        self.mask = (1 << history_bits) - 1
        self.mode, self.threads = mode, threads

    def index(self, thread, pc):
        history = self.global_history if self.mode == "shared-global" else self.histories[thread]
        width = len(self.table) // self.threads if self.mode == "partitioned-local" else len(self.table)
        offset = thread * width if self.mode == "partitioned-local" else 0
        return offset + (((pc >> 2) ^ history) & (width - 1))

    def step(self, thread, pc, taken):
        index = self.index(thread, pc)
        wrong = (self.table[index] >= 2) != taken
        self.table[index] = min(3, self.table[index] + 1) if taken else max(0, self.table[index] - 1)
        self.histories[thread] = ((self.histories[thread] << 1) | int(taken)) & self.mask
        self.global_history = ((self.global_history << 1) | int(taken)) & self.mask
        return int(wrong)


def trace(seed, regime, quantum, length=10240):
    rng = random.Random(seed)
    seen = [0] * 4
    biases = [[rng.choice([0.05, 0.95]) for _ in range(256)] for _ in range(4)]
    output = []
    for i in range(length):
        thread = (i // quantum) % 4
        if regime == "opposing-bias":
            site, probability = 0, (0.95 if thread % 2 == 0 else 0.05)
        elif regime == "shared-bias":
            site, probability = 0, 0.95
        elif regime == "capacity-pressure":
            site = rng.randrange(256) if thread == 0 else 256 + thread
            probability = biases[0][site] if thread == 0 else 0.95
        elif regime == "thread-alternation":
            site = 0
            probability = float(seen[thread] % 2 == 0)
        else:
            raise ValueError(regime)
        taken = rng.random() < probability
        seen[thread] += 1
        output.append((thread, 0x1000 + site * 4, taken))
    return output


def run():
    root = Path(__file__).resolve().parent
    out = root / "results"
    out.mkdir(exist_ok=True)
    rows = []
    modes = ["shared-global", "shared-local", "partitioned-local"]
    regimes = ["opposing-bias", "shared-bias", "capacity-pressure", "thread-alternation"]
    for seed in range(5):
        for regime in regimes:
            for quantum in [1, 16, 256]:
                events = trace(seed, regime, quantum)
                for entries in [32, 128, 512]:
                    for history in [0, 4, 8]:
                        for mode in modes:
                            predictor = Predictor(entries, history, mode)
                            errors = [0] * 4
                            counts = [0] * 4
                            for i, (thread, pc, taken) in enumerate(events):
                                wrong = predictor.step(thread, pc, taken)
                                if i >= 2048:
                                    errors[thread] += wrong
                                    counts[thread] += 1
                            n, misses = sum(counts), sum(errors)
                            rows.append(dict(seed=seed,regime=regime,quantum=quantum,
                                entries=entries,history_bits=history,mode=mode,
                                measured_branches=n,mispredictions=misses,
                                error_percent=100*misses/n,
                                worst_thread_error_percent=max(100*e/c for e,c in zip(errors,counts)),
                                per_thread_errors=";".join(map(str,errors)),
                                per_thread_counts=";".join(map(str,counts)),
                                counter_bits=2*entries,
                                history_storage_bits=history*(1 if mode=="shared-global" else 4)))
    with (out/"raw.csv").open("w",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {}
    for regime in regimes:
        summary[regime] = {}
        for mode in modes:
            values=[r["error_percent"] for r in rows if r["regime"]==regime
                    and r["mode"]==mode and r["entries"]==128
                    and r["history_bits"]==4 and r["quantum"]==1]
            summary[regime][mode]=dict(mean=statistics.mean(values),minimum=min(values),maximum=max(values))
    metadata=dict(model="synthetic committed-branch predictor model; not a CPU simulator",
        python=platform.python_version(),platform=platform.platform(),
        command="python3 reproduce.py",warmup_branches=2048,measured_branches=8192,
        seeds=list(range(5)),threads=4,entries=[32,128,512],history_bits=[0,4,8],
        scheduling_quanta=[1,16,256],rows=len(rows),
        summary_slice=dict(entries=128,history_bits=4,quantum=1),summary=summary)
    (out/"summary.json").write_text(json.dumps(metadata,indent=2)+"\n")
    svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="480">',
         '<rect width="1100" height="480" fill="white"/>',
         '<text x="25" y="30" font-size="21" font-family="sans-serif">Thread sharing versus counter partitioning</text>',
         '<text x="25" y="55" font-size="13" font-family="sans-serif">Error percentage; 128 counters; 4 history bits; quantum 1; mean of 5 seeds</text>']
    colors=["#536b85","#2883b5","#d88b28"]
    for tick in [0,10,20,30,40,50]:
        y=375-tick*5
        svg.append(f'<line x1="45" y1="{y}" x2="1070" y2="{y}" stroke="#ddd"/>')
        svg.append(f'<text x="10" y="{y+4}" font-size="12" font-family="sans-serif">{tick}</text>')
    for i, regime in enumerate(regimes):
        x=70+i*260
        for j,mode in enumerate(modes):
            mean=summary[regime][mode]["mean"]
            svg.append(f'<rect x="{x+j*65}" y="{375-mean*5:.2f}" width="50" height="{mean*5:.2f}" fill="{colors[j]}"/>')
            svg.append(f'<text x="{x+j*65}" y="{365-mean*5:.2f}" font-size="12" font-family="sans-serif">{mean:.2f}</text>')
        svg.append(f'<text x="{x}" y="405" font-size="13" font-family="sans-serif">{regime}</text>')
    for j,mode in enumerate(modes):
        svg.append(f'<rect x="{70+j*340}" y="440" width="15" height="15" fill="{colors[j]}"/>')
        svg.append(f'<text x="{95+j*340}" y="453" font-size="14" font-family="sans-serif">{mode}</text>')
    svg.append("</svg>")
    (out/"comparison.svg").write_text("\n".join(svg)+"\n")
    lines=["# Measured Results","",
           "Predeclared slice: 128 counters, 4 history bits, one branch per thread switch. Values are error percentages, averaged across five synthetic seeds.","",
           "| Workload | Shared global | Shared per-thread history | Partitioned per-thread history |",
           "| --- | ---: | ---: | ---: |"]
    for regime in regimes:
        vals=[summary[regime][m]["mean"] for m in modes]
        lines.append(f"| {regime} | {vals[0]:.3f}% | {vals[1]:.3f}% | {vals[2]:.3f}% |")
    lines+=["","The full CSV includes every configuration and per-thread counts. These are trace-model measurements, not application performance.",""]
    (out/"MEASUREMENTS.md").write_text("\n".join(lines))
    print(json.dumps(metadata,indent=2))


if __name__=="__main__":
    run()
