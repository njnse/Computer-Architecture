# Weight-qualified bit-plane scheduling

## Falsifiable hypothesis

Removing zero-weight lanes from the activation bit union reduces exact signed dot-product service cycles on sparse weights. That reduction is not automatically an implementation improvement: input qualification costs logic, and an equally qualified counter-span scheduler may offer a better throughput/resource tradeoff. Dense nonzero weights must have identical cycles with and without qualification. Signed activations with surviving negative lanes can erase the benefit.

The mechanism changes execution only; it does not prune or retrain a model. The primary public-workload comparison is W=8, N=4, all three attributed sparse checkpoints, using both qualified and unqualified bitmap/counter schedulers. W=4,N=4 and W=8,N=8 are predefined sensitivities. No policy is tuned on the test split.

## Interface and arithmetic

Synchronous active-high reset, ready/valid input and output, N packed signed W-bit activation and weight lanes, 8-bit tag. Lane zero is least significant. W >= 2. Exact output width O=2W+ceil(log2(N))+1. One active job and one output slot; ordered outputs. Reset cancels unfinished and unconsumed work. An output under backpressure retains valid, sum, and tag. Source retains its transaction until input handshake.

For qualification, union only activation lanes whose signed weight is nonzero. Stored operands are unchanged. Every omitted lane contributes zero to every plane, including the negatively weighted two's-complement sign plane. A zero union emits exact zero without serial processing. Cancellation between nonzero weights is not detected or skipped.

## Matched mechanisms

- `parallel`: registered parallel multiplication, MODE=0, qualification disabled.
- `fixed`: fixed W-plane serial arithmetic, MODE=1, qualification disabled.
- `bitmap`: internal zero-plane skipping, MODE=3, qualification disabled.
- `qualified_bitmap`: identical MODE=3 arithmetic with weight qualification.
- `counter`: separate contiguous low/high counter scheduler, MODE=5, qualification disabled.
- `qualified_counter`: the same counter scheduler with weight qualification.

All configurations use the same endpoint, operands, lane count, result width, and stimulus. Continuous no-stall intervals and latency are K+1 cycles, including one endpoint cycle: K=W for fixed, K=popcount(union) for bitmap, K=high-low+1 for counter, and K=0 for an empty dynamic union. Parallel interval/latency is one cycle.

Qualification adds N W-bit zero comparisons and activation qualification gates before union reduction; it stores no additional per-lane metadata. Actual synthesis measures the optimized logic cost. There is no compressed input protocol, bandwidth saving claim, timing/Fmax measurement, or power estimate.
