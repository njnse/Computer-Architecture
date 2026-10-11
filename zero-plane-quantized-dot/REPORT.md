# Exact zero-plane scheduling for quantized dot products

## Research question and evidence boundary

Can a shared activation bit-plane bitmap improve exact signed dot service time beyond a counter-based contiguous-span scheduler, and when do grouping and FPGA resource costs erase that benefit? The expected mechanism is removal of internal zero planes. Leading/trailing trimming already removes excess precision; comparing only against fixed width would inflate the apparent contribution.

This is a completed bounded RTL implementation and verification experiment on attributed public quantized inputs. It is not a trained quantization algorithm, complete accelerator, completed thesis or conference-ready paper. No hardware frequency, power, physical KV260 result or GPU training is measured.

## Method

The interface and initial hypothesis are in SPEC.md. Each transaction contains N signed W-bit activation/weight pairs and a tag. Parallel multiplication is a registered throughput baseline. Fixed serial, leading-only, bitmap contiguous-span and zero-plane modes use the same accumulation/shifting structure. A separately implemented offset/counter baseline executes only the contiguous span from lowest to highest active plane, following the inspected Dynamic Stripes mechanism. Only zero-plane mode removes holes within that span. The sign plane subtracts its term, preserving two's-complement arithmetic. Results have sufficient width for the exact N-term integer sum; no rounding, saturation or approximate multiplication enters the operator.

The main configuration is W=8,N=4, with W=4/8 and N=1/4/8 parameter verification. Tests use uniform signed, uniform nonnegative, low-range, zero-rich, all-negative-minus-one and phase-changing distributions. Three seeds are independent synthetic input draws; repeated execution of a seed is not an independent statistical observation. Protocol tests introduce producer bubbles, periodic/random receiver stalls and synchronous reset during work and output holding. The fixed traffic grid receives equal treatment for every mechanism. The 4,096-group convergence streams and per-result bit-count formula check startup/drain accounting.

Public replay uses all 360 held-out images from the documented re-split of sklearn digits. The seed-7 dense and structured-pruned checkpoints are reused, with channelwise symmetric W=4/8 weight quantization and nonnegative pixels mapped to 0 through `2^(W-1)-1`. No labels or validation accuracy tune the scheduler, lane grouping, tool constraints or checkpoint choice. Both validation and test input-density sensitivity are recorded; their labels do not influence decisions. The original data was already a test subset of the full UCI writer-independent benchmark, so these small results do not estimate modern-model generalization.

Each image/class executes sixteen four-feature RTL blocks. All block outputs match an independently computed signed-integer dot. Summed raw dot matrices match NumPy integer matrix multiplication; class scaling/bias and argmax are host operations. These accuracy checks establish arithmetic preservation for the fixed exported operator, not end-to-end integer-only inference or a quantization-accuracy advance.

Synthesis uses identical width, lanes and Yosys settings per comparison. Generic mapped cells and logical Xilinx UltraScale+ cells are retained. Both DSP-disabled and DSP-enabled main mappings are measured; choosing only LUT multiplication would bias an FPGA comparison. Every retained type is reported, including carry and control cells. No clock or part placement is performed, and logical `xcup` cells are not native placed K26 site counts.

## Measured results

Measured W=8,N=4 continuous public replay, 360 images, ten classes, 57,600 block transactions per model/mechanism. Dense and sparse checkpoints have identical input scheduling and cycle averages. Counts below are DSP-allowed logical Xilinx mapping outputs.

| Mechanism | Measured cycles/group | LUT1–LUT6 | FF | DSP48E2 |
| --- | ---: | ---: | ---: | ---: |
| Parallel multipliers | 1.000000 | 57 | 28 | 4 |
| Fixed serial | 9.000000 | 161 | 128 | 0 |
| Leading-only bitmap | 7.476042 | 214 | 128 | 0 |
| Contiguous bitmap span | 6.967882 | 218 | 128 | 0 |
| Counter span (prior mechanism) | 6.967882 | 193 | 126 | 0 |
| Zero-plane bitmap | 6.524479 | 200 | 128 | 0 |

The zero-plane candidate reduces cycles by **6.3635%** relative to the counter span and gives **1.067960x** throughput at an assumed equal clock (image bootstrap 95% interval **1.064742–1.071269x**). It uses **200 versus 193 LUTs** (+3.63%) and **128 versus 126 FFs** (+1.59%), with zero DSPs in both. The derived equal-clock throughput per LUT improves by **3.0581%**; this is a derived ratio of measured cycles and mapped LUT counts, not routed implementation performance.

The fixed-width comparison is **1.379420x** throughput (+37.94%), much larger than the additional 6.80% over the applicable prior mechanism. Parallel multiplication is **6.524479x faster** in group cycles than the candidate, using **57 LUTs, 28 FFs and four DSPs**. With DSPs disabled, the clean parallel baseline uses **727 LUTs, 28 FFs and zero DSPs**. This makes DSP availability a fundamental constraint, not an optional presentation detail.

W=4,N=4 public replay measures **3.331944 versus 3.426736 cycles/group** (zero planes versus counter span), only **1.028449x** throughput at equal clock. Its mapped counts are **108 versus 107 LUTs**, and **76 FFs** in both. All-minus-one groups at W=8 take **9 cycles/group** for every serial scheduler, so there is no arithmetic-cycle gain.

The selected seed-7 dense checkpoint yields **348/360 (96.667%)** correct at W=4 and **343/360 (95.278%)** at W=8; the pruned checkpoint yields **346/360 (96.111%)** and **343/360 (95.278%)**. Every mechanism produces identical raw dot matrices and predictions at each precision. The accidental higher W=4 accuracy on this small fixed split is not evidence that lower precision generally improves accuracy.

Final validation comprises **768 RTL/netlist runs**, **1,783,050 checked outputs**, **8,649,407 checked cycles**, **246 reset-canceled jobs**, **30 synthesized configurations**, **zero inferred/mapped latches**, **12 generic-netlist replay runs**, **eight Python tests**, **six bounded SAT checks**, and **two detected mutations**. Recorded coverage includes **85 active-work resets**, **161 pending-output resets**, **98,441 stalled-output cycles**, **126,726 zero groups** and **159,408 groups containing negative activations**. Final comparison records replace the superseded parallel measurements; those deterministic exploratory runs are not counted as independent observations.

Actual synthesis stdout is partial at ABC/ABC9 even though all requested netlists are emitted and commands return zero. All thirty products are independently reloaded, structurally checked and cross-checked against printed resource statistics, with retained readback logs. The partial synthesis transcripts are retained and explicitly identified.


## Causal interpretation and negative results

The benefit beyond counter-based span trimming is **modest**: interior holes save 0.443403 cycles per group on the W=8 public input, but add seven LUTs and two FFs in the matched mapping. The candidate is useful when DSPs are constrained and the input union retains holes. It does not beat the DSP-enabled parallel endpoint in throughput or LUT/FF cost. No claim of a system-level efficiency improvement is supported by these endpoint measurements.

The zero-plane result is caused by the shared OR bitmap's population count, not by per-element activation sparsity alone. One lane can fill a bit missing in all others. Larger groups reduce the probability of a globally empty plane; the grouping sensitivity explicitly exposes this boundary. Negative two's-complement values can fill high bits even when numerical magnitude is small. For groups of minus one, all serial mechanisms visit all W planes and zero-plane skipping has no cycle benefit.

The counter and bitmap span modes have identical cycle behavior by construction and measurement, but different synthesized control costs. This separates a scheduling benefit from avoidable baseline implementation overhead. A cycle saving can be overwhelmed by a lower routed clock or a resource bottleneck. All speedups here assume equal clock; they must not be read as measured wall-clock speedups. A finite receiver-ready rate can also hide arithmetic acceleration, as recorded in stress results.

The parallel baseline emits one group per ready cycle and remains the highest throughput endpoint under continuous traffic. Bit-serial execution trades that throughput for a multiplier-free implementation; it is not automatically preferable on a DSP-rich device. The DSP-enabled comparison is material to the intended KV260 deployment. Additional input queues, independent-lane scheduling, weight-zero gating, data reuse, DMA, memory bandwidth and full layer accumulation are not modeled by this endpoint.

## Verification and evidence-to-claim mapping

| Claim | Executed evidence | Practical limit |
| --- | --- | --- |
| Exact signed arithmetic and tags on tested workloads | Independent scoreboards, exhaustive W=4 single-lane RTL pairs, all public block outputs, tests and simulation logs | Finite test space; host rescale/bias is outside RTL |
| Internal holes produce the measured cycle reduction | Every continuous result latency and total admission interval checked against independent bit count/span; effects.json | Equal clock and local endpoint only |
| Control implementation changes area | Bitmap span versus separate counter span in resources.json and retained netlists | Logical mapping, no routed timing or physical area |
| Reset/backpressure behavior exercised | Recorded active/output resets, hold assertions, generic-netlist replays, detected mutations | Coverage counters are not complete production coverage |
| Small-parameter numeric correctness checked beyond sampled vectors | Six W=3,N=1,12-step SAT checks with arbitrary input/ready/reset | Bounded and reduced parameterization, no unbounded liveness |
| Accuracy is unchanged by the selected exact mechanism | Every replayed dot matrix and prediction agrees across modes | Fixed seed-7 models and small data; no new training claim |

The original random-ready mutation test did not expose a deliberately broken output overwrite path. Directed one-in-eight readiness now detects it; both the escape and correction are retained. This establishes that improving verification stimulus was necessary, rather than presenting a passing random test as sufficient. Tool preparation and development revisions are in DEVELOPMENT.md; no outcome-based filtering removes poor-performing workloads.

The 95% bootstrap intervals resample 360 held-out images with seed 991 and 4,000 resamples, pairing mechanisms on each image. Ten repeated class dots of one image are not treated as ten independent samples. Intervals describe workload sampling under a fixed model/split, not training uncertainty or physical timing. Writer correlation and the convenience subset can violate independent-image assumptions. N=1/8 public grouping results are input-derived analytical predictions, whereas N=4 is independently reproduced by actual RTL.

## Related work and novelty

Primary full texts for Pragmatic and Dynamic Stripes were inspected; RELATED_WORK.md gives exact links and mechanism differences. Zero-bit skipping and dynamic precision are established ideas. This artifact supplies a shared-bitmap implementation, an efficient counter-span comparator, explicit signed behavior, reproducible public-input grouping boundaries, and executed verification/mapping evidence. It does not establish a previously unknown algorithm or reproduce the complete prior accelerators. Recent literature coverage is incomplete.

## Thesis and submission extension

A defensible thesis direction would learn activation quantizers or group assignments using an expected shared-plane service cost, then test whether that objective produces an accuracy/latency/resource Pareto improvement over uniform quantization, QAT and applicable bit-sparse accelerators. The present exact operator and tests are a hardware measurement foundation, not that learning contribution.

Before a NeurIPS submission, a precise learning-method contribution, strong modern quantization/sparsity baselines, multiple realistic models and datasets, independent training seeds, held-out calibration/tuning separation and statistical accuracy analysis are necessary. Before an architecture submission, a complete memory/dataflow architecture and realistic layer traces, optimized prior-art implementations, matched throughput/resource budgets and measured or constrained implementation timing are necessary. The daily artifact cadence cannot substitute for those evidence requirements.

For the user's KV260/HiPerGator path, next work requires an actually connected execution environment, compatible Vivado target/clock constraints, synthesis and implementation on K26, routed setup/hold closure, driver/DMA integration, board throughput measurements and workload training jobs under the user's allocation. ASIC verification work requires an executable real UVM environment on a verified compatible simulator plus coverage closure, CDC/RDC and formal/equivalence signoff. Those stages remain unexecuted here.
