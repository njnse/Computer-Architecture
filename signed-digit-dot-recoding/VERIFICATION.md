# Executed verification method

## Independent arithmetic and training checks

Direct Python integer dot products and an SV multiply/add scoreboard are independent of the DUT's shift/add control. Python magnitude decomposition uses `abs` and sign-adjusted integer weights. Booth cost/arithmetic uses `d_j = bit(2j-1) + bit(2j) - 2*bit(2j+1)`, independently of the RTL's case table. Eleven unit tests cover exhaustive W3/N2 tuples, all signed values across odd/even widths 2..9, signed random groups, min-by-min multiplication, cancellation, zero weights, and positive no-gain cases. Training gradients are compared with independent central finite differences for both Tanh and ReLU.

## RTL protocol and functional checks

The driver holds input through a stall. Accepted transactions are queued with expected sum, tag and acceptance cycle. Every emitted output is checked for value, tag and order. Stalled output validity/data/tag must remain unchanged. Reset cancels the expected queue, with `emitted + canceled == accepted count` required at drain. Tags wrap modulo 256. The bench samples after DUT input capture and before nonblocking updates to avoid driver/DUT races.

Coverage counts record zeros, signed operands, zero-weight lanes, stalls, reset during active work and reset with pending output. These are finite exercised cases, not complete code coverage or a percentage claim of reachable states. The testbench clock period is an arbitrary simulation clock; it does not establish a valid physical frequency.

## Predefined matrix

- W8/N4 synthetic service: magnitude limits 3/31/127, negative probabilities 0/50/100%, zero-weight probabilities 0/50%, seeds 7/31/97, 256 groups, eight mechanisms. Surviving weights are nonzero signed integers.
- Stress: W4/W8, N1/N4/N8, eight mechanisms, two readiness/bubble patterns, 512 groups, seed 4242. Reset cycles 19/47/113 and a forced sink stall expose reset/overwrite corners.
- Exhaustive RTL: all 4,096 W3/N2 operand tuples on all eight mechanisms.
- Odd-width RTL: W5/N2 directed/random streams test sign extension and non-power-of-two radix-4 digit counts.
- Startup/drain: seed 2718, 512/4,096 groups. Every no-stall emitted latency and admission interval sum must match the independently enumerated K+1 formula.
- Public replay: newly trained Tanh/ReLU MLPs, seeds 7/31/97, 360 fixed test images, W8/N4, W4/N4, W8/N8, eight mechanisms. N4 has 28,800 block outputs per run; N8 has 14,400.

Public class reductions must equal independent NumPy integer matrix multiplication, and all eight fixed-precision classifications must match. W8/N4 and W8/N8 matrices must match each other. Nonnegative ReLU TC/SM cycle costs must be identical, directly validating the no-benefit control.

## Mutation checking

Five compiled faulty variants must fail actual functional/protocol checks: treating the magnitude top plane as a negative sign plane, failing to widen recoded weights, accepting input while output is stalled, misencoding the +2 Booth digit, and failing top sign extension for an odd width. Compile errors are not counted as successful mutation detection.

## Formal and post-synthesis validation

Eight bounded Yosys SAT checks use W3/N2 and 12 steps, arbitrary signed operands, tags, reset and sink readiness, and zero initialization. Assertions cover exact output arithmetic/tag, pending-work membership, blocked input during output stall and output stability across a stall. No unbounded proof, all-width proof or unconditional liveness claim is made.

Forty-five actual synthesized designs are independently reloaded for structural checks and cell-type cross-checks. Twenty-two generic netlists are re-simulated with the same scoreboard under signed stress/reset/backpressure. All mapped and generic types are checked for inferred latches. FPGA-family netlists are not vendor timing simulated.

`results/validation.json` audits counts, model-selection history, source/runtime pins, per-run stimulus/output hashes, retained netlists, public integer results, service records and controls. Model retraining hash equality is a determinism cross-check, not extra independent seeds. No actual UVM environment, CDC closure, place-and-route timing or board execution is completed.
