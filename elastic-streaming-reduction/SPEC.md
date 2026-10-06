# Elastic Four-Operand Reduction Specification

## Function and parameters

Every accepted input transaction contains four unsigned WIDTH-bit operands. The output is their exact sum in WIDTH+2 bits. No truncation or saturation is permitted.

PIPE supports exactly 1 or 2. The evaluated widths are 1, 8, 16, and 32. Other positive widths are not part of the validated parameter matrix.

## Interface contract

Input transfer occurs at a rising clock edge when s_valid and s_ready are both high. Output transfer occurs when m_valid and m_ready are both high. The producer holds valid and operands until acceptance. The consumer can change ready freely.

Output valid and data remain stable during backpressure. Transfers are ordered; each accepted input produces one output unless reset cancels it. The module has PIPE transaction slots.

The active-high reset synchronously clears valid state at a rising edge. Both interface handshake signals are also masked while reset is asserted. Reset cancels all pending transactions; data registers need not be cleared because they are invalid. Reset deassertion is synchronous.

## Architecture

PIPE=1 computes two widened pair sums and their final sum before one output register.

PIPE=2 registers the two pair sums, then registers the final sum. Each stage advances independently when empty or when its successor can accept data.

Readiness propagates combinationally backwards. This is a small elastic datapath, not a registered-ready skid-buffer design or complete AXI4-Stream interface. Larger chains require analysis of ready-path timing and combinational loops.

## Performance contract

With valid and ready continuously asserted, output latency from accepted-input edge to output-transfer edge is PIPE cycles, and the initiation interval is one cycle. Backpressure can increase latency.

No physical clock frequency is specified or established by this artifact. The simulation's 10 ns clock is a stimulus setting, not an FPGA timing-closure result.
