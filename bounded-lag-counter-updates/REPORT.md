# Hardware Evaluation of Bounded-Lag Counter Updates

## Question and falsifiable hypothesis

Can local batching reduce update cost beyond a strong cache-line-padded baseline while retaining a bounded number of buffered events? Does that benefit persist when useful work separates updates?

Before examining results, the experiment fixed two batch sizes, two worker counts, and three work intensities. The hypothesis fails as a general improvement if gains disappear outside an update-dominated regime. It also fails for workloads requiring immediate publication, because batching changes their semantics regardless of speed.

## Implemented contribution

The implemented mechanism accumulates a thread's events locally, performs a relaxed atomic addition at batch size 16 or 64, and flushes the remainder before completing. Its strong baseline is separate cache-line-padded atomic counters, not merely a contended global atomic.

Packed per-thread counters isolate false sharing from true sharing; one shared atomic provides a true-sharing control. A one-worker experiment removes concurrent cross-worker writes. Work intensities and duration checks test whether the update bottleneck is relevant and whether fixed measurement overhead explains the result.

Padding and batching are established mechanisms. This artifact contributes a reproducible measurement and explicit tradeoff analysis on the available host; it does not claim algorithmic novelty or implement a production counter library.

## Execution environment

The host reports Intel Xeon Platinum 8573C, a 64-byte cache line, three allowed logical CPUs, and a cgroup quota of two CPU-equivalents. The main thread is pinned to the first allowed CPU and workers to the next one or two. Guest topology reports distinct core identifiers for workers, but this does not prove their physical placement on an exclusive machine.

Python 3.12.14, the exact GCC version, flags `-O3 -std=c11 -pthread -Wall -Wextra`, kernel/platform description, C-source SHA-256, CPU placement, and cgroup observations are retained in the manifest. No PMU tool was available. The measurement is wall-clock execution on the running cloud host, not bare-metal calibration.

Wall time uses CLOCK_MONOTONIC_RAW. Worker CPU clocks provide a second measure of time consumed while executing. Startup threads and affinity setup occur before the measured interval; start/finish barriers and clock calls remain inside or near its edges. Empty two-worker trials have median duration 90.53 microseconds. This overhead is reported, not subtracted, because subtraction would presume identical scheduling costs.

## Workload and semantic matching

Each worker performs a fixed number of logical events. Work intensity zero performs no arithmetic beyond loop/counter logic. Intensities 32 and 256 add that many dependent unsigned 64-bit multiply-add steps per event. The recurrence result is printed as a checksum, preventing elimination; an independent Python implementation verifies it on small cases.

Iterations per worker are 2,000,000 for zero work, 250,000 for work 32, and 100,000 for work 256. Comparisons within each intensity use identical work and counts. Cross-intensity timing differences include deliberately different work and should not be treated as identical tasks.

All atomic updates use memory_order_relaxed. Each batched addition is atomic, but a sum of independent counters is not a linearizable aggregate. Batching does not have the same intermediate visibility as per-event updates. Final counts after synchronization are exact and verified.

For batch B, local pending events are at most B: a worker may be preempted after reaching the threshold but before executing its atomic flush. Between completed loop iterations the normal bound is B-1. No finite time-based freshness bound follows under arbitrary scheduling. This artifact does not measure a concurrent reader or validate an observer protocol.

At two workers, active logical counter storage is 16 bytes for packed/batched counters and 128 bytes for padded counters; active counter cache-line footprint is one versus two lines. These figures exclude argument structures, synchronization, local accumulators, compiler register spills, alignment wastage, and the benchmark's separately declared unused policy arrays. They are not the whole-process memory footprint.

## Protocol, controls, and revisions

Thirty pilot configurations warm the executable and are retained separately. They were not used to choose a winning batch size. Nine measured blocks each contain every configuration in independently shuffled order using documented seeds. This reduces systematic ordering bias but cannot eliminate shared-host scheduling noise or time correlations.

Both fixed batch sizes are evaluated on all work intensities and worker counts. No held-out outcome is used to select a configuration; all alternatives are reported. For an adaptive controller, a separate training/evaluation protocol would be required.

After an initial measurement pass, instrumentation was extended with worker CPU time, explicit alignment checks, and duration sensitivity; the full retained experiment was rerun. The earlier pass is not pooled into the reported dataset. Assembly filtering was tightened to recognize lock-prefixed instructions rather than matching the word fragment in clock symbols; this changed validation evidence, not measured algorithms.

The independent duration study uses 500,000, 2,000,000, and 8,000,000 iterations per worker, zero arithmetic work, three policies, and five randomized repetitions: 45 additional measurements.

## Main results

For two workers and zero arithmetic work, median update cost is:

| Policy | Median ns per logical event |
| --- | ---: |
| Packed | 15.239 |
| Padded | 5.348 |
| Shared | 14.937 |
| Batch 16 | 1.640 |
| Batch 64 | 0.920 |

Using paired block ratios, batch 16's median speedup over padded is 3.452x, with approximate bootstrap interval 2.704–3.787x. Batch 64's corresponding value is 5.942x, interval 4.736–8.045x. These are ratios of aligned repetitions; they differ from dividing separately computed medians.

The bootstrap resamples nine paired ratios 2,000 times and summarizes the median. Intervals describe resampling uncertainty conditional on this execution, not cross-host reproducibility, measurement independence, or a causal proof. All outliers are retained.

Packed and genuinely shared counters have similar update costs in this regime. Padding improves packed counters, consistent with avoiding destructive cache-line sharing. However, no coherence-event counts are available, so wall-clock differences alone cannot quantify cache-line ownership transfers.

## Negative results and boundary

With work 32, batch 64's median paired speedup over padded is 1.094x, interval 0.970–1.390x. With work 256 it is 0.996x, interval 0.661–1.426x. Both intervals include one. The data therefore do not establish a benefit in these compute-heavy conditions; the zero-work result must not be generalized to whole applications.

In the one-worker zero-work control, packed and padded median costs are 9.618 and 9.805 ns/event. These independently measured one-worker runs need not match two-worker per-event averages, which divide aggregate worker events by elapsed wall time. Batch 64 is 1.080 ns/event, demonstrating that batching can reduce atomic-operation overhead even without inter-worker false sharing.

This control means the batching gain cannot be attributed entirely to reduced coherence traffic. It reduces the number of atomic operations as well as the opportunity for coherence transfers.

## Duration and scheduling checks

Median ns/event in the zero-work, two-worker duration study:

| Iterations per worker | Packed | Padded | Batch 64 |
| --- | ---: | ---: | ---: |
| 500,000 | 14.214 | 5.349 | 1.277 |
| 2,000,000 | 15.713 | 5.619 | 0.907 |
| 8,000,000 | 15.612 | 5.212 | 0.962 |

The rank ordering survives longer measurement windows. These data support robustness of the update-dominated observation, not universal warmup convergence. Shared-host jitter remains visible in raw measurements.

The cgroup recorded two throttled periods and 3,162 microseconds of throttled time across the instrumented collection window. This is aggregate telemetry, not a per-trial correction. For the two-worker zero-work slice, median summed-worker-CPU/wall ratios are approximately 1.934 for packed, 1.877 for padded, and 1.862 for batch 64, consistent with substantially concurrent execution. Scheduling gaps and quota effects cannot be eliminated from these observations.

## Correctness and evidence mapping

Fifteen benchmark cases cover all five policies with zero events, a non-divisible batch tail, and two-worker arithmetic. Every case validates exact total, independently computed checksum, atomic flush count, counter stride, and 64-byte alignment. The executable checks affinity success and lock-free atomic support. Disassembly retains actual locked-add instructions.

Every retained measurement verifies exact totals. Checksums agree across policies for each workload, worker count, and event count. Additional validation checks unique records, speedup arithmetic, checksum consistency, convergence counts, and figure syntax.

| Claim | Evidence | Remaining uncertainty |
| --- | --- | --- |
| Exact final count | Independent totals, tail tests, all measured runs | Intermediate reader semantics are not tested |
| Padding helps packed counters on this host | Two-worker layout ablation and one-worker control | No PMU-based coherence attribution |
| Batching helps update-heavy tasks beyond padding | Paired results and duration sensitivity | Only a microbenchmark on one cloud host |
| Gain vanishes with substantial work | All workload intensities and uncertainty intervals | Other application structures may differ |
| Batching reduces publication frequency | Exact flush count checks | Reader cost/freshness under load is unmeasured |

## Verified related work

[SHERIFF: Precise Detection and Automatic Mitigation of False Sharing](https://people.umass.edu/tongping/pubs/sheriff-oopsla11.pdf), by Tongping Liu and Emery D. Berger, presents detection and mitigation mechanisms that isolate thread updates. It is a broader runtime system, not a batching implementation or a baseline executed here.

[Hoard: A Scalable Memory Allocator for Multithreaded Applications](https://people.cs.umass.edu/~emery/hoard/asplos2000.pdf), by Emery D. Berger, Kathryn S. McKinley, Robert D. Blumofe, and Paul R. Wilson, addresses allocator scalability and false-sharing-related layout problems. This experiment changes counter layout directly rather than evaluating an allocator.

The [Linux kernel false-sharing documentation](https://www.kernel.org/doc/html/v6.7/kernel-hacking/false-sharing.html) discusses padding, reducing writes, and delayed per-CPU synchronization, and recommends cache-to-cache profiling. It directly establishes that the tested mitigation families are known techniques.

These primary sources were opened and checked. The literature review is focused, not exhaustive; no priority claim is justified.

## Thesis and conference extension

A stronger research contribution would be a visibility-budget-aware runtime that chooses layout and batching under reader freshness and memory constraints. It requires concurrent readers, application-derived event streams, workload phase changes, topology diversity, modern scalable-counter baselines, and a training protocol separated from held-out evaluation.

Before an ASPLOS or architecture submission, evaluate end-to-end applications and independently reproduce the results on dedicated hardware. Collect coherence PMU evidence, establish reader semantics, and quantify controller overhead and memory costs. This artifact is complete and reproducible, but it is not a completed master's thesis or conference-ready paper.
