# Weight-qualified bit-plane dot products

## Research question and measured conclusion

Can zero-weight lane qualification improve a shared activation-bit scheduler without sacrificing exact signed arithmetic, and does that benefit survive an equally qualified contiguous-counter control and added mapping cost?

On the predefined W8/N4 pruned-checkpoint slice, qualification changes bitmap service cost from **6.524479 to 5.699873 cycles per block**, a **1.144671x equal-clock throughput ratio**. Against the stronger equally qualified counter, the candidate achieves **1.092871x**. Its logical LUT counts are **216 versus 210**, giving a **1.062513x equal-clock throughput/LUT proxy**. Gains over the unqualified counter alone (1.222463x) overstate the advantage attributable to internal-hole skipping; both schedulers benefit from qualification.

This is a completed runnable RTL experimental artifact. It is not a newly trained quantizer, a complete accelerator, a NeurIPS-ready method, a full reproduction of prior architectures, or physical FPGA performance evidence. Known weight/bit sparsity combinations are acknowledged in [related work](RELATED_WORK.md).

## Method and matched controls

The hypothesis, primary slice, and sensitivities were fixed in [SPEC.md](SPEC.md). The on-handshake union includes activation lane i only when weight i is nonzero. Arithmetic still uses all captured operands and remains bit-exact. The sign plane subtracts its shifted partial sum. Cancellation between nonzero weights is not exploited.

Six endpoint implementations use matched widths, lane counts, result widths, tags, input vectors, and ready/valid protocol: parallel, fixed serial, bitmap, qualified bitmap, separate counter span, and equally qualified counter span. Every simulated no-stall output's latency is compared with independently enumerated K+1 cost, including endpoint overhead; interval totals separately account for startup and drain.

The 33 synthesis configurations comprise W4/N4 and W8/N4 for all six mechanisms under generic and DSP-disabled xcup mapping, W8/N8 for the four dynamic schedulers under both flows, and one DSP-allowed W8/N4 parallel mapping. Identical tool versions and settings are used within each comparison. Qualification uses no additional metadata storage, but adds weight-zero detection and qualification logic; optimized LUT/FF costs are measured, not assumed free. Resources are fixed per endpoint, not fitted to test accuracy or selected by favorable outcomes. Throughput/LUT is a partial resource proxy, not matched-area silicon or replicated-system throughput.

## Workload provenance and experimental separation

Inputs are scikit-learn's UCI handwritten-digits subset, with exact pixel/label hashes, attribution and CC BY 4.0 licensing in [toolchain](TOOLCHAIN.md) and `fixtures/provenance.json`. Existing training/validation/test split sizes are 1,077/360/360. This re-splits the original UCI test subset; it is not an official writer-independent benchmark.

All six attributed source checkpoints are reused: dense and restricted-pattern/pruned models for training seeds 7, 31, and 97. No retraining or checkpoint selection occurs here. Inputs use round-to-nearest quantization from 0..16 into signed positive qmax; weights use per-class symmetric scaling from the frozen checkpoint. W8/N4, W4/N4 and W8/N8 are all actually replayed in RTL, not only analytically counted.

Each N4 replay has 57,600 block outputs (360 images, ten classes, sixteen feature blocks); each N8 replay has 28,800. Both use all 64 features. Host integer reductions are cross-checked with independent matrix multiplication. Scaling, bias and classification remain Python operations. Reported per-image service cycles sum block costs; they are not an integrated or memory-overlapped inference latency.

The synthetic grid isolates failure boundaries using nonzero surviving weights, zero probabilities 0/25/50/75/100%, unsigned/signed/all-minus-one activations, seeds 7/31/97, W8/N4 and 512 groups. Those random seeds are workload replicates, not independent hardware measurements or training seeds of a new method. Extra reset/stall tests use seed 4242; longer startup/drain checks use 2718. The test split never selects a scheduling threshold: qualification is exact zero comparison.

## Main resource and service comparison

Arithmetic means across all three W8/N4 pruned checkpoints, each with the same 360 test images:

| Mechanism | RTL cycles/block | Generic cells | Logical LUT | Logical FF | DSP-disabled mapping DSP |
| --- | ---: | ---: | ---: | ---: | ---: |
| parallel | 1.000000 | 2095 | 727 | 28 | 0 |
| fixed | 9.000000 | 566 | 163 | 128 | 0 |
| counter | 6.967882 | 704 | 195 | 126 | 0 |
| qualified_counter | 6.229225 | 782 | 210 | 126 | 0 |
| bitmap | 6.524479 | 674 | 201 | 128 | 0 |
| qualified_bitmap | 5.699873 | 732 | 216 | 128 | 0 |

The separate DSP-allowed parallel map uses **57 LUT, 28 FF and 4 DSP cells**, and still accepts one block per cycle. Parallel arithmetic is faster in cycles than the serial candidate. These DSP/LUT regimes cannot be collapsed into one fair area score; memory bandwidth and the target's DSP budget would determine the practical choice.

For the fair qualified-counter comparison, bitmap saves **8.4979% of service cycles**. The candidate/baseline clock-frequency ratio must exceed **0.915021** to retain equal-throughput advantage. This is a derived break-even condition, not a measured clock frequency. Generic/mapped logical synthesis cannot establish KV260 Fmax.

## Ablations, sensitivity and negative findings

The within-scheduler comparison isolates qualification; qualified bitmap versus qualified counter isolates internal-hole scheduling after both receive identical weight-zero information.

| W/N | Checkpoints | Q-bitmap / bitmap throughput | Q-bitmap / Q-counter throughput | Q-bitmap / bitmap throughput per LUT |
| --- | --- | ---: | ---: | ---: |
| 8/4 | dense | 1.0032x | 1.0686x | 0.9336x |
| 8/4 | index | 1.1447x | 1.0929x | 1.0652x |
| 4/4 | dense | 1.0630x | 1.0311x | 0.9983x |
| 4/4 | index | 1.1315x | 1.0344x | 1.0626x |
| 8/8 | dense | 1.0011x | 1.0230x | 0.9044x |
| 8/8 | index | 1.0670x | 1.0439x | 0.9639x |

For synthetic dense **nonzero** weights, qualification and unqualified bitmap have exactly equal service cycles in all three activation regimes. Qualification's extra logic therefore has no cycle benefit there. Logical resources and input timing must still be paid; no measured physical timing loss is assumed.

At 50% generated zero weights, bitmap qualification yields 1.2976x on unsigned values, 1.3087x on uniformly signed values, and only 1.0524x on all-minus-one values. In the latter, any surviving lane fills every bit plane; only all-zero-weight groups take the short path. At 100% zero weights, one-cycle zero output is a useful correctness/limit case, not a realistic application speedup claim. Raw sweeps and all public cases are retained, including dense or weak-benefit conditions.

Group size changes the chance that surviving lanes fill the union, while pruning pattern and activation location determine which removed lanes had unique bits. Nominal zero-weight fraction alone is not a reliable predictor of service savings. No bandwidth reduction is obtained: every endpoint still transfers the full activation and weight vectors.

## Accuracy and uncertainty

All six mechanisms produce identical integer dot matrices and classifications at each checkpoint/precision. Cross-grouping W8/N4 and W8/N8 dot matrices also match. This proves execution equivalence for the replayed inputs; it does not show that quantization or pruning improves accuracy.

| Precision | Checkpoints | Correct predictions for seeds 7 / 31 / 97 |
| --- | --- | --- |
| 4 | dense | 348/360 (96.667%) / 345/360 (95.833%) / 347/360 (96.389%) |
| 4 | index | 346/360 (96.111%) / 345/360 (95.833%) / 344/360 (95.556%) |
| 8 | dense | 343/360 (95.278%) / 343/360 (95.278%) / 343/360 (95.278%) |
| 8 | index | 343/360 (95.278%) / 341/360 (94.722%) / 341/360 (94.722%) |

The primary fair ratio's paired-image bootstrap interval is **[1.089437, 1.096127]x**, using seed 991 and 4,000 resamples. Each resampled image retains all its class blocks and all three fixed checkpoints together. Its between-checkpoint ratio range is **[1.092718, 1.092964]x**.

The bootstrap only describes image sampling conditional on these frozen checkpoints. It does not quantify the population of training seeds, writer-independent generalization, physical clock variability, or independent board replication. Writer correlation may further limit interpretation. Confidence intervals do not turn this small linear classifier into a modern CNN/Transformer benchmark.

## Executed validation

- Ten independent Python tests passed, including exhaustive W3/N2 tuples and seeded signed arithmetic.
- **484 RTL/generic-netlist runs**, **5,419,264 checked outputs**, and **27,620,254 checked cycles**; **256 canceled jobs** explicitly accounted for.
- **108 public RTL runs**, totaling **5,184,000 exact block outputs**.
- Three compiled mutations detected by functional/protocol checks: wrong sign, stalled overwrite, inverted weight qualification.
- Six W3/N2 bounded SAT checks for 12 steps with arbitrary operands, tags, reset and sink readiness. Arithmetic, pending-result membership, tag correspondence and stalled-output stability are checked; this is not unbounded/full-parameter proof.
- **33 synthesis configurations**, zero inferred latches, independent structural/statistical readback of every retained top design, and **16 generic-netlist stress replays**.

Coverage counts and exact commands are in `results/summary.json` and `commands.json`. Per-run output/stimulus hashes, actual tool-pin checks and measurement-source hashes preserve traceability. One complete candidate public block CSV and all per-image service records are checked in; the one-command run regenerates every run's CSV in `build/`. Synthesis stdout is retained as received and may be partial around ABC/ABC9; independent readback logs substantiate structural and cell-statistics checks.

## Evidence-to-claim mapping

| Claim | Executed evidence | Boundary |
| --- | --- | --- |
| Qualification preserves signed arithmetic | Python/SV independent scoreboards, exhaustive cases, public dot hashes, SAT | Finite tests and small bounded formal |
| Sparse weights reduce service cycles | Public emitted cycle CSVs, independently checked K+1, synthetic sweep | Core service cycles, not application runtime |
| Benefit also reaches the counter | Equally qualified counter ablation on identical operands | Mechanism baseline, not full Dynamic Stripes |
| Control logic has measurable cost | Actual mapped cells, retained netlists, independent readback | Logical mapping, not routed device area/Fmax |
| Prediction changes are zero | Independent integer matrix products and classification checks | Host postprocessing and small reused classifier |
| Method fails to help dense nonzero weights | All zero-probability sweeps and resource comparisons | Physical timing cost remains unknown |

## Engineering skills and research extension

The artifact demonstrates synthesizable parameterized signed RTL, variable-latency control, exact width handling, ready/valid/reset verification, independent scoreboards, mutation testing, bounded formal checks, netlist verification, reproducible synthesis and resource/service analysis. The executed harness is **not UVM**.

The next implementation gate is a K26-constrained Vivado flow plus KV260 execution under matched clocks/interfaces. Add weight-tile reuse, accumulation/requantization and AXI/DMA integration, then measure input-loading, compute and end-to-end times separately. Run an actual UVM environment on an installation proven to execute its library and features; close functional coverage and expand formal/protocol checks before production use.

A thesis contribution could investigate whether group-aware quantization/pruning objectives reduce qualified shared-plane cost across real CNN/Transformer layers, under fixed accuracy and resource/bandwidth budgets. This requires strong modern quantization baselines, validation-only tuning, independently held-out tests, new multi-seed training, an exhaustive nearby literature review, larger workloads, and actual timing/board evidence. Those prerequisites are unmet here. Potential MICRO/HPCA/ASPLOS or NeurIPS relevance is a research direction, not a submission-readiness claim.

## Reproduction and artifacts

```bash
python3 run_project.py
```

See [toolchain](TOOLCHAIN.md), [specification](SPEC.md), [verification](VERIFICATION.md), and [development record](DEVELOPMENT.md). Key artifacts: [comparison data](results/comparison.csv), [paired effects](results/effects.json), [per-image cycles](results/image_cycles.csv), [raw candidate blocks](results/application_blocks.csv), [resource summaries](results/resources.json), and [audit](results/validation.json).

![Measured cycle/resource tradeoffs](results/tradeoffs.svg)
