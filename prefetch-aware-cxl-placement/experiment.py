"""Controlled additive residual-wait model; not a CPU or CXL simulator."""
import csv
import itertools
import json
import platform
import random
import statistics
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Demand:
    page: int
    lead_ns: float
    exposed: float


def wait(event, latency):
    return max(0.0, latency - event.lead_ns) * event.exposed


def generate(seed, regime, count=2400):
    rng = random.Random(seed)
    events = []
    # Eight hot stream pages and eight less frequent dependent-load pages.
    for _ in range(count):
        stream = rng.random() < 0.72
        page = rng.randrange(8) + (0 if stream else 8)
        if regime == "frequency-aligned":
            lead, exposed = 0.0, 1.0
        elif regime == "prefetch-hidden":
            lead = rng.uniform(180, 320) if stream else 0.0
            exposed = 0.25 if stream else 1.0
        elif regime == "phase-reversal":
            lead = rng.uniform(180, 320) if not stream else 0.0
            exposed = 1.0 if stream else 0.25
        else:
            raise ValueError(regime)
        events.append(Demand(page, lead, exposed))
    return events


def benefit(events, local, remote):
    scores = [0.0] * 16
    for event in events:
        scores[event.page] += wait(event, remote) - wait(event, local)
    return scores


def select(scores, capacity):
    return frozenset(sorted(range(16), key=lambda p: (-scores[p], p))[:capacity])


def policy(events, name, capacity, rate, seed, local, remote):
    rng = random.Random(seed)
    sampled = [event for event in events if rng.random() < rate]
    if name == "frequency":
        scores = [0.0] * 16
        for event in sampled:
            scores[event.page] += 1
    elif name == "residual":
        scores = benefit(sampled, local, remote)
    else:
        raise ValueError(name)
    return select(scores, capacity)


def cost(events, placement, local, remote):
    # Fixed compute component plus serialized exposed wait. Not measured runtime.
    return len(events) * 50 + sum(
        wait(event, local if event.page in placement else remote)
        for event in events
    )


def oracle(events, capacity, local, remote):
    # Exact optimum only for static placement in this separable model.
    return select(benefit(events, local, remote), capacity)


def run():
    root = Path(__file__).resolve().parent
    out = root / "results"
    out.mkdir(exist_ok=True)
    rows = []
    for seed, regime, capacity, remote, rate in itertools.product(
        range(10), ["frequency-aligned", "prefetch-hidden", "phase-reversal"],
        [2, 4, 8], [200, 300, 400], [0.01, 0.1, 1.0]
    ):
        train = generate(seed * 2, "prefetch-hidden" if regime == "phase-reversal" else regime)
        test = generate(seed * 2 + 1, regime)
        initial = frozenset(range(capacity))
        static_cost = cost(test, initial, 100, remote)
        placements = {
            name: policy(train, name, capacity, rate, seed + 1000, 100, remote)
            for name in ["frequency", "residual"]
        }
        placements["oracle"] = oracle(test, capacity, 100, remote)
        for name, placement in placements.items():
            raw = cost(test, placement, 100, remote)
            # One promotion displaces one resident page. Pair cost includes both copies.
            pairs = len(placement - initial)
            for pair_cost in [0, 5000, 20000]:
                migration = pairs * pair_cost
                rows.append(dict(
                    seed=seed, regime=regime, capacity=capacity, remote_ns=remote,
                    sample_rate=rate, policy=name, migration_pair_ns=pair_cost,
                    placement=";".join(map(str, sorted(placement))),
                    moved_pairs=pairs, service_cost_ns=raw,
                    migration_cost_ns=migration, total_cost_ns=raw + migration,
                    static_cost_ns=static_cost, speedup=static_cost / (raw + migration),
                ))
    with (out / "raw.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    # Predefined illustrative slice, not selected after seeing results.
    summary = {}
    for regime in ["frequency-aligned", "prefetch-hidden", "phase-reversal"]:
        summary[regime] = {}
        for name in ["frequency", "residual", "oracle"]:
            values = [
                r["speedup"] for r in rows if r["regime"] == regime
                and r["policy"] == name and r["capacity"] == 4
                and r["remote_ns"] == 300 and r["sample_rate"] == 0.1
                and r["migration_pair_ns"] == 5000
            ]
            summary[regime][name] = {
                "mean_speedup": statistics.mean(values),
                "min_speedup": min(values), "max_speedup": max(values),
                "seeds": len(values),
            }
    metadata = {
        "model": "additive exposed residual wait; analytical synthetic experiment",
        "python": platform.python_version(), "platform": platform.platform(),
        "command": "python3 experiment.py", "rows": len(rows),
        "local_latency_ns": 100, "compute_ns_per_demand": 50,
        "train_demands": 2400, "test_demands": 2400,
        "seeds": list(range(10)), "pages": 16,
        "remote_latency_ns": [200, 300, 400], "capacities_pages": [2, 4, 8],
        "sample_rates": [0.01, 0.1, 1.0],
        "migration_pair_ns": [0, 5000, 20000],
        "summary_slice": {"capacity": 4, "remote_ns": 300,
                          "sample_rate": 0.1, "migration_pair_ns": 5000},
        "summary": summary,
    }
    (out / "summary.json").write_text(json.dumps(metadata, indent=2) + "\n")
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="960" height="460" viewBox="0 0 960 460">',
           '<rect width="960" height="460" fill="white"/>',
           '<text x="30" y="30" font-family="sans-serif" font-size="20">Static-placement speedup in the analytical model</text>',
           '<text x="30" y="55" font-family="sans-serif" font-size="13">Mean across 10 seeds; 4 local pages; 300 ns remote; 10% sampling; 5 us per migration pair</text>']
    colors = ["#63748a", "#247cba", "#d38427"]
    scale = 150
    for i, (regime, entries) in enumerate(summary.items()):
        x = 80 + i * 300
        svg.append(f'<text x="{x}" y="390" font-family="sans-serif" font-size="14">{regime}</text>')
        for j, (name, result) in enumerate(entries.items()):
            h = result["mean_speedup"] * scale
            bx = x + j * 72
            svg.append(f'<rect x="{bx}" y="{350-h:.2f}" width="55" height="{h:.2f}" fill="{colors[j]}"/>')
            svg.append(f'<text x="{bx}" y="{340-h:.2f}" font-family="sans-serif" font-size="13">{result["mean_speedup"]:.3f}</text>')
    svg.append('<line x1="50" y1="200" x2="925" y2="200" stroke="#222" stroke-dasharray="5 5"/>')
    svg.append('<text x="5" y="205" font-family="sans-serif" font-size="12">1.0x</text>')
    for j, name in enumerate(["Frequency", "Residual", "Static oracle"]):
        svg.append(f'<rect x="{70+j*280}" y="420" width="15" height="15" fill="{colors[j]}"/>')
        svg.append(f'<text x="{95+j*280}" y="433" font-family="sans-serif" font-size="14">{name}</text>')
    svg.append("</svg>")
    (out / "comparison.svg").write_text("\n".join(svg) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    run()
