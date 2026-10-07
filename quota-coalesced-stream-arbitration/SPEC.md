# Behavioral specification and experiment contract

## Scope and hypothesis

Multiple ready/valid sources share one receiver. A beat is an independent transaction; no packet-lock, AXI ordering, IDs, outstanding responses, or multibeat atomicity is implied. The design contains no payload buffer and no pipeline register. The contribution is an executed RTL tradeoff/verification artifact for an established scheduling idea, not a claim of inventing quota arbitration.

H1: Under continuously valid sources and an always-ready receiver, both ordinary round-robin (Q=1) and quota coalescing sustain one accepted beat per clock; grouping Q beats reduces accepted-source changes to approximately 1/Q per transfer.

H2: A continuously requesting source waits for at most `(N-1)*Q` other accepted beats before its next service, assuming legal ready/valid sources. This is a bound on service opportunities, not wall-clock time: receiver backpressure can be unbounded.

H3: Coalescing requires quota/owner control state and trades longer waits for fewer source changes. Resource changes must be measured rather than assumed; source changes do not measure power, cache locality, or application speedup.

The hypotheses, workload families, quota values, and evaluation seeds were fixed before running the experiment. Q=4 is an illustrative candidate, not a tuned optimum. Q=1 ablates coalescing; Q=2 and Q=8 test quota sensitivity. No held-out seed was used to optimize the RTL.

## Interface

| Signal/parameter | Meaning |
| --- | --- |
| `N >= 1` | Number of source ports |
| `WIDTH >= 1` | Unsigned opaque payload width |
| `QUOTA >= 1` | Maximum consecutive accepted beats in a service visit |
| `FIXED` | 1 selects fixed lowest-index priority; 0 selects quota round-robin |
| `clk` | Rising-edge clock |
| `rst` | Synchronous state reset; also masks ready/valid combinationally while asserted |
| `s_valid[N-1:0]` | Source presents a beat |
| `s_data[N*WIDTH-1:0]` | Port i occupies `[i*WIDTH +: WIDTH]` |
| `s_ready[N-1:0]` | One-hot acceptance permission; transfer on valid and ready at an edge |
| `m_valid`, `m_ready` | Receiver handshake |
| `m_data`, `m_source` | Selected payload and source index; meaningful only when m_valid is high |

A source must retain valid and its payload while valid is high and ready is low, except across reset. Receivers may change ready arbitrarily. Reset invalidates source obligations and resets scheduling history; the external test queues explicitly flush their pending beats. The arbiter itself stores no payload to lose.

## Selection and state updates

1. Reset clears pointer, owner, quota remainder, and backpressure lock. No handshake occurs during reset.
2. If a selection was stalled at the preceding edge, retain that source until the receiver accepts its beat. Late arrivals cannot replace a stalled output.
3. Otherwise, fixed priority chooses the lowest valid index. Round-robin retains the owner if it is still valid and has remaining quota; otherwise two masked priority searches choose the first pending source at/after the cyclic pointer, wrapping if needed.
4. Every accepted beat moves the cyclic pointer to the index after the selected source. The first beat of a visit initializes Q-1 remaining beats; subsequent accepted beats decrement the remainder. Stall clocks never consume quota.
5. Skip absent sources immediately without arbitration bubbles. When all sources are idle, expire any partial quota while preserving the pointer. An idle interval must not restart at port zero or resurrect the old owner's quota.

The output is combinational. A ready beat can transfer at the first sampling edge after becoming valid; there is no added clocked datapath latency. Competition and receiver stalls cause queue waiting. The reverse `m_ready -> s_ready` path and the forward request/selection/payload path require timing analysis in integration.

## Matched evaluation

Core sweep: N in {1,3,4,8}, WIDTH=16, fixed priority/Q=1/Q=4/Q=8. Width sensitivity: N=4, WIDTH in {1,8,32}, Q=1/Q=4. Additional quota sensitivity: N=4, WIDTH=16, Q=2. All use identical payload widths, unbuffered interfaces, tool settings, and generated open-loop arrival/receiver sequences. Different policies may expose different queue heads, while their arrival processes remain identical.

The external source queues are traffic generators and are excluded from all synthesis resource counts. This isolates arbiter/control/mux overhead; it is not an end-to-end FIFO/interconnect area comparison. Equal interface does not mean equal cell budget: the area cost is an outcome explicitly reported.

Evaluation seeds: 11,29,47,101,211. Seed 7 is reserved for directed protocol/fault checks. Each main run uses 4096 sampled cycles, excludes the first 512 from performance reporting, and validates all cycles. Source arrivals, payload functions, reset scheduling, and receiver-ready sequences are specified in executable `reference.py`. Synthetic traffic is openly reproducible and original to this artifact; there are no downloaded application traces or external RTL licenses to redistribute.
