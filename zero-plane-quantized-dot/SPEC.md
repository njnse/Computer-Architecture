# Exact zero-plane quantized dot products

## Frozen question and hypothesis

A shared bit-plane scheduler can skip a plane only when every activation lane is zero in that plane. Does skipping internal zero planes improve exact signed integer dot-product service time beyond a leading-zero trimmed serial baseline, and is the benefit worth the bitmap/priority-selection area? Expect low-range positive inputs to help relative to fixed precision, but group-union density and negative two's-complement values to erase much of the benefit beyond leading-zero trimming. This is a reproducible implementation study of known bit-sparsity ideas, not a claim to invent bit skipping.

## Interface

`dot_engine` has synchronous active-high reset, `in_valid/in_ready`, packed signed W-bit activation and weight vectors with N lanes (lane zero in least significant bits), an 8-bit tag, and `out_valid/out_ready`, an exact signed `2*W+$clog2(N)+1`-bit dot product and tag. Reset cancels accepted unfinished work and pending output. A producer holds payload while stalled; the consumer may apply arbitrary backpressure. Output remains stable while stalled. No numerical truncation or approximate multiplication is allowed. Inputs are snapshotted on handshake. Output order is input order.

## Mechanisms

Mode 0 is a registered parallel multiplier/add baseline with one result per cycle when ready. Mode 1 is full-width bit serial. Mode 2 trims only the high zero planes of the OR of all lane activations, retaining internal zeros. Mode 4 is the stronger dynamic contiguous-span baseline: it trims both leading and trailing zero planes, as described in Dynamic Stripes. Mode 3 visits only set bits in the shared OR bitmap. The top two's-complement plane subtracts the weighted contribution; other planes add. An all-zero group takes no processing cycles in modes 2, 3 and 4. Serial computation uses one full-width partial sum per plane, without multipliers. This endpoint has one active job and one result slot, and no separate input queue.

## Evaluation frozen before results

Main point W=8,N=4. Parameter checks W=4/8,N=1/4/8. Measure all modes on identical input groups and traffic, including signed random, unsigned random, zero-rich, low-range, dense negative, and phase changes; seeds 7,31,97. Include source bubbles and receiver stalls; reset active and stalled output. Use every held-out image of the attributed digits checkpoint as a realistic but small application replay, W=4/8,N=4, with independent integer dot reference. No training or hardware tuning on the held-out labels. Group sensitivity is evaluated on the same 64-element inputs, and results include regressions and minimal-gain cases. RTL measured cycles are independently checked against the number of visited planes under continuous traffic. Synthesize the exact RTL with fixed tool settings; retain netlists, scripts, resource types and logs, and flag latches. Generic and logical Xilinx mapping are not place-and-route or KV260 timing evidence.

## Prior-baseline implementation strengthening

Mode 5 executes the same contiguous active span as mode 4 using offset registers and a monotonically incrementing plane counter. It has the same numerical and handshake specification, but a different control implementation. `rtl/counter_engine.sv` is separately synthesized and simulated. This addition follows primary mechanism inspection and retains mode 4 as an implementation ablation. No labels or parameter searches select its configuration.
