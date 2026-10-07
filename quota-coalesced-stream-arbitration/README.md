# Quota-coalesced streaming arbitration

A completed, narrowly scoped hardware experiment on the tradeoff between accepted-source transitions, bounded service waiting, and implementation resources. This is synthesizable SystemVerilog with an executed non-UVM verification harness, generic netlist simulation, bounded formal checks, and actual Yosys iCE40 technology mapping. It is not a completed thesis, conference paper, placed FPGA implementation, or board benchmark.

**Question:** Can grouping up to Q independent beats from one requester reduce source transitions without reducing work-conserving throughput, and what fairness and resource costs result?

## Reproduce

On Linux x86-64 with Python 3.12, `venv`, `dpkg-deb`, and access to Debian/PyPI:

```sh
python3 run_project.py
```

This bootstraps pinned workspace-local Icarus and YoWASP Yosys, regenerates stimuli, executes every simulation and synthesis flow, runs bounded proofs and deliberate fault injections, recreates analysis artifacts, and validates their consistency. No commercial license is required. The experiment/reference code uses the standard library; the standalone figure uses Matplotlib with all dependencies pinned in [analysis-requirements.txt](analysis-requirements.txt). Missing/mismatched plotting packages are installed into a workspace-local analysis virtual environment. Tool downloads are pinned in [tools/setup.py](tools/setup.py) and [tools/requirements.txt](tools/requirements.txt).

To use already-installed tools:

```sh
IVERILOG=/path/to/iverilog IVL_BASE=/path/to/ivl \
VVP=/path/to/vvp YOSYS=/path/to/yosys \
XDG_CACHE_HOME=/writable/cache python3 run_project.py
```

The checked-in run used Icarus 12.0 and Yosys 0.69, revision `9f75ca1f9`, via the pinned YoWASP package. Native versions are optional overrides, not the toolchain used for the archived evidence. `IVL_BASE` is needed for an extracted Icarus package; omit it for a normal installation. All temporary binaries and stimulus files stay under `build/`.

## Deliverables

| Path | Purpose |
| --- | --- |
| [SPEC.md](SPEC.md) | Interface, scheduling rules, reset semantics, falsifiable hypotheses |
| [rtl/stream_arbiter.sv](rtl/stream_arbiter.sv) | Fixed-priority, masked round-robin, and quota-coalesced RTL |
| [reference.py](reference.py) | Independent deque-based scheduler and public generated traffic |
| [tb/check_vectors.sv](tb/check_vectors.sv) | Cycle scoreboard, hold assertions, independent counters |
| [formal/properties.sv](formal/properties.sv) | Safety and service-opportunity waiting properties |
| [VERIFICATION.md](VERIFICATION.md) | Executed checks and interpretation of coverage |
| [REPORT.md](REPORT.md) | Findings, causal interpretation, evidence mapping, thesis extension |
| [results/simulation.csv](results/simulation.csv) | Raw executed RTL/netlist observations and vector hashes |
| [results/resources.json](results/resources.json) | Actual generic/mapped cell statistics for all configurations |
| [results/tradeoffs.svg](results/tradeoffs.svg) | Standalone comparison figure |
| [results/paired_effects.json](results/paired_effects.json) | Matched-seed deltas and qualified variability intervals |
| [results/per_port.csv](results/per_port.csv) | Per-source latency/waiting and starvation censoring |
| [results/warmup_sensitivity.csv](results/warmup_sensitivity.csv) | Longer-run and warmup checks |
| [results/protocol.vcd](results/protocol.vcd) | Compact debug waveform with late arrivals and resets |
| [results/validation.json](results/validation.json) | Machine-generated pass counts and coverage counters |
| [results/environment.json](results/environment.json) | Versions, configurations, seeds, and source hashes |
| [results/commands.json](results/commands.json) | Executed tool argument vectors and return codes |

Full synthesis/formal logs and generic netlists are retained as deterministic gzip + base64 text archives, allowing the GitHub text API to preserve them without dropping output. Decode any archive with the standard library, for example:

```sh
python3 -c 'import base64,gzip,pathlib; p=pathlib.Path("results/synthesis.log.gz.b64"); pathlib.Path("build/synthesis.log").write_bytes(gzip.decompress(base64.b64decode(p.read_bytes())))'
```

`build/` is created by reproduction. `results/synthesis_commands.ys` and `results/formal_commands.ys` retain the actual commands with `design -reset` between configurations. The generic netlists archive is a JSON dictionary of netlist text; those exact netlists were simulated against the same vectors.

## Engineering skills

Parameterized RTL and non-power-of-two indexing, combinational priority/mux design, handshake-safe state updates, independent scoreboards, protocol assertions, functional coverage, mutation testing, bounded formal verification, post-synthesis simulation, technology mapping, and honest cycle/resource analysis. UVM was not executed: no validated UVM-capable simulator/library was available. Production UVM, timing closure, CDC checks, and board deployment remain extensions, not checked-off tasks.
