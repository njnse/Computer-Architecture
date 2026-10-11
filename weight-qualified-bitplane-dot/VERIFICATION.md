# Executed verification plan

## Independent arithmetic

Python `reference.dot` uses direct integer multiplication and addition. Its separate bit decomposition checks the two's-complement identity. Ten unit tests include all 4,096 W3/N2 operand tuples, 6,000 seeded signed random groups, zero weights, sign extrema, internal holes, monotone qualification cost, nonzero-weight cancellation, and packed lane order. The service-cost checker enumerates a set of active bit positions independently of the RTL bitmap state or counter implementation.

## Handshake scoreboard

`tb/check.sv` adapts the attributed predecessor scoreboard. The driver retains an input until acceptance. A monitor queues accepted jobs and independently recomputes a signed multiply/add oracle, comparing both the Python expected value and every actual output. Tags wrap modulo 256; ordered comparison detects wrong routing, duplication, loss, and unsolicited outputs. Reset removes pending expectations and counts canceled jobs. Every run checks `emitted + canceled == count` after draining.

Assertions implemented as executable fatal checks enforce output validity/data/tag stability under backpressure. Source bubbles, periodic one-in-eight sink readiness, random readiness, and resets during active computation and pending output are exercised. The bench samples after DUT input capture and before nonblocking updates, avoiding driver/DUT races. Timeout detects finite-test failure to drain; this is not an unconditional liveness proof with an indefinitely unready sink.

## Predefined experiment matrix

- Synthetic service sweeps: W8/N4; unsigned, uniformly signed, and all-minus-one activations; zero-weight probabilities 0, 25, 50, 75, and 100%; seeds 7, 31, and 97; 512 groups per stream. Surviving weights are sampled from nonzero signed values. Dense cases therefore isolate qualification overhead without incidental random zeros.
- Stress: W4/W8, N1/N4/N8, all six mechanisms, both long-stall and randomized traffic, seed 4242, 512 directed/random groups, fixed reset cycles 19, 47, and 113. Coverage counts zero weights, excluded nonzero activations, empty qualified groups, reduced masks, negative operands, input/output stalls, and reset state.
- Exhaustive RTL: all 4,096 W3/N2 operand tuples on all six mechanisms.
- Startup/drain checks: streams of 512 and 4,096 groups, seed 2718. Every no-stall output must have exact reference K+1 latency, and admission intervals must equal the sum over all preceding groups.
- Public RTL replay: all six existing dense/pruned checkpoints, 360 fixed test images, W8/N4, W4/N4, and W8/N8, all six mechanisms. No model or policy is tuned using these test results.

Public output blocks are reduced and compared to an independent NumPy integer matrix multiplication. Predictions after host scaling/bias must be identical across mechanisms at fixed checkpoint and precision. The class reduction and floating rescale/bias are host operations, not implemented inference RTL.

## Fault injection

Three deliberately incorrect RTL variants must fail functional/protocol checks: treating the sign plane as positive, accepting inputs while output is stalled, and inverting the zero-weight qualification predicate. Compilation failures do not count as detected functional errors; each compiled mutant must produce an appropriate scoreboard/protocol diagnostic.

## Formal and synthesis cross-check

Each of the six mechanisms is checked with Yosys SAT for 12 steps, W3/N2, arbitrary activation/weight values, tags, reset and sink readiness, and zero-initialized state. Assertions check pending-result membership, arithmetic and tag correspondence. The reference is an independent direct multiply/add expression. This is finite bounded proof, not unbounded proof, parameter-universal proof, coverage closure, or a timing analysis.

All 33 synthesized designs are checked for latches, independently reloaded, structurally checked, and their cell-type counts cross-checked. Sixteen generic netlists are also executed with the same independent stress scoreboard. Xilinx-family mapped designs receive structural/statistical checks; vendor timing simulation is not executed.

## Evidence and remaining closure

`results/simulation.json`, `application.json`, `image_cycles.csv`, `application_blocks.csv`, `formal.json`, `mutations.json`, `resources.json`, `netlist_readback.json`, and `validation.json` contain machine-generated results. `protocol.vcd` shows a compact stress window; a full reproduction regenerates per-run output CSVs in `build/`. Output/stimulus hashes identify each generated run.

UVM agents, AXI integration, CDC checks, full-size formal induction, implementation timing, board error injection, and production coverage closure remain unexecuted. Functional counters characterize the tested scenarios; they are not a percentage claim of all reachable behavior.
