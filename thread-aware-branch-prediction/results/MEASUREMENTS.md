# Measured Results

Predeclared slice: 128 counters, 4 history bits, one branch per thread switch. Values are error percentages, averaged across five synthetic seeds.

| Workload | Shared global | Shared per-thread history | Partitioned per-thread history |
| --- | ---: | ---: | ---: |
| opposing-bias | 6.250% | 6.252% | 5.552% |
| shared-bias | 5.349% | 5.356% | 5.444% |
| capacity-pressure | 14.351% | 16.306% | 16.567% |
| thread-alternation | 0.000% | 0.000% | 0.000% |

The full CSV includes every configuration and per-thread counts. These are trace-model measurements, not application performance.
