# Executed verification methodology

## Measurement path

Python generates open-loop arrivals and maintains independent per-source FIFO queues. Its reference scheduler uses a rotating deque, a visit budget, and a held selection; the RTL uses two masked priority encoders, indices, and registers. The reference writes legal source vectors and expected outputs. Source vectors are feedback-dependent through accepted queue heads, while the arrival/ready process is policy independent.

Icarus samples at each rising edge before nonblocking state updates. The testbench checks every output-valid, source-index, payload, and ready mask against the independent reference. It also asserts source hold rules, output stability under backpressure, and one-hot valid grants. Every vector is checked, including warmup and reset. Independently accumulated simulation transfer, stall, per-port service, accepted-source-change, and maximum serviced-wait counts must exactly match reference counts before a record is accepted.

`simulation.csv` contains only completed simulations; each row includes a SHA256 of the generated vector file. Commands and PASS output are in `simulation.log`. The vector files are deterministically regenerated; representative input/grant behavior and waveform are retained separately. Source SHA256 values establish which executable files produced the evidence.

## Checks beyond random vectors

* Saturated closed-form schedule: expected port is `floor(t/Q) modulo N`, independently checked for N=1,3,4,8 and Q=1,2,4,8. Fixed priority must select port zero under saturation.
* Directed protocol sequence: initially only the last port requests, the receiver stalls, and lower-index requests arrive later. This checks that a stalled choice survives new higher-priority requests. It also checks a request-free interval, nonzero resumption history, and reset while blocked queues contain pending traffic.
* Parameter corners: a single source, non-power-of-two N=3, WIDTH=1 truncation, and wider payloads.
* Random/open-loop scenarios: saturated, long/random receiver stalls, dominant-source asymmetry, short bursts, underloaded arrivals, rotating dominant phases, and repeated reset while active.
* Generic post-synthesis netlists: all configurations repeat directed protocol, receiver-stall, and phase-change runs using the same scoreboard and vectors. All raw fields and vector hashes must equal their matched RTL records.
* Fault injection: one deliberate payload-bit corruption and one removal of the backpressure selection lock must both produce a scoreboard failure. Their failure logs are expected evidence, not failures of the published RTL.
* Warmup/run-length checks: Q=1 and Q=4, three traffic families, alternate warmups and 2048/4096/8192-cycle runs. These are correlated convergence diagnostics and never counted as independent uncertainty samples.

## Bounded formal checks

Yosys SAT checks N=3, WIDTH=2 for fixed priority and Q=1/Q=4. Source-hold assumptions encode legal ready/valid traffic. All sequential state initially starts at zero and the first step asserts reset. A 20-step unrolling verifies reset masking, work conservation, one-hot/request-qualified grants, payload/source agreement, and stalled-output stability. Round-robin variants additionally verify the continuously requesting source wait counter does not exceed `(N-1)*Q` other transfers. Fixed priority intentionally has no fairness assertion.

Separate four-step SAT queries establish that a valid blocked output is reachable under the assumptions. This reduces a simple vacuity risk but does not constitute complete coverage. Proofs are bounded, at reduced parameters; they are not unbounded induction or a proof for every N/WIDTH/QUOTA. Main-size fairness is checked by executed workloads, not formally proven universally.

## Coverage and limits

Functional counters record reset with pending traffic, late arrivals during a blocked output, idle cycles, single/concurrent pending sources, sink stalls, wraparound grants, and repeated-source runs. `coverage.json` preserves counts per run; `validation.json` aggregates them and checks every category was exercised. These are functional scenario counters, not line/toggle/branch coverage or UVM coverage. Directed cases run on every configuration, although N=1 naturally cannot cover multiport events.

Queue latency starts at open-loop arrival and includes earlier queued beats, competition, and receiver stalls. The “serviced wait” is the number of other accepted beats while that head request is continuously valid. It excludes receiver-only stalls. Queue p99 includes only completed requests, so starvation can make it deceptively small; unserved-port counts and maximum pending age expose censoring. Service Jain index is interpreted only in equal-demand saturated experiments, not as a fairness verdict for unequal offered loads.

This harness is not UVM. Icarus 12.0 executed the SystemVerilog subset used here; no commercial simulator or validated compatible UVM library was configured. No claim is made about production signoff, CDC/RDC, X propagation, gate delays, FPGA timing, or physical power. Generic netlist simulation is zero-delay functional checking; iCE40 primitive netlists were mapped, not separately simulated or placed.
