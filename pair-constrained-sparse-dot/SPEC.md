# Pair-constrained sparse dot product

## Frozen experimental question

Does constraining a 2:4 weight group to one selected value in each adjacent pair reduce selector resources relative to unrestricted index-based and compact-code 2:4 hardware, while retaining useful held-out classification accuracy? A counterexample is acceptable: modern mapping may absorb selection logic, or the pattern restriction may destroy useful weights. No novelty or submission-readiness claim is made.

Pair is exactly two adjacent 1:2 groups packed into one four-input kernel. It is a known N:M constraint, not a new sparsity class. The contribution is the measured matched-kernel encoding/selector/accuracy comparison and executable cross-validation.

The kernel consumes four signed WIDTH-bit activations. It produces their exact integer weighted sum with `2*WIDTH+2` output bits. A single elastic result register gives one-cycle latency with an always-ready consumer and a maximum initiation rate of one group per cycle. All variants have the same activation width, result width, handshake, reset, and pipeline depth.

## Formats and mechanisms

`MODE` is an elaboration parameter, not a runtime selector. Inputs are `s_x[4*WIDTH-1:0]`, `s_w[4*WIDTH-1:0]`, `s_meta[3:0]`, and `s_valid`; outputs are `s_ready`, `m_data`, `m_error`, and `m_valid`, with `m_ready` from the consumer. Element zero occupies the least significant bits.

| MODE | Name | Weight data used | Metadata used | Supported legal patterns |
| --- | --- | --- | --- | --- |
| 0 | dense | four weights | none | unrestricted |
| 1 | index | two compressed weights | two 2-bit indices, first in bits 1:0 | all six distinct sorted pairs |
| 2 | code | two compressed weights | bits 2:0 encode (0,1),(0,2),(0,3),(1,2),(1,3),(2,3) | all six distinct pairs |
| 3 | pair | two compressed weights | bit 0 selects 0/1, bit 1 selects 2/3 | (0,2),(0,3),(1,2),(1,3) |
| 4 | fixed | two compressed weights | none | (0,2) only; selector-free ablation |

Unused input bits have no effect and may be optimized away during synthesis. Noncanonical index metadata (first index >= second) and code values 6/7 return zero with `m_error=1`; errors are normal buffered transactions. Other modes always return `m_error=0`. The compressed format may retain zero-valued weights: exactly two *slots* are selected, but quantization may make fewer than two values nonzero. This is not a guarantee of exactly 50% numerical nonzeros.

`s_ready = !rst && (!occupied || m_ready)`; `m_valid = !rst && occupied`. Synchronous active-high reset masks both channels immediately and clears occupied at the rising edge, discarding any buffered result. Output data/error are meaningful only when `m_valid` is high. A source must hold valid/data/metadata until accepted. A stalled valid output must remain valid and hold both data and error unless reset is asserted. Reset can be asserted at any cycle. WIDTH >= 2 is supported.

## Evaluation fixed before result inspection

* Logic synthesis widths: 2, 4, 6, 8, 12; all five modes. Generic Boolean synthesis plus Xilinx UltraScale+ family mapping with DSPs disabled and enabled. No timing or power claims; Vivado and physical boards are inaccessible in this execution environment.
* Additional selector-cost ablation: synthesize index/code with `CHECK_META=0` and DSPs disabled. This removes malformed-metadata checking and changes behavior on invalid inputs; it is only a resource ablation for compliant streams, not the default tested interface. Use it to avoid attributing validator cost to selection alone.
* Public workload: scikit-learn's 1,797-image `load_digits` copy of UCI optical digits. A seeded, stratified 60/20/20 split is fixed across all variants. This is a newly split copy of the original UCI test subset, **not** the official writer-independent training/test benchmark. Preserve sample indices and data hashes. Raw images are not checked in.
* Model: a 64-input, 10-class linear softmax classifier, trained with explicit NumPy full-batch gradients. Three initialization seeds: 7, 31, 97. Dense training uses 600 epochs, learning rate 0.5, L2 coefficient 0.0001. Select the lowest validation cross-entropy checkpoint every ten epochs. Do not tune on held-out test data.
* Mask policies: dense; unrestricted top-2 magnitude per group; top-1 magnitude in each adjacent pair; fixed (0,2) ablation. Construct masks only from the dense training checkpoint. Compare immediate pruning and equal-budget 300-epoch fixed-mask recovery with the same optimizer/checkpoint rule. Dense also gets the recovery budget. This is fixed-mask recovery, not SR-STE, QAT, or a state-of-the-art pruning trainer.
* Quantization: signed widths 4 and 8, qmax = 2^(WIDTH-1)-1. Activations are nonnegative integer pixels rounded after multiplying qmax/16; weights use per-output maximum absolute scale; bias remains floating point in the host. The RTL implements group products and sums, not host rescaling, full-layer accumulation, or softmax. Evaluate every combination and publish regressions.
* Held-out workload replay: all test images, outputs, and 16 groups for seed 7 after recovery. Replay dense and all sparse formats at widths 4/8. Full index/code use the same unrestricted mask; pair and fixed use their respective masks. Compare RTL group results and reconstructed host predictions to independently computed matrix multiplication.
* Verification: exhaustive WIDTH=2 arithmetic; randomized signed extremes, all metadata, long stalls, source gaps, active resets, and drain; generic synthesized netlist replay; bounded formal checks; deliberate arithmetic/protocol mutations. Record transfer conservation, coverage, seeds, and actual tool commands.
* Post-integration validation extension: also replay DSP-disabled mapped netlists at widths 4/8 with Yosys functional primitive models. This strengthens implementation validation without changing policies, datasets, or reported experimental selection. DSP-enabled primitive simulation remains unavailable.
* Uncertainty: summarize initialization-seed ranges. Paired bootstrap intervals resample test images for seed-7 prediction differences; these measure sampling variability on this fixed split, not independent training replicas or a population/generalization guarantee. Deterministic reruns are not independent observations.

## Cost boundary

Count weight payload and metadata: dense 4W; index 2W+4; code 2W+3; pair 2W+2; fixed 2W bits per group. Activation payload is 4W for every mode. These are format sizes, not observed system bandwidth. All modes sustain one group per cycle under the same always-ready interface; halving multipliers does not establish a twofold speedup. Account for output FFs, control logic, error detection, and mapped LUT/carry/DSP cells. Ignore no off-chip memory or packing overhead in claimed system performance: those are unmeasured limitations.
