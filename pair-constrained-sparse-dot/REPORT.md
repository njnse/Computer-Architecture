# Pair-constrained sparse dot product: measured report

## Contribution and hypothesis

This completed experimental artifact links a restricted sparse integer RTL kernel to an openly obtainable classification workload. It measures whether restricting six 2:4 patterns to four pair-balanced patterns reduces implementation cost, and measures the representational cost under equal-budget fixed-mask recovery. It includes index-based 2:4, a compact six-pattern code baseline, dense hardware, and a selector-free fixed-pattern ablation. These are mechanisms implemented here; no original invention or publication-ready novelty is claimed.

The pre-implementation protocol is [SPEC.md](SPEC.md). All configurations, including regressions, are retained. The tested hypothesis is conditional on precision, mapping, and workload; a sparse MAC count is not a system speedup model.

## Method

Use the same one-entry elastic pipeline, activation/result widths, synchronous reset, and traffic in every RTL variant. Sparse modes have two multipliers, while dense has four; this is a cost comparison at equal group throughput, not equal multiplier count across dense and sparse. Index, code, pair, and fixed share two arithmetic units. WIDTH=2/4/6/8/12 tests expose precision sensitivity. The implementation is SystemVerilog executed in Icarus 12.0. Yosys 0.69 revision 9f75ca1f9 performs generic synthesis and actual UltraScale+ family LUT/DSP technology mapping. This is not an exact K26 device implementation or placed timing analysis.

Digits contains 1,797 public 8×8 images. A fixed stratified split uses 1,077 training, 360 validation, and 360 test samples. Train a small linear softmax classifier from three initializations, choose checkpoints by validation cross-entropy, freeze masks from the dense checkpoint, and compare immediate pruning with matched 300-epoch recovery. Per-output weight scales and nonnegative signed-range activation quantization use 4/8 bits. Host bias and dequantization remain floating point. See raw training curves and stored weights; this is not a CNN, QAT, SR-STE, or a modern large-model benchmark.

All seed-7 recovered test-image/class/group operations were replayed through RTL in every format. The emitted group sums reconstruct exactly the independently computed integer matrix products and predictions. Thus the workload and kernel arithmetic are connected; full-layer accumulation, bias/scaling, and software orchestration are not implemented in RTL.

## Measured resources

| Width | Mode | LUT, DSP disabled | FF | Carry cells | LUT, DSP enabled | DSP cells |
| --- | --- | --- | --- | --- | --- | --- |
| 4 | dense | 153 | 11 | 9 | 153 | 0 |
| 4 | index | 97 | 11 | 3 | 97 | 0 |
| 4 | code | 99 | 11 | 3 | 99 | 0 |
| 4 | pair | 89 | 10 | 3 | 89 | 0 |
| 4 | fixed | 68 | 10 | 3 | 68 | 0 |
| 8 | dense | 681 | 19 | 15 | 52 | 4 |
| 8 | index | 388 | 19 | 5 | 53 | 2 |
| 8 | code | 402 | 19 | 5 | 57 | 2 |
| 8 | pair | 345 | 18 | 5 | 35 | 2 |
| 8 | fixed | 325 | 18 | 5 | 19 | 2 |

Complete cell-type breakdowns for all 85 synthesis configurations are in [results/resources.json](results/resources.json). Mapping excludes IO pads/clock buffers equally and runs latch/driver checks. Resource counts are technology-mapped synthesis output, not Vivado utilization, placed resource occupancy, Fmax, or power.

The requested mapping family is `xcup`. Emitted carry cell types are recorded exactly (the current Yosys flow emits CARRY4 rather than native K26 physical carry-site counts); DSP-enabled cases may emit DSP48E2. Treat these as logical primitive counts from this tool flow, not a device-ready K26 netlist or final physical site occupancy. Vivado may transform/pack logic differently.

At 4 bits, pair changes mapped LUT count by -8.25% against index and -10.10% against code. The seed-7 recovered accuracy delta versus unrestricted sparsity is -3.33 percentage points (paired image-bootstrap interval -5.56 to -1.11).
The compliant-stream CHECK_META=0 ablation uses 86 index LUTs and 92 code LUTs versus 89 pair LUTs. This isolates some validator cost; invalid-input behavior no longer matches the default specification.
With index metadata validation removed, pair changes LUT count by +3.49%. The pair area advantage reverses: unrestricted selection is smaller, so the default checked-baseline gain cannot be attributed to simpler selection alone.
At 8 bits, pair changes mapped LUT count by -11.08% against index and -14.18% against code. The seed-7 recovered accuracy delta versus unrestricted sparsity is -1.67 percentage points (paired image-bootstrap interval -3.61 to +0.28).
The compliant-stream CHECK_META=0 ablation uses 371 index LUTs and 364 code LUTs versus 345 pair LUTs. This isolates some validator cost; invalid-input behavior no longer matches the default specification.
With index metadata validation removed, pair changes LUT count by -7.01%. A reduction remains after removing index validation, but is smaller than the default checked-baseline reduction.

## Accuracy, loss, and recovery

| Precision | Mask | Immediate mean accuracy (%) | Recovered mean (%) | Recovered seed range (%) |
| --- | --- | --- | --- | --- |
| float | dense | 95.00 | 95.28 | 95.28–95.28 |
| float | index | 93.43 | 95.00 | 95.00–95.00 |
| float | pair | 90.93 | 93.33 | 93.33–93.33 |
| float | fixed | 69.81 | 86.39 | 86.39–86.39 |
| 4 | dense | 95.56 | 96.30 | 95.83–96.67 |
| 4 | index | 94.35 | 95.83 | 95.56–96.11 |
| 4 | pair | 91.48 | 93.06 | 92.78–93.61 |
| 4 | fixed | 69.81 | 87.41 | 87.22–87.78 |
| 8 | dense | 95.09 | 95.28 | 95.28–95.28 |
| 8 | index | 93.61 | 94.91 | 94.72–95.28 |
| 8 | pair | 90.93 | 93.61 | 93.61–93.61 |
| 8 | fixed | 69.91 | 86.39 | 86.39–86.39 |

Every point is a measured held-out result, not a projected accuracy. Pair conflicts in unrestricted dense-checkpoint masks are [89, 88, 89] out of 160 groups across the three initializations. These are groups selecting both weights from the same adjacent pair; pair cannot represent those masks. Immediate dropped-weight energy records expose the representational cost, while recovery changes surviving weights and biases. Seed ranges describe initialization sensitivity on the same split and training procedure; they are not independent datasets. Bootstrap intervals in [results/summary.json](results/summary.json) resample paired test images for one seed only and must not be interpreted as training-population confidence intervals.

## Cycle performance and payload

Each saturation experiment accepts 2,000 groups, has 1,999 simultaneous input/output transfers, and emits all outputs with measured one-cycle latency and no stalls. All five modes therefore have the same one-group-per-cycle initiation rate. There is no measured throughput speedup from using two rather than four multipliers. Random backpressure increases latency and source stalls for every mode; the raw per-run histograms and reset conservation counters are published.

Weight-format payload at 4 bits is dense 16, index 12, code 11, pair 10, fixed 8 bits/group; at 8 bits it is 32, 20, 19, 18, 16. Activations cost 4W bits/group for all variants. Pair removes two metadata bits versus index but only one versus compact code. These payload sizes exclude storage alignment, interfaces, headers, biases/scales, buffering, and off-chip transfer overhead, and are not measured bandwidth gains. A unified wide test port does not impose equal stored-weight format size; unused bits are optimized away.

## Validation and measurement path

The run passed 7 independent reference tests, 150 RTL/generic-netlist simulations over 1,195,920 checked cycles, and 85 synthesis configurations with no latches. Exhaustive WIDTH=2 arithmetic covers all signed inputs and compressed weights, including malformed metadata. Directed extreme values are also present in randomized signed tests. Valid/data/error stability, reset cancellation, and transfer conservation are checked independently. Five WIDTH=2 formal configurations passed ten-step bounded arithmetic/protocol assertions with arbitrary input data, metadata, stalls, and later resets; this is not an unbounded proof. Wrong-pair selection and stalled-output corruption mutations were both detected. A checked-in debug waveform demonstrates the pair kernel's mixed traffic.

Generic synthesized netlists were replayed for all widths/modes. Ten DSP-disabled Xilinx-mapped netlists at widths 4/8 were also replayed with Yosys's functional primitive models; this is not vendor timing simulation. DSP-enabled mapped netlists were not functionally simulated, so their equivalence remains an additional validation requirement. The harness is Python-generated vectors plus SystemVerilog assertions/scoreboard, **not UVM**. No validated UVM simulator/library, Vivado license/tool connection, GPU, HiPerGator session, or physical KV260 access was available here.

## Causal interpretation and negative evidence

The selector-free fixed ablation separates the arithmetic/elastic-register floor from index-selection overhead. Compact code separates index bit count from pattern flexibility; its decoder can consume resources, so fewer metadata bits need not mean lower area. DSP-enabled mapping identifies cases where multipliers dominate the comparison. Pair's same-pair restriction is stronger than unrestricted 2:4 and can drop influential coefficients even at matched selected-slot count. The immediate-versus-recovered comparisons separate mask damage from the optimizer's recovery. Quantization can erase selected slots; raw numerical nonzero counts are reported rather than assuming exactly half of coefficients survive.

This artifact does not establish that the pair constraint is a generally preferable pruning pattern. Assess the actual resource deltas alongside the accuracy table, including poorer precisions, masks, and unrecovered cases. A small linear model and a fixed split cannot support claims about CNNs, transformers, writer-independent recognition, end-to-end accelerator latency, energy, or NeurIPS-level generalization.

Pair is exactly adjacent 1:2 sparsity packed into one four-input kernel. Its constraint is established, not a new sparsity class. Both input ordering and bank size may change the tradeoff; no permutation search is performed here. Validation checkpoints frequently reach the available training budget, so the experiments establish equal-budget outcomes rather than optimization convergence.

## Verified related work and mechanism differences

Taka et al., *Systolic Sparse Tensor Slices: FPGA Building Blocks for Sparse and Dense AI Acceleration*, FPGA proceedings, [primary paper](https://arxiv.org/html/2502.03763v1), DOI 10.1145/3706628.3708867: the inspected sparse-PE section uses two-bit indices and activation multiplexing with a systolic execution schedule. This artifact borrows the relevant index-based selection concept as a standalone baseline; it does not reproduce their full systolic block or architecture-level evaluation. Pair restricts supported masks; compact code retains six masks. Their silicon/architecture results are not comparison measurements here.

Zhou et al., *Learning N:M Fine-grained Structured Sparse Neural Networks From Scratch*, ICLR, [primary paper](https://arxiv.org/abs/2102.04010), studies N:M training and SR-STE. Our magnitude-derived fixed masks plus recovery are deliberately simpler and cannot claim parity with SR-STE. Mishra et al., *Accelerating Sparse Deep Neural Networks*, [primary paper](https://arxiv.org/abs/2104.08378), describes structured GPU acceleration. GPU sparse-tensor hardware is a relevant concept, not an FPGA baseline run here. The paper abstracts and the SST mechanism section were inspected; a comprehensive novelty survey and reproduction of state-of-the-art training are unfinished.

Cao et al., *Efficient and Effective Sparse LSTM on FPGA with Bank-Balanced Sparsity*, [author-hosted primary paper](https://www.microsoft.com/en-us/research/uploads/prod/2019/05/FPGA2019_final.pdf), DOI 10.1145/3289602.3293898, partitions rows into equal-sized banks and prunes within banks; its mechanism section was inspected. Pair is the tiny-bank case conceptually, but this project does not reproduce their banked scratchpad, sparse matrix format, LSTM, or full accelerator. Restrictions for regular execution are established prior art. The measured selector/payload costs here motivate larger bank-size and data-movement studies rather than an unverified novelty claim.

Alpaydin and Kaynak, *Optical Recognition of Handwritten Digits*, [UCI source](https://archive.ics.uci.edu/dataset/80/optical+recognition+of+handwritten+digits), DOI 10.24432/C50P49, is CC BY 4.0. [scikit-learn loader documentation](https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_digits.html) identifies the 1,797-image test subset. We train/validate/test anew within that subset and disclose that limitation. No raw dataset or third-party traces are redistributed; derived trained weights and predictions are provided.

## Evidence-to-claim mapping

| Claim | Direct evidence | Boundary |
| --- | --- | --- |
| Exact implemented integer kernels | exhaustive/random RTL, generic and DSP-disabled mapped replay, bounded formal logs | WIDTH=2 formal depth 10; no vendor timing or DSP-enabled simulation |
| One group per cycle under ready receiver | saturation counters and one-cycle histograms in simulation.csv | no measured MHz or full-system rate |
| Precision-dependent selector resource cost | actual synthesis cell types, summary.json, tradeoffs.svg | family mapping, no exact-device placement/timing |
| Restriction/pruning/quantization can change predictions | classification.csv, masks, predictions, training curves | linear digits classifier and one resplit subset |
| ML-to-kernel arithmetic consistency | replay.json output hashes and exact matrix-product comparisons | host accumulation/scales/bias remain outside RTL |

## Thesis and submission extension

Build a fixed-point accumulated layer with explicit scales/bias and a data-movement interface; run formal proofs and production-grade constrained-random UVM in a compatible simulator. Use Vivado on the user's Windows installation for exact K26 synthesis, routing and clock constraints, then deploy to one KV260 with transfer-inclusive latency and measured board power. Quantify storage packing and metadata/buffering costs at layer/array scale before claiming system benefits. Use HiPerGator for matched QAT and sparse-training baselines on multiple CNN/transformer workloads, separated tuning/test data, multi-seed uncertainty, and additional hold-out architectures. Compare pair restrictions to learned permutations and other balanced patterns with exact hardware costs. These are substantial remaining research tasks; this completed kernel/workload artifact is evidence infrastructure, not a completed master's thesis or conference-ready paper.

The implemented skills include signed parameterized RTL, compressed formats, elastic protocols, independent scoreboards, exhaustive arithmetic tests, fault injection, bounded formal checking, post-synthesis generic simulation, FPGA family mapping, measured cycle/resource analysis, and traceable quantized workload integration.
