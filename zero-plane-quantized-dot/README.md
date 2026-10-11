# Zero-plane quantized dot products

A complete synthesizable RTL experiment asking whether a shared activation bitmap can reduce **exact signed dot-product cycles** beyond contiguous precision trimming, and what resource cost and input boundaries result. The artifact implements registered parallel multiplication, full-width bit serial, leading-only trimming, zero-plane skipping bitmap span ablation and a separately implemented counter-based leading/trailing contiguous-span baseline.

```bash
python3 run_project.py
```

Use Python 3.12 on Linux x86-64. Initial setup needs network access, `venv` and `dpkg-deb`; versions and tool overrides are in [TOOLCHAIN.md](TOOLCHAIN.md). The runner executes tests, RTL/public-workload replay, generic and logical Xilinx synthesis, gate-netlist tests, reduced bounded proofs, DSP-enabled mapping, analysis, audit and compact evidence packaging. No GPU or proprietary simulator is required.

- [Specification and pre-experiment hypothesis](SPEC.md)
- [Executed verification and its scope](VERIFICATION.md)
- [Results, causal interpretation and submission gaps](REPORT.md)
- [Primary related work and novelty boundary](RELATED_WORK.md)
- [Exploratory revisions and verification gap](DEVELOPMENT.md)
- [Standalone tradeoff figure](results/tradeoffs.svg)
- [Machine-generated measurements](results/simulation.json), [resources](results/resources.json), [public block outputs](results/application_blocks.csv), and [summary](results/summary.json)

The work demonstrates signed parameterized RTL, exact bit-serial arithmetic, variable-latency scheduling, ready/valid control, independent scoreboards, mutation testing, reduced formal checking, netlist simulation and measured cycle/resource comparisons. Public digits checkpoints and splits are attributed in `fixtures/provenance.json`; six checkpoints are retained for byte-exact provenance, but this artifact uses only the dense and sparse seed-7 models. There is no new training or tuning on held-out labels.

Performance is measured RTL **cycles**, resource counts are Yosys synthesis/mapping outputs, and N=1/8 public grouping curves are explicitly input-derived analytical sensitivities. Class reduction/rescale/bias is Python postprocessing. No routed Fmax, KV260 deployment, board latency, power, HiPerGator execution or real UVM is claimed. This bounded experimental artifact is not a completed thesis or publication-ready paper.
