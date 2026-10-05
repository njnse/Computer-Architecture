# Computer Architecture Research

Reproducible experimental projects with implementations, correctness tests, raw results, figures, and English analysis. Project names describe research topics without date labels.

| Project | Artifact | Main observation |
| --- | --- | --- |
| [Prefetch-aware page placement](prefetch-aware-cxl-placement/README.md) | Controlled analytical experiment; 7,290 records | Residual-wait ranking helps in a prefetch-hidden workload but fails after phase reversal |
| [Thread-aware branch prediction](thread-aware-branch-prediction/README.md) | Synthetic branch-trace experiment; 1,620 records | Partitioning reduces interference but can worsen prediction under uneven capacity pressure |
| [Age-bounded memory scheduling](age-bounded-memory-scheduling/README.md) | Event-driven single-bank experiment; 240 records | Strict request aging can reduce row locality and substantially increase tail latency |
| [Bounded-lag counter updates](bounded-lag-counter-updates/README.md) | Hardware microbenchmark; 270 evaluation runs and 45 duration checks | Batching beats padded counters for update-heavy tasks, but loses clear benefit with substantial work and changes visibility |

Each report distinguishes model findings from simulation or hardware evidence. Thesis and conference directions are research objectives, not claims of completed publication-level validation.
