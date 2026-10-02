# Prefetch-Aware Page Placement for CXL Memory

**Research question:** Can an online estimate of residual demand stall, conditioned on prefetch behavior, allocate scarce local DRAM more effectively than access-frequency-based tiering?

**Status:** Research proposal. No experiments have been executed. The novelty assessment and related-work mapping are provisional pending a systematic literature review.

## Motivation

A system with local DRAM and CXL-attached memory has heterogeneous latency and bandwidth. Promoting frequently accessed pages to local DRAM is intuitive, but access frequency alone does not establish how much application execution time a promotion saves.

Consider two pages with equal access counts. Page A belongs to a predictable stream: prefetches often arrive before demand and memory-level parallelism hides remaining latency. Page B serves dependent loads: demands frequently wait for data and little latency overlaps with other work. Promoting B may offer greater performance benefit even if A generates more traffic.

This creates a possible interaction between page placement and prefetching. A prefetch policy can change a page's apparent hotness, and migration can change prefetch timeliness and contention. The project investigates whether accounting for that interaction yields a useful architectural mechanism.

This is a hypothesis, not an established limitation of every existing tiering policy.

## Thesis hypothesis

Under constrained local-memory capacity, pages differ materially in the execution stall that remains after prefetching and overlap. A practical approximation of this residual stall can improve page placement over well-tuned independent tiering and prefetch controllers, after accounting for monitoring overhead and migration costs.

The proposed contribution is the placement signal and its implementation. It is not simply enabling prefetching in a tiered-memory system.

## Architectural mechanism

Use a bounded, sampled hardware table indexed by physical page number. The LLC and memory-request path record:

- demand accesses and demand misses;
- whether a demand merges with an outstanding prefetch;
- prefetch usefulness and lateness;
- sampled time spent waiting for outstanding requests;
- per-core memory-level parallelism and tier queue pressure;
- placement history and migration cooldown.

A demand that hits a prefetched cache line supplies evidence that its latency was hidden. A demand merging with an outstanding prefetch supplies evidence of incomplete hiding. A miss without a matching prefetch is another class. None of these classes by itself proves that the access lies on the execution critical path.

For the initial mechanism, use observable request wait and outstanding-request counts as proxies. Estimate exact execution-critical stall only in a simulator oracle, then quantify the proxy's error. Shared pages require contributions from multiple cores rather than a single owner.

For page p, rank candidate promotion benefit using:

    G(p) = sum over sampled demand events [
        demand_wait(event)
        * overlap_weight(event)
        * estimated_local_reduction(event)
    ]

G is an estimated benefit rate scaled to a defined decision horizon. estimated_local_reduction is a bounded fraction calibrated using tier-specific observed demand service time and queue pressure. It must not assume that all remote latency disappears after promotion.

For each replacement pair, compare the predicted gain from promoting the remote page against the loss from demoting the local page. Include copying both pages, bandwidth interference, mapping updates, and monitoring costs:

    predicted net benefit
      = promotion gain over horizon
      - demotion loss over horizon
      - migration and interference cost

The model must use consistent units; bandwidth consumption should be converted through an explicit penalty model rather than directly subtracted from time. First test simple threshold variants before introducing more parameters.

An OS component receives candidate page identifiers and performs migration with mapping and TLB maintenance. Hardware does not move pages implicitly. Use hysteresis, minimum residency, a migration bandwidth cap, and cooldown to avoid oscillation. Reset or age relevant observations after migration.

Hold the prefetch algorithm fixed in the primary study. Add bounded prefetch-degree coordination only after establishing whether the placement signal itself helps.

## Scope and implementation

Use gem5 for a multicore CPU, LLC, local DRAM, and a second memory tier. Begin with a generic two-tier timing model and clearly identify it as such. Before claiming CXL-specific conclusions, model or calibrate the CXL path's latency, bandwidth limits, queues, and interference. A fixed added latency alone is insufficient.

Start with controlled address allocation and simulated migration. Model data-copy traffic, mapping changes, blocked accesses or forwarding during copying, and required translation maintenance. If a full OS migration implementation is too large initially, document the functional abstraction and charge its costs explicitly. Selected full-system validation should follow for a systems claim.

Use 4 KiB pages initially, then evaluate large-page sensitivity. Track sample-table size, lookup traffic, dropped samples, counter width, aliasing, and metadata memory accesses. Avoid an unbounded per-page table in the implementable design.

A simulation-only thesis is possible if model limitations are explicit. A real CXL platform would strengthen calibration but is not required for the initial hypothesis test.

## Evaluation

### Baselines

1. No migration with fixed placement and identical capacity limits.
2. Frequency-based migration with demand-only counts.
3. Frequency-based migration with all memory traffic counted.
4. Latency- or stall-aware tiering selected from verified prior work.
5. Prefetch-aware tiering selected from verified prior work, if available.
6. Independently tuned migration and adaptive prefetch control.
7. Proposed placement with the same prefetch policy as each relevant baseline.

All dynamic policies receive equal monitoring and migration budgets. Use held-out workloads for tuning. Report disabled-prefetch configurations as diagnostic comparisons, not as the main competitive baseline.

An offline placement search on small regions can provide an optimistic reference. Do not call it a strict upper bound unless it is actually optimal under the same migration, interference, and placement constraints.

### Workloads

Start with synthetic workloads that separately control predictability, dependency chains, memory-level parallelism, phase length, and page working set. Include workloads where all policies should behave similarly.

Then use selected memory-intensive workloads from GAP Benchmark Suite, NAS Parallel Benchmarks, and an open-source in-memory key-value workload. SPEC CPU is optional and requires the appropriate license.

Study single applications first, then multiprogrammed mixtures with predictable and irregular accesses. Select and publish regions, warmup behavior, input sizes, and phase coverage. A trace-only model must not be used to infer out-of-order stall changes without validation.

### Experimental dimensions

Sweep local-memory capacity, remote latency, remote bandwidth, core count, prefetch aggressiveness, sampling rate, control horizon, and migration budget. Initial values are experimental choices, not claims about a particular device.

Run workloads whose working sets exceed local memory, plus controls that fit locally. Include remote-memory saturation and workloads with short phases where migration may be harmful.

### Metrics

Report application runtime and IPC, weighted speedup for mixes, maximum slowdown for fairness, demand wait-time distributions, prefetch accuracy and timeliness, tier bandwidth, migrations and copied bytes, metadata size, monitoring traffic, and control overhead.

Request latency is not a substitute for application stall. Attribute improvements through controlled comparisons and corroborate them with execution-level measurements.

For deterministic simulation, report effects across workload regions and mixes rather than treating repeat runs as independent statistical evidence. For stochastic workloads or sampling, use multiple seeds and confidence intervals.

### Ablations

- remove the prefetch-derived features;
- remove the overlap correction;
- replace the proposed signal with demand frequency;
- remove migration-cost accounting;
- remove hysteresis;
- vary sample-table capacity and page aggregation granularity;
- compare sampled estimates with the detailed simulator-only signal.

Keep budgets and tuning effort equal across ablations.

## Falsification and decision criteria

Reject the central hypothesis if, after equal-budget tuning and overhead accounting:

- prefetched and non-prefetched pages show no useful difference in placement sensitivity;
- ordinary demand frequency ranks promotion benefit nearly as well;
- the sampled signal cannot track changing phases accurately;
- gains disappear against the strongest applicable prior policy;
- migration costs consistently exceed savings.

A provisional target is at least a 5% geometric-mean runtime improvement against the strongest implementable baseline on a predeclared suite, with bounded worst-case slowdown and explicit overhead. This is a project go/no-go target, not a predicted result or a conference acceptance criterion. Set the exact target and slowdown bound before final testing.

## Related work and novelty gate

The literature review must cover four intersecting areas:

| Area | What to establish |
| --- | --- |
| CXL and heterogeneous-memory tiering | Which policies already use latency, stall, or prefetch information |
| Hardware-assisted page placement | Which sampled signals and interfaces are already available |
| Feedback-directed prefetching | How timeliness, usefulness, pollution, and bandwidth are measured |
| Criticality and memory-level parallelism | Which practical signals predict execution-time sensitivity |

Useful search terms include “CXL prefetch-aware page migration,” “tiered memory prefetch timeliness,” “stall-aware memory placement,” and “criticality-aware page promotion.”

Feedback Directed Prefetching and memory-level-parallelism-aware memory management are known starting points for the conceptual review; their exact bibliographic details and relevance must be verified before citation. No checked bibliography is supplied here.

Do not claim the first prefetch-aware tiering mechanism. The novelty gate requires reading the closest papers and identifying a specific unaddressed mechanism, constraint, or measurement. If prior work already contains the same signal and coordination, revise or retire this proposal.

## Execution plan

1. Build the bibliography and nearest-work comparison; decide whether the mechanism remains distinct.
2. Establish a two-tier timing model and reproduce frequency-based placement.
3. Run fixed-placement and static-prefetch sensitivity experiments to locate workloads where promotion benefit differs from frequency.
4. Add detailed simulator instrumentation and test the ideal signal.
5. Implement the bounded sampled approximation and migration controller.
6. Run the primary comparisons, overhead accounting, and ablations.
7. Validate selected conclusions against a more detailed model or available hardware.
8. Package scripts, configurations, workload manifests, raw data, and limitations for reproduction.

A realistic scope is one mechanism, one primary simulator, and a focused workload suite over roughly four to six months after establishing the novelty gate. Calibration and simulator modifications may extend this.

## Potential venue

HPCA is the primary target if the contribution is a practical architectural monitoring and placement mechanism with convincing multicore evaluation. MICRO is plausible if predictor design and implementation dominate. ASPLOS is more appropriate if a validated hardware–OS interface and full-system implementation become the principal contribution.

Conference submission is a research objective. This document is a thesis starting point, not a completed or submission-ready paper.

