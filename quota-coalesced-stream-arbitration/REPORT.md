# Quota-coalesced ready/valid arbitration: an executed RTL tradeoff study

## Research question and contribution

Does retaining a requester for at most Q accepted independent beats reduce source changes while preserving work-conserving throughput, and what waiting/resource costs does this impose? The implemented candidate is handshake-safe quota round-robin. It is compared with a simple fixed-priority baseline and the established two-priority-search masked round-robin mechanism at Q=1. Q=1 also ablates coalescing; Q=2/Q=8 locate the quota tradeoff.

The contribution is a complete reproducible hardware artifact: interface specification, synthesizable RTL, an independently coded deque reference, cycle-exact executed verification, fault-sensitive measurement, generic netlist cross-checks, bounded safety/fairness checks, and real iCE40 mapping. Quota scheduling is an established concept. No novelty, completed thesis, or conference-readiness claim is made.

## Method and experimental contract

The unbuffered multiplexer forwards opaque independent beats. A receiver stall locks the selected source; quota and cyclic scan history advance only on actual acceptance. Idle intervals expire unused quota but preserve cyclic history. Payload storage, source queues, and receivers are outside the synthesized design. There is no added payload pipeline register. This is not an AXI/packet arbiter, cycle-accurate CPU simulator, or physical FPGA measurement.

Twenty-three matched configurations cover N=1/3/4/8, WIDTH=16, fixed priority and Q=1/4/8; additional N=4 widths 1/8/32 at Q=1/4, and N=4/WIDTH=16/Q=2. The tested source queues receive identical open-loop arrivals for every policy, with identical receiver-ready sequences. Five evaluation seeds (11,29,47,101,211) were fixed before execution; diagnostic seed 7 is separate. There was no tuning on evaluation data. Each main evaluation has 4096 clocks, with 512 excluded from reported performance but still verified. Workload code and provenance are in `reference.py` and `SPEC.md`.

The seven synthetic traffic families are saturation, long/random sink stalls, a persistent dominant source with sparse minority arrivals, periodic bursts, underloaded random arrivals, rotating dominant phases, and repeated active reset. They stress arbitration behavior; they are not measured application/DMA traces. The N=4 burst workload has largely nonoverlapping source bursts, intentionally exposing a case where coalescing has no opportunity to help.

Icarus 12.0 executed the RTL and zero-delay generic netlists. Yosys 0.69 revision `9f75ca1f9`, through pinned YoWASP, performed generic synthesis and `synth_ice40 -device hx` using its bundled iCE40 HX library. All mapped configurations use the same settings. There is no selected FPGA package/capacity, floorplan, clock constraint, place-and-route result, board, or power measurement. Therefore mapped LUT/FF counts are valid synthesis evidence, but they cannot establish achieved FPGA Fmax or system performance.

## Main measurements

At N=4/WIDTH=16 with all four sources continuously requesting and receiver always ready:

| Policy | Accepted beats/clock | Source changes/transfer | Maximum serviced head wait, other transfers | iCE40 LUT4 | Mapped FF |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fixed priority | 1.000 | 0.000 | 0 for the only served port; three ports starve | 75 | 6 |
| Round-robin Q=1 | 1.000 | 0.999721 | 3 | 97 | 8 |
| Coalesced Q=2 | 1.000 | approximately 0.500 | 6 | 81 | 8 |
| Coalesced Q=4 | 1.000 | 0.250000 | 12 | 82 | 9 |
| Coalesced Q=8 | 1.000 | approximately 0.125 | 24 | 112 | 10 |

Q=4 reduces accepted-source changes by approximately 75% relative to Q=1. **It does not improve throughput.** The maximum observed continuous-head wait rises fourfold, from 3 to 12 competing transfers. Q=1/Q=4 serve all four saturated sources equally (Jain index 1); fixed priority has Jain index 0.25 and never serves three ports. A reported fixed-priority serviced wait or completed-request latency of zero is not evidence of fairness: starved requests are censored, and their pending age reaches 4093 clocks.

All variants accept at every available ready/pending opportunity in the tested scenarios. With long/random sink stalls, Q=1 and Q=4 both average 0.647879 beats/clock across the five seeds. Their mean source-change rates are 0.999569 and 0.249956. Accepted-opportunity fairness remains bounded, but wall-clock waiting may grow with arbitrarily long receiver stalls.

At N=4/WIDTH=16, other traffic exposes the boundary of the transition benefit:

| Scenario | Throughput, both Q=1/Q=4 | Changes/transfer Q=1 | Changes/transfer Q=4 | Mean per-seed maximum serviced head wait Q=1 -> Q=4 |
| --- | ---: | ---: | ---: | ---: |
| Sparse-minority asymmetric | 1.000000 | 0.213616 | 0.181975 | 2.6 -> 5.6 |
| Underloaded random | 0.602121 | 0.863629 | 0.730233 | 3.0 -> 8.2 |
| Periodic bursts | 0.330357 | 0.124155 | 0.124155 | 0.0 -> 0.0 |
| Rotating dominant phases | 0.879520 | 0.176072 | 0.158874 | 2.6 -> 6.8 |
| Active reset stress | 0.641574 | 0.993476 | 0.246154 | 3.0 -> 12.0 |

The benefit is smaller when requests rarely contend, and absent in the disjoint-burst case. Quota coalescing increases serviced-head waits even when aggregate queue p99 is unchanged. Aggregate completed-request p99 means are 4.2 clocks for both Q=1/Q=4 in light and phase-change traffic, but that metric must not be substituted for a per-port QoS guarantee. `per_port.csv` separately exposes each port's completed latency, waiting, pending count, and oldest pending age by replaying exact simulator-checked vector hashes.

In asymmetric traffic, port 0 is persistently requesting and ports 1/2/3 receive sparse independent arrivals. Mean per-seed completed queue p99 for port 1 increases from **1.8 to 4.4 clocks**, port 2 from **1.6 to 4.0**, and port 3 from **1.2 to 4.0** under Q=1 -> Q=4. The dominant port's p99 remains 442.8 clocks, so the aggregate p99 of 442.8 hides the minority-port regressions. This is the main QoS negative finding: transition reduction benefits no throughput here and makes short minority requests wait behind a longer dominant-source visit. The per-port analysis replays 140 exact verified vector files into 560 port records, with hashes and source provenance in `per_port_validation.json`.

## Resource sensitivity and negative results

Mapped costs are not monotonic in quota or source count. At WIDTH=16:

| N | LUT4 Q=1 -> Q=4 | FF Q=1 -> Q=4 | Interpretation |
| ---: | ---: | ---: | --- |
| 1 | 22 -> 30 | 2 -> 5 | Extra mapped logic without any multiport benefit |
| 3 | 54 -> 69 | 5 -> 9 | Resource regression despite fewer source transitions |
| 4 | 97 -> 82 | 8 -> 9 | 15.5% fewer LUT4, one additional FF |
| 8 | 246 -> 223 | 14 -> 12 | Both mapped counts decrease in this tool/configuration |

At N=4, WIDTH=1 gives 38 LUT4 for both Q=1/Q=4, while FF rises from 8 to 9. WIDTH=8 gives 68 -> 56 LUT4; WIDTH=32 gives 164 -> 132. Q=8 at N=4/WIDTH=16 costs 112 LUT4 and 10 FF, with one carry cell, worsening area and waiting compared with Q=1 while further reducing transitions. No BRAM was inferred. Full generic cell types and mapped cell types are retained in `resources.json`; these totals include the actual selection mux and control, not external queues.

The architectural cause of fewer transitions is explicit repeated-source acceptance. The cause of the larger waiting bound is allowing each competing source up to Q accepts before scanning onward. The nonmonotonic LUT/FF counts arise after synthesis optimization and technology mapping of different control equations/enables; these counts alone do not identify a unique gate-level causal explanation. Additional RTL coding-style controls and placed timing are needed before generalizing the area pattern. The single-port result also identifies a useful engineering follow-up: specialize away unnecessary scheduling state for N=1.

## Validation, uncertainty, and reproducibility

The final main dataset has **828 RTL runs and 69 generic-netlist runs**, totaling **3,491,584 checked clock samples and 2,535,117 observed transfers**. Every cycle's valid, ready mask, source, and payload was checked against the independent reference. The simulator separately accumulated transfer/stall/service/transition/wait counters. Netlist records exactly match their RTL counterparts. An additional 24 longer-run/warmup diagnostics validate the same measurement path. Forty-six synthesis flows completed without unintended inferred latches.

Three 20-step bounded proofs at N=3/WIDTH=2 cover Q=1/Q=4 and fixed priority. Legal source hold assumptions are explicit; reset masks output/ready; one-hot/request qualification, work conservation, payload identity, and stall stability are verified. Round-robin fairness counters additionally stay within `(N-1)*Q`. Separate SAT witnesses show stalled-output states are reachable. These are reduced-size bounded checks, not a universal unbounded proof.

Both deliberate mutations were detected: payload corruption and removal of the stall-selection lock. Functional counters exercised idle, single/concurrent requests, backpressure, late arrivals, cyclic wrap, same-source runs, and reset while pending. They are scenario coverage, not UVM/code/toggle coverage. The actual pass counts and coverage are machine-generated in `validation.json`; setup corrections are recorded in `EXPERIMENT_HISTORY.md`.

Stochastic comparisons use paired seeds sharing arrivals and receiver-ready sequences. `paired_effects.json` reports mean differences with a five-seed paired t interval (critical value 2.776). For light traffic, Q=4 minus Q=1 source changes/transfer is -0.133396, with interval [-0.139957,-0.126836]. For sink stalls it is -0.749613, interval [-0.749919,-0.749308]. These intervals characterize seed variability within these generators; they do not imply uncertainty over real applications, FPGA silicon, or timing. Saturated/disjoint-burst duplicate seeds are deterministic repeats and are not treated as independent evidence. Queue p99 includes only completed requests; explicit pending/unserved statistics prevent starvation from masquerading as low latency.

`warmup_sensitivity.csv` records 2048/4096/8192-cycle runs and warmups 0/256/1024. Saturation retains one beat per available non-reset clock and the quota waiting bound; including the two initial reset clocks with warmup=0 produces 0.999512 beats/clock rather than 1. Stochastic sink-stall throughput ranges from 0.642253 to 0.646484 for both Q=1/Q=4 in these diagnostics; light traffic ranges from 0.606689 to 0.617188 for both. Estimates vary with sampled arrival/ready sequences and window length; no claim of application convergence is made. Original vectors, logs, and source hashes can be regenerated from one command. Full logs/netlists are losslessly archived, and `commands.json` records actual executed argument vectors and return codes without credentials.

## Evidence-to-claim mapping

| Claim | Evidence | Boundary |
| --- | --- | --- |
| Tested RTL correctly implements selection and handshake stability | `simulation.csv`, `simulation.log`, TB assertions, two mutation failures | Legal source protocol; no gate delays or X-propagation signoff |
| Candidate preserves available-cycle throughput | `fires == opportunities`, independent counters, saturated closed form | These unbuffered generated traffic models; no system speedup |
| Coalescing trades transitions for service waiting | Matched Q=1/2/4/8 records, `comparison.csv`, `tradeoffs.svg` | Transitions are not energy measurements |
| Reduced-size bounded safety/fairness | Formal source, exact scripts, lossless proof/witness logs | 20 steps, N=3/WIDTH=2, initialized/reset legal sources |
| Mapped resource changes can reverse across dimensions | `resources.json`, `fpga_resources.csv`, full synthesis logs | iCE40 HX mapping, no placement/frequency/ASIC area |
| Per-port tail/censoring analysis is traceable to execution | `per_port.csv`, replay hashes and validation JSON | Replay of already verified vectors, not a new board measurement |

## Related work and thesis extension

The closest inspected sources are Matt Weber's [Arbiters: Design Ideas and Coding Styles](https://abdullahyildiz.github.io/files/Arbiters-Design_Ideas_and_Coding_Styles.pdf), especially its two-priority-arbiter mask method, and Charles Eric LaForest's [Round-Robin Arbiter](https://fpgacpu.ca/fpga/Arbiter_Round_Robin.html), including preservation of idle history. This artifact adapts the architectural comparison to independent accepted beats, bounded visits, and explicit backpressure locking. It does not reproduce their exact coding/synthesis results or establish a literature gap. Source access and differences are documented in `RELATED_WORK.md`.

A thesis could ask whether **adaptive accepted-beat coalescing with explicit per-source latency caps** improves measured locality/energy in FPGA DMA or accelerator interconnects under real application traffic. That requires a new candidate policy, broader primary-literature review, strong weighted/deficit and age-sensitive baselines, separated tuning/evaluation applications, and matched area/resource budgets. Next engineering stages are pipelined/skid-buffer integration, constrained place-and-route with timing closure, application trace provenance, board-level throughput/locality measurements, and actual measured switching/power if energy is claimed.

For ASIC verification depth, migrate the validated checks into a real executable UVM environment with agents, sequencers, monitor/scoreboard separation, functional coverage closure, reset concurrency, protocol error injection, and constrained-random regression on a validated simulator/library. Current evidence is explicitly non-UVM. Parameter-wide unbounded proofs, CDC/RDC, reset-release analysis, X propagation, and delayed gate simulations remain production-verification work. These limitations prevent a conference-ready claim while leaving a complete, useful RTL/verification/synthesis artifact.
