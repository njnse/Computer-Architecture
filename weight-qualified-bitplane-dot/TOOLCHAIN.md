# Toolchain and execution boundaries

Run from this project directory:

```bash
python3 run_project.py
```

This runs Python reference tests, RTL simulations, public workload replay, synthesis, generic-netlist replay, independent netlist readbacks, bounded formal checks, analysis, result auditing, and evidence packaging. It writes `build/` and overwrites generated `results/`. A fresh default run regenerates the complete grid. `--resume-synthesis` is only for an interrupted run after the complete RTL stage; it is not the recommended independent reproduction command.

## Pinned setup

Linux x86-64, Python 3.12.14, `venv`, and `dpkg-deb`. Native Windows is not supported by the pinned Debian Icarus package; use a compatible Linux environment or WSL. `tools/setup.py` installs tools into the project without root privileges. The initial bootstrap needs HTTPS downloads from PyPI and Debian. Experiments subsequently use the bundled scikit-learn data and attributed checkpoints, without trace downloads or commercial licenses.

- Icarus Verilog 12.0, Debian `12.0-2+b1`, package SHA256 `febe027d2d3f5a7e570844d55758339ab5490acc09f404f214a8719d89d07056`.
- YoWASP Yosys package `0.69.0.0.post1233`, Yosys revision `9f75ca1f9`, pinned Wasmtime/runtime dependencies in `tools/requirements.txt`.
- Numerical and plotting packages are fully pinned in `requirements.txt`. Main packages: NumPy 2.3.5, SciPy 1.17.0, scikit-learn 1.8.0, Matplotlib 3.10.8.

Validated runs reused those identical installed workspace tools using `IVERILOG`, `IVL_BASE`, `VVP`, and `YOSYS` environment selectors. `results/environment.json` records observed versions/platform; `results/commands.json` records exact invoked commands and return codes. Workspace-local `XDG_CACHE_HOME` and `MPLCONFIGDIR` avoid writes to a read-only home directory. The tool bootstrap itself is supplied but a fresh network install was not rerun on this already provisioned worker.

## Synthesis interpretation

Generic synthesis and `synth_xilinx -family xcup -flatten -noiopad` use the same tested RTL. DSP-disabled mappings use `-nodsp`. One W8/N4 parallel configuration permits DSP inference. `xcup` is a logical UltraScale+ mapping family, not an exact K26 device or KV260 board implementation. LUT/FF/DSP counts come from actual mapped cells; cell types and compact top-design netlists are retained.

YoWASP's synthesis stdout can terminate around ABC/ABC9 even when the process completes and emits netlists. Logs are retained as received; do not treat them as complete synthesis transcripts. Every emitted design is independently reloaded, checked, and its printed cell-type counts compared to the retained JSON. These readbacks supplement the actual netlist evidence, rather than inventing missing log output.

No Vivado, supported UVM runtime, place-and-route tool, exact-device timing flow, remote HiPerGator connection, or physical KV260 execution was available in this worker. The executed SystemVerilog scoreboard is not UVM. No Fmax, nanosecond latency, physical power, or end-to-end inference speedup is measured here.

## Licensing and attribution

Icarus is GPL-licensed; Yosys is ISC-licensed. Tools and binaries are obtained by the setup script, not redistributed in the artifact. Dependencies retain their upstream licenses.

Public inputs are the `sklearn.datasets.load_digits` subset of UCI *Optical Recognition of Handwritten Digits* by E. Alpaydin and C. Kaynak, [DOI 10.24432/C50P49](https://doi.org/10.24432/C50P49). The [primary dataset page](https://archive.ics.uci.edu/dataset/80/optical+recognition+of+handwritten+digits) was inspected and states CC BY 4.0. That attribution applies to the derived measurement records as well. The artifact records transformations, exact hashes, and split indices, without vendoring raw dataset files.

Checkpoints are six generated training outputs attributed to `pair-constrained-sparse-dot`; provenance pins their source commit and SHA256. The dataset is re-split within the original UCI test subset, not the official writer-independent benchmark. No new training or model selection is performed here.

Compressed text evidence is decoded with Python `base64.b64decode` followed by `gzip.decompress`. Each `.log.gz.b64` stores its original log content. `results/netlists.json.gz.b64` retains each flattened top design; it omits redundant unused library definitions, which are supplied by the pinned synthesis tool on readback. Original emitted JSON and canonical retained-design hashes are distinguished in resource rows.
