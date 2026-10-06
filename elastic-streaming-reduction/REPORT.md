# Elastic Reduction: Pipeline Placement and FPGA Mapping

## Research question and scope

How does inserting an elastic register between pairwise sums change cycle latency, sustained throughput, and mapped resources for an exact four-operand reduction?

The hypothesis is that both variants retain one-transfer-per-cycle capability and correct backpressure behavior, while splitting the arithmetic changes the mapped resource mix. A shorter arithmetic stage does not by itself prove a higher physical clock frequency.

This is a completed RTL/verification/synthesis experiment and a hardware-career portfolio artifact. It does not propose a novel reduction algorithm or claim conference readiness.

## Matched designs

The baseline is a balanced one-stage sum, not a deliberately serial or non-pipelined strawman. Both designs use identical unsigned widths, exact WIDTH+2 results, ready/valid semantics, active-high synchronous valid-state reset, and independently stalled storage.

The two-stage version registers two WIDTH+1 pair sums before the final addition. It has two transaction slots instead of one, so storage capacity and latency differ intentionally. Comparisons do not claim equal register budgets.

The tested widths are 1, 8, 16, and 32. Signed arithmetic, variable packet lengths, metadata, clock-domain crossings and full AXI compliance are outside the specification.

## Verification method

Python generates 512 operand tuples per width, including zero, all-maximum, carry-heavy and unit-valued directed cases, followed by deterministic random vectors. Its arbitrary-precision sum produces the reference answers independently of RTL's widened pairwise implementation.

The SystemVerilog harness drives valid/data according to the handshake contract, monitors accepted/retired transfers, and compares every retired result against a queue of expected answers. It records input/output stalls, simultaneous transfers, cycle latency, output gaps and reset cancellation. Output and source stability are checked under backpressure.

Three traffic scenarios are executed with seeds 7, 31, and 101: saturated traffic, random source gaps with sink backpressure, and random traffic with long sink stalls and reset while transactions remain pending.

The source generator is closed-loop: it preserves an offered vector until acceptance. Different pipeline capacities can therefore change source valid timing even with the same cycle-based random readiness and vector order. Random-traffic cycle differences are not a claim about identical open-loop traces.

After generic synthesis, the same harness is run on the generated netlist for every width/pipeline and all three scenarios at seed 31. Complete metrics match the corresponding RTL run, not just the final output count.

An intentional one-bit output corruption is required to fail with a scoreboard mismatch. This checks that the reference path detects a broken datapath. One representative waveform is retained for reset/backpressure debugging.

No UVM library or UVM-capable simulation was executed. The harness demonstrates driver/monitor/scoreboard architecture without being labeled UVM. The counters are observed scenario coverage, not code coverage or verification closure.

## Executed results

The final matrix contains 72 RTL simulations and 24 generic-netlist simulations. Across these runs, 49,152 input transactions were accepted, 49,104 results checked, and 48 pending transactions intentionally canceled by reset. Conservation holds in every run.

Both designs retire 512 saturated transactions with output gaps of exactly one cycle. Accepted-input-to-retirement latency is exactly one cycle for PIPE=1 and two cycles for PIPE=2. Including fill/drain, the saturated cases take 513 and 514 active test cycles respectively.

Random and reset scenarios exercise source stalls, sink stalls, and reset with nonempty storage. Their individual latency/cycle measurements are in the CSV. Three pseudo-random seeds are correctness stress cases, not independent samples supporting a population-level performance confidence interval.

## Synthesis and resources

The executed toolchain is Icarus 12.0 and YoWASP-Yosys 0.69, Yosys revision 9f75ca1f9. Dependency versions are pinned in the bootstrap files.

Each tested RTL configuration runs generic synthesis and iCE40 technology mapping with identical tool settings apart from width and pipeline depth. Resource counts come from actual synthesis statistics. No inferred latch type is present in the checked cell summaries. The generic netlist, rather than the iCE40 primitive netlist, is the one simulated.

| Operand width | Pipeline stages | LUT4 | Flip-flops | Carry primitives |
| --- | ---: | ---: | ---: | ---: |
| 1 | 1 | 8 | 4 | 2 |
| 1 | 2 | 13 | 9 | 2 |
| 8 | 1 | 43 | 11 | 8 |
| 8 | 2 | 31 | 30 | 25 |
| 16 | 1 | 83 | 19 | 16 |
| 16 | 2 | 55 | 54 | 49 |
| 32 | 1 | 163 | 35 | 32 |
| 32 | 2 | 103 | 102 | 97 |

Flip-flops aggregate the mapped SB_DFF-family cells, including valid-state registers. These are mapping-stage primitive counts, not a placed device's occupied logic-cell total. LUT, flip-flop and carry resources may share physical logic cells and must not simply be summed into a physical area estimate.

At width 16, splitting the sum reduces LUT4 count from 83 to 55, but increases flip-flops from 19 to 54 and carries from 16 to 49. At width 1 the split instead increases LUT4 count. A blanket statement that additional pipelining saves area is therefore unsupported.

The changed resource mix is consistent with different arithmetic optimization opportunities across register boundaries. Establishing the specific optimizer transformation would require netlist-level attribution or pass ablations; this artifact does not treat that explanation as proven.

## Bounded formal checks

At WIDTH=4, both pipeline variants pass a 16-step SAT check of occupancy bounds, no valid output with zero pending count, reset handshake masking, and stable valid/data during output backpressure.

The model starts with zero-initialized state and reset asserted at the first step; inputs afterwards are unconstrained. A separate four-step SAT query finds a full, stalled state for each variant, demonstrating that relevant backpressure states are reachable.

These are bounded safety checks, not unbounded induction, arithmetic equivalence, ordering proofs for all time, or complete protocol verification. Arithmetic and ordering are checked by executed scoreboards over the stated test matrix.

The current Yosys assertion representation required async2sync and chformal lowering before its SAT importer could consume edge-triggered checks. The logged commands include that conversion; failed setup attempts were resolved before recording successful proofs.

## Evidence-to-claim map

| Claim | Executed evidence | Limit |
| --- | --- | --- |
| Exact arithmetic and order on tested vectors | Independent Python answers, queue scoreboard, overflow cases | Not exhaustive over all operand tuples |
| Correct handling of stalls and reset cancellation | Runtime stability assertions, conservation, observed coverage | No UVM or code-coverage closure |
| Generic synthesis preserves tested behavior | 24 netlist simulations with matching RTL metrics | iCE40 primitive netlist is not simulated |
| Storage invariants survive arbitrary bounded inputs | Two SAT configurations plus reachable stalled states | Bound 16, width 4, no induction |
| Both variants sustain one beat per cycle | Saturated output-gap measurements | No physical clock-frequency result |
| Pipeline placement changes FPGA resource mix | Eight matched iCE40 mappings | No placed-area or power estimate |

## Limits, related work, and next steps

The combinational ready path is not registered. Long chains may need skid buffers or credit-based control to avoid a timing bottleneck. Place-and-route with an explicit device, pinout and clock constraint is required before Fmax or timing-closure claims. There is no FPGA-board execution or physical power measurement.

[Theory of Latency-Insensitive Design](https://sld.cs.columbia.edu/pubs/carloni_tcad01_lip.pdf), by Luca P. Carloni, Kenneth L. McMillan and Alberto L. Sangiovanni-Vincentelli, provides an established foundation for preserving ordered computation while changing channel latency in stallable systems. This small datapath does not reproduce or extend that theory.

[Rules for Ready/Valid Handshakes](https://fpgacpu.ca/fpga/handshake.html), by Charles Eric LaForest, explains handshake and stall/reset contracts used to motivate the interface. Our elastic stage enables are a standard design pattern rather than a novelty claim.

The [Yosys iCE40 synthesis reference](https://yosyshq.readthedocs.io/projects/yosys/en/0.35/cmd/synth_ice40.html) describes target mapping and primitive resources. The actual installed tool version and local help/logs, not the older documentation version, define the executed flow.

These primary technical sources were opened and checked. The literature survey is focused rather than exhaustive.

A thesis-scale extension could study adaptive elastic buffering and pipeline placement across a realistic reduction/aggregation accelerator, using application-derived workloads, fixed resource budgets, registered-ready alternatives and constrained physical implementation. To support an architecture submission, add strong existing accelerator baselines, end-to-end workloads, timing/power evidence and a clearly distinct mechanism.

For hardware careers, this artifact demonstrates parameterized RTL, correct arithmetic widening, flow control, randomized verification, reference scoreboards, mutation testing, bounded formal checks, synthesis scripts and honest cycle/resource analysis. Production work still requires deeper protocol verification, UVM on a compatible simulator where appropriate, timing closure, CDC review if clocks multiply, and board-level validation.
