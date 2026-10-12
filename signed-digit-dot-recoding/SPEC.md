# Exact signed activation recoding

## Frozen question and falsifiable hypothesis

For small negative activations, exact magnitude recoding reduces shared bit-plane work relative to raw two's complement. The hypothesis is that some cycle benefit remains on genuine signed Tanh hidden-layer outputs, but the cost of magnitude conversion and widened sign-adjusted weights may erase throughput/LUT benefit. Nonnegative ReLU traces must have identical TC/SM service cycles. A radix-4 Booth mechanism is an independently implemented stronger signed-digit baseline; magnitude wins over TC do not imply a win over Booth.

The primary evaluation is W8/N4 output-layer block replay from all three newly trained Tanh MLP checkpoints. ReLU, W4/N4 and W8/N8 are predefined controls/sensitivities. All model selection/calibration uses training/validation only; no test-based representation or threshold tuning.

## Endpoint specification

Synchronous active-high reset; ready/valid input and output; N packed signed W-bit activation/weight lanes; 8-bit transaction tag. Lane zero is least significant. Exact signed output O=2W+ceil(log2(N))+1. One active job and one result slot. Source holds a stalled input. Sink backpressure retains valid/data/tag. Reset cancels active and pending outputs; remaining outputs preserve acceptance order.

W >= 2 and N >= 1; derived output/coefficient widths use their declared defaults. Narrower manual O/SW overrides are outside the contract. Executed RTL widths are 3/4/5/8, with N1/N2/N4/N8 as specified by the verification matrix; parameter-universal correctness is not claimed.

## Mechanisms and storage

- Parallel registered multiplication (MODE=0), one block/cycle.
- Fixed W-plane two's-complement serial arithmetic (MODE=1).
- TC bitmap and separate TC counter-span schedulers (MODE=3/5).
- SM bitmap and SM counter: replace each activation by its unsigned W-bit magnitude; adjust its weight sign in a **W+1-bit signed field**. This correctly represents abs(-2^(W-1)) and negation of the minimum weight. Magnitude's top plane is positive; TC's top plane subtracts.
- Booth bitmap and Booth counter: exact radix-4 modified Booth digits in {-2,-1,0,1,2}, stored as three-bit signed fields, with D=ceil(W/2). Odd widths sign-extend the top overlapping bit. Shift/add/subtract operates at output width before scaling by 2^(2j).

All dynamic schedulers exclude lanes with zero original weight. No pruning, value rounding, compression, output approximation, or changed input bandwidth is introduced by recoding. SM and Booth conversion occurs combinationally before capture; actual mapping cost is included, but physical timing is not measured. SM stores N extra weight bits; Booth stores N*3D digit bits instead of N*W activation bits. Synthesis can optimize constants/redundancy; report actual FF types/counts.

Under continuously valid/ready traffic, bitmap latency/interval is K+1, where K is the size of the qualified active-position union; counter uses its contiguous span length, with an empty union taking one cycle. Fixed takes W+1. Parallel takes one. Report cycles rather than interpreting the arbitrary testbench clock period as physical frequency.
