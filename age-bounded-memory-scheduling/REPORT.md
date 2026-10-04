# Request Aging Can Increase Tail Latency

## Research question

Does prioritizing old requests over row-buffer hits reliably reduce the tail latency of a sparse memory requester? How does this depend on offered load?

The implemented experiment tests this question with fixed FCFS, row-first, and age-bounded schedulers. It finds that protecting old requests can worsen tail latency by reducing service capacity. This is a reproducible negative result, not a claim of a new scheduling algorithm.

## Implemented model

One nonpreemptive bank serves one request at a time. The bank retains the row of the last serviced request. A row hit takes 12 abstract time units; a row change takes 36. The initial row is closed. Newly arriving requests become eligible only when their arrival time is reached; selection occurs at service boundaries.

FCFS selects the oldest pending request, breaking ties by identifier. Row-first selects the oldest pending hit if any, otherwise the oldest pending request. Age-bounded selects the oldest request exceeding the age threshold when one exists, otherwise applies row-first. Thresholds are 64 and 256.

Age is waiting time before service, not completed request latency. A threshold does not enforce an absolute wait bound: multiple aged requests can remain queued. Finite traces drain fully, so this experiment does not prove infinite-stream starvation freedom or quantify steady-state starvation.

All policies receive identical offered requests and service-time assumptions. Aging consumes no extra simulated decision latency; consequently even the negative results omit possible hardware overhead.

## Workloads and experimental design

Two synthetic clients generate requests:

- Client zero issues 1,000 requests with interarrival intervals uniformly between 0.5 and 1.5 times a specified mean. With probability 0.5 or 0.95 it accesses row zero; otherwise it selects rows 1–15.
- Client one issues 200 requests with five times that mean interarrival interval, accessing rows 16–31 uniformly.

Client one is called sensitive because its latency is the focal metric, not because an actual application dependency chain is modeled. Its requests are independent offered arrivals. There is no closed-loop issue stall or CPU feedback.

Mean stream intervals are 8, 24, and 64; row locality is 0.5 or 0.95; ten seeds and four policies produce 240 records. Each policy sees the exact same trace for a seed/locality/interval. All 1,200 requests are measured, including startup and final drain. There is no warmup or steady-state inference.

The trace generator is checked in and uses Python's standard random generator. No external workload data are used. Environment and parameter metadata appear in the JSON manifest. The example trace and schedule files expose individual decisions for inspection.

## Metrics

Throughput is completed requests divided by the time from the first arrival to the last completion. Mean latency includes both clients. Sensitive p95 uses the nearest-rank percentile over client one's 200 requests per trace. Summary values average each seed's metric; the mean p95 is not the percentile of all pooled samples.

Maximum latency and row-hit fraction are also recorded. This is end-to-end response time in the model, not merely service time. Seed variability reflects the synthetic generator, not real application populations.

## Measured findings

For row locality 0.95 and mean stream interval 24, the ten-seed means are:

| Policy | Throughput, requests/unit | Sensitive p95, units | Hit fraction |
| --- | ---: | ---: | ---: |
| FCFS | 0.04660 | 1626.51 | 0.608 |
| Row-first | 0.04922 | 202.09 | 0.670 |
| Age 64 | 0.04667 | 1589.63 | 0.609 |
| Age 256 | 0.04922 | 201.58 | 0.670 |

At this load, the strict age-64 policy has approximately 7.87 times the sensitive p95 of row-first. The permissive threshold behaves nearly like row-first. A statement that stronger aging always improves latency is falsified in this controlled case.

The average offered rate is approximately 1.2/24 = 0.05 requests per unit. Actual finite-trace arrivals vary by seed. Small reductions in row locality can push service capacity below offered load, creating a growing backlog. Once many requests age, strict aging largely becomes FCFS, which repeatedly switches rows. This explains the measured delay amplification; it is not evidence that all real aging controllers behave this way.

With locality 0.95 and interval 8, all policies have large delays: sensitive p95 is 16,917.15 for FCFS, 12,627.92 for row-first, 16,914.75 for age 64, and 16,799.55 for age 256. Row-first throughput is 0.07920 versus 0.04669 for FCFS. This finite overload case does not establish stability for an endless workload.

With interval 64, throughput is approximately 0.01848 for every policy, and sensitive p95 is approximately 46.3 units. At light load there is little queueing benefit to scheduling changes.

All locality-0.5 conditions, remaining seed outcomes, sensitive maximum values, and mean response times are included in the raw CSV rather than discarded.

## Correctness checks

Seven tests passed: exact one-request miss timing, row-hit service timing, protection of an old miss, zero-threshold equivalence to FCFS, infinite-threshold equivalence to row-first, conservation/causality/nonoverlap, and deterministic workload regeneration.

Additional artifact validation checks unique configuration counts, finite nonnegative metrics, and SVG syntax. These tests validate the implementation of the stated model, not hardware fidelity.

## Limits and related work

The queue is unbounded, arrivals are exogenous, and service is a single-bank serial abstraction. Real DRAM has banks, ranks, bus timing, command eligibility, refresh, write draining, bank-level parallelism, finite request queues, and CPU feedback. Row-first here is inspired by row-hit preference; it is not a complete FR-FCFS implementation.

No hardware timings are calibrated, and no speedup, IPC, energy, or area claims are made. Overload and finite-drain effects must not be generalized to steady-state tail guarantees.

Live academic literature verification was unavailable. The literature and novelty assessment remain provisional; no checked citations or priority claims are supplied. A thesis review should cover FR-FCFS-style scheduling, fairness-oriented memory scheduling, batching, slowdown-aware policies, and deadline/age mechanisms. These are established research areas.

## Thesis extension

The candidate contribution is a load-aware age controller that balances old-request service with minimum useful row batching. Its hypothesis is that queue growth and arrival/service-rate estimates can prevent aggressive age protection from collapsing service capacity.

A follow-up should compare adaptive thresholds against strong existing fairness and slowdown policies, estimate requester criticality without privileged labels, and include a finite-queue closed-loop model. A DRAM timing simulator and CPU integration are required before architectural performance claims. Hardware metadata, controller decision latency, and requester-level fairness must be accounted for.

HPCA or MICRO may fit a validated scheduling mechanism with clear implementation costs and robust application-level evidence. The present project is a complete executable preliminary experiment, not a completed thesis or a submission-ready paper.
