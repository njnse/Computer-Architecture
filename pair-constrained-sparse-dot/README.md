# Pair-constrained sparse dot product

A completed, bounded hardware/workload experiment connecting 4/8-bit quantized classification to synthesizable sparse integer RTL. It compares unrestricted 2:4 index selection, a compact six-pattern code, pair-constrained selection, dense arithmetic, and a fixed-pattern ablation. The project executes specification → RTL → verification → synthesis → cycle/resource analysis. It is not a completed thesis, modern-model benchmark, or NeurIPS/architecture-conference submission-ready paper.

**Question:** Does restricting two retained weights to one in each adjacent pair reduce selection cost, and how much predictive flexibility does that restriction remove?

## One-command reproduction

On Linux x86-64 with Python 3.12, `venv`, `dpkg-deb`, and network access to PyPI/Debian:

```sh
python3 run_project.py
```

The entry point installs missing pinned dependencies under this project, trains models, runs exhaustive and randomized RTL verification, synthesizes generic and Xilinx UltraScale+ family netlists, replays generic and DSP-disabled mapped netlists, runs bounded formal proofs and deliberate faults, replays every held-out test group, regenerates the report/figures, and checks consistency across artifacts. Dependencies are pinned in [requirements.txt](requirements.txt) and [tools/requirements.txt](tools/requirements.txt); the Icarus Debian package is SHA256-pinned in [tools/setup.py](tools/setup.py). No commercial license or GPU is required for this archived pipeline. First-run installation needs network access; subsequent runs can reuse the workspace-local tools.

Use existing tools with explicit overrides:

```sh
IVERILOG=/path/to/iverilog IVL_BASE=/path/to/ivl \
VVP=/path/to/vvp YOSYS=/path/to/yosys \
XDG_CACHE_HOME=/writable/cache python3 run_project.py
```

`IVL_BASE` is only needed for an extracted Icarus installation. `YOSYS_XILINX_SIM` can specify the matching `xilinx/cells_sim.v` library for a custom Yosys installation; the pinned installation is discovered automatically. The recorded toolchain is Icarus 12.0 and YoWASP Yosys 0.69, revision `9f75ca1f9`. Native tool overrides are supported but are not the exact archived implementation. Training forces one BLAS thread and records initialization/split seeds. Workload images come from the pinned scikit-learn package; no external trace download is needed. Reproduction creates temporary files in `build/` and regenerates `results/`.

## Evidence and source

| Path | Deliverable |
| --- | --- |
| [SPEC.md](SPEC.md) | Frozen hypothesis, interface, formats, costs, and evaluation protocol |
| [rtl/sparse_dot.sv](rtl/sparse_dot.sv) | Five synthesizable mechanisms and metadata-check ablation |
| [reference.py](reference.py) | Independent expanded-weight arithmetic and deque protocol model |
| [workload.py](workload.py) | Explicit softmax training, pruning, quantization, workload replay |
| [tb/check_vectors.sv](tb/check_vectors.sv) | Per-cycle scoreboard, hold checks, transfer/coverage/latency counters |
| [formal/properties.sv](formal/properties.sv) | Independent mask-expansion arithmetic and bounded protocol assertions |
| [VERIFICATION.md](VERIFICATION.md) | Verification scope and meaningful coverage |
| [REPORT.md](REPORT.md) | Machine-derived results, limitations, related work, thesis extension |
| [results/classification.csv](results/classification.csv) | All measured accuracy/pruning/quantization outcomes |
| [results/models.json](results/models.json) | Learned weights, masks, biases, validation-selected checkpoints |
| [results/training.csv](results/training.csv) | Training and validation loss checkpoints |
| [results/test_predictions.json](results/test_predictions.json) | Every held-out prediction and label |
| [results/workload_provenance.json](results/workload_provenance.json) | Data hashes, attribution, split indices, and seeds |
| [results/simulation.csv](results/simulation.csv) | Actual RTL/netlist cycle, coverage, and latency observations |
| [results/replay.json](results/replay.json) | Exact matrix-to-RTL replay consistency and output hashes |
| [results/resources.json](results/resources.json) | Actual generic/mapped resource summaries and cell types |
| [results/summary.json](results/summary.json) | Resource deltas, seed ranges, and paired image-bootstrap intervals |
| [results/tradeoffs.svg](results/tradeoffs.svg) | Standalone resource/accuracy/format comparison figure |
| [results/protocol.vcd](results/protocol.vcd) | Compact reproducible mixed-traffic debug waveform |
| [results/validation.json](results/validation.json) | Test/proof/mutation counts and execution boundaries |
| [results/artifact_checks.json](results/artifact_checks.json) | Independent cross-artifact acceptance checks |
| [results/environment.json](results/environment.json) | Runtime/tool versions and source hashes |
| [results/commands.json](results/commands.json) | Actual tool argument vectors and return codes |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Integration revisions and limits of the frozen protocol |

Full synthesis and formal logs and the tested generic netlists are retained as deterministic gzip/base64 text archives. Decode with Python standard library, for example:

```sh
python3 -c 'import base64,gzip,pathlib; p=pathlib.Path("results/synthesis.log.gz.b64"); pathlib.Path("build/synthesis.log").write_bytes(gzip.decompress(base64.b64decode(p.read_bytes())))'
```

`results/generic_netlists.json.gz.b64` decodes to a JSON dictionary of Verilog netlist texts. `results/synthesis_commands.ys` and `results/formal_commands.ys` retain executed tool scripts. Read [REPORT.md](REPORT.md) for measured improvements **and regressions**; a lower multiplier count is not evidence of a faster full system.

## Hardware and career scope

Design evidence includes signed arithmetic sizing, compressed sparse formats, parameterized mux/decode logic, one-entry elastic buffering, control cost, and FPGA family mapping. Verification evidence includes independent reference models, protocol assertions, exhaustive signed arithmetic, constrained random sources, malformed inputs, coverage, bounded formal proofs, deliberate fault injection, generic post-synthesis simulation, and application-derived replay.

The executed harness is **non-UVM**. A compatible production UVM simulator/library was unavailable. Vivado on the user's Windows workstation, HiPerGator, and the user's KV260 boards are not attached to this cloud execution environment. Yosys mapping is family-level synthesis, not K26 placement, timing closure, a bitstream, Fmax, board latency, or power. Full accumulation, scaling/bias, DMA/PS integration, production UVM, actual routing/timing, and board tests remain necessary. Both implemented design and executed verification evidence are present; unsupported stages are explicitly identified.

## Workload attribution and benchmark boundary

Alpaydin and Kaynak, *Optical Recognition of Handwritten Digits*, UCI Machine Learning Repository, DOI [10.24432/C50P49](https://doi.org/10.24432/C50P49), [source and CC BY 4.0 license](https://archive.ics.uci.edu/dataset/80/optical+recognition+of+handwritten+digits). The scikit-learn loader packages 1,797 images from the original test subset. This project creates a new stratified split within that subset; its accuracy is not the official writer-independent benchmark. Raw images are not redistributed. Derived masks, weights, predictions, and split indices are provided with source attribution. Data transformations include scaling, integer quantization, mask pruning, and the new split.
