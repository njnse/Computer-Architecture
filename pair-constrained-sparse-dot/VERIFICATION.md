# Executed verification methodology

## Independent paths

The Python arithmetic reference expands compressed weights into a four-element vector and computes a mathematical integer dot product. RTL directly selects activations and multiplies compressed weights. The formal reference independently constructs a bitmask, expands values in ascending position order, and uses four products. Public-workload verification compares emitted RTL groups to NumPy's integer matrix multiplication and recomputes predictions. This is more than displaying matching waveforms from the same algorithm.

The protocol reference is a deque with at most one result. It handles output removal before input enqueue, supports simultaneous consume/replace, and clears on reset. The SystemVerilog harness independently counts input transfers, output transfers, canceled buffered results, and latencies; it checks their conservation and every cycle's reference handshake/result. Source stimuli hold transactions under backpressure. Random reset may invalidate a pending output, which is counted as cancellation rather than an arithmetic failure.

## Tests

* Seven unit tests use hand-computed signed extrema, all pair patterns, explicit error cases, format roundtrips, a pruning-energy counterexample, and quantization bounds/zero rows.
* WIDTH=2 exhaustive tests cover all dense input/weight vectors, all compressed weights, and all relevant metadata. Index/code enumeration includes every invalid code and unused high-bit behavior. Pair enumeration covers every supported pattern. The fixed ablation covers every input and compressed value with its single pattern.
* WIDTH=2/4/6/8/12 randomized tests use seeds 7/31/97, 1,600 transactions each, signed minimum/maximum/zero/unit values, uniformly distributed signed values, all sixteen metadata values, source gaps, sustained output stalls, and active reset positions. Each case must drain and conserve transfers.
* Saturation tests use 2,000 groups at each width/mode. Exact one-cycle latency and 1,999 simultaneous transfers provide an independent measurement of the one-group-per-cycle rate. Initial reset and final drain are included in raw cycle counts; they are not hidden as warmup effects.
* Generic synthesized netlists are run on 800-transaction seed-211 stress streams for every width/mode. DSP-disabled mapped netlists at widths 4/8 are additionally checked on seed-317 stress streams using Yosys functional models. Source and vector hashes preserve traceability. Vendor timing simulation and DSP-enabled primitive simulation are not executed.
* Five WIDTH=2 formal configurations prove arithmetic, error propagation, occupancy/readiness, reset masking, and stalled-output stability for ten bounded steps. The first step assumes reset; later resets/valid/ready/data/metadata are arbitrary. Input stability is unnecessary for these safety properties because only accepted input matters. This is not an unbounded proof or liveness claim.
* Two deliberate faulty RTL variants change pair selection and overwrite a stalled result. Both must fail the existing scoreboard; their diagnostics and return codes are recorded.
* Every held-out group for seed-7 recovered models is replayed through every RTL format at 4/8 bits: 360 images × 10 class outputs × 16 groups. Exact integer accumulated products and predictions must match the independent software path. The code format and index format share the unrestricted trained mask, allowing a direct encoding cross-check.

## Coverage and assumptions

`simulation.csv` records accepted metadata counts, signed minimum/maximum hits, negative outputs, observed errors, simultaneous transfers, stalls, reset-on-busy events, cancellation, and latency histograms. These are concrete functional counters, not vendor code/branch/toggle coverage or UVM coverage. The reset tests include multi-cycle reset, busy cancellation, and restart. Parameters include very small and wider arithmetic widths. Exact results use enough signed bits to avoid mathematical sum overflow. No approximate arithmetic is used.

Metadata checking is enabled in all correctness experiments. The `CHECK_META=0` synthesis-only ablation intentionally changes invalid-input behavior and is not presented as a separately verified production interface. Family mapped cells are checked for driver errors/latches and counted from emitted JSON, not guessed from RTL operators.

No clock-domain crossing, analog behavior, reset synchronization, physical clock timing, power, DMA transaction protocol, full neural-layer accumulation, or proprietary UVM flow is modeled. Those require additional specifications, tools, and validation. The current validation is executed non-UVM RTL/generic-netlist verification with bounded formal evidence.
