"""Write English analysis from audited measured results; never invent timing."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
R=ROOT/'results'
load=lambda name:json.loads((R/name).read_text())
summary=load('summary.json');effects=load('effects.json');app=load('application.json')
resources=load('resources.json');audit=load('validation.json');sim=load('simulation.json')
assert audit['passed']


def effect(base,candidate,width=8,lanes=4,policy='index'):
    return next(x for x in effects if (x['baseline'],x['candidate'],x['width'],x['lanes'],x['policy'])==(base,candidate,width,lanes,policy))


q=effect('bitmap','qualified_bitmap')
fair=effect('qualified_counter','qualified_bitmap')
old=effect('counter','qualified_bitmap')
main=[]
for variant in ['parallel','fixed','counter','qualified_counter','bitmap','qualified_bitmap']:
    rows=[x for x in app if x['width']==8 and x['lanes']==4 and x['policy']=='index' and x['variant']==variant]
    cycles=sum(x['mean_cycles_per_block'] for x in rows)/3
    rs=next(x for x in resources if (x['width'],x['lanes'],x['variant'],x['flow'])==(8,4,variant,'xcup_nodsp'))
    generic=next(x for x in resources if (x['width'],x['lanes'],x['variant'],x['flow'])==(8,4,variant,'generic'))
    main.append(f"| {variant} | {cycles:.6f} | {generic['cells']} | {rs['lut']} | {rs['ff']} | {rs['dsp']} |")
table='\n'.join(main)
sens=[]
for width,lanes in [(8,4),(4,4),(8,8)]:
    for policy in ['dense','index']:
        a=effect('bitmap','qualified_bitmap',width,lanes,policy)
        b=effect('qualified_counter','qualified_bitmap',width,lanes,policy)
        sens.append(f"| {width}/{lanes} | {policy} | {a['equal_clock_throughput_ratio']:.4f}x | {b['equal_clock_throughput_ratio']:.4f}x | {a['equal_clock_throughput_per_lut_ratio']:.4f}x |")
accuracies=[]
for width in [4,8]:
    for policy in ['dense','index']:
        rows=[x for x in app if x['width']==width and x['lanes']==4 and x['policy']==policy and x['variant']=='qualified_bitmap']
        accuracies.append(f"| {width} | {policy} | "+' / '.join(f"{x['correct']}/360 ({100*x['correct']/360:.3f}%)" for x in sorted(rows,key=lambda x:x['model_seed']))+' |')
dsp=next(x for x in resources if x['flow']=='xcup_dsp')
def synth_gain(kind,p):
    rows=lambda v:[x['mean_latency'] for x in sim if x['run'].startswith(f'sweep_{kind}_p{p}_') and x['variant']==v]
    return sum(rows('bitmap'))/sum(rows('qualified_bitmap'))

report=f'''# Weight-qualified bit-plane dot products

## Research question and measured conclusion

Can zero-weight lane qualification improve a shared activation-bit scheduler without sacrificing exact signed arithmetic, and does that benefit survive an equally qualified contiguous-counter control and added mapping cost?

On the predefined W8/N4 pruned-checkpoint slice, qualification changes bitmap service cost from **{q['baseline_cycles_per_block']:.6f} to {q['candidate_cycles_per_block']:.6f} cycles per block**, a **{q['equal_clock_throughput_ratio']:.6f}x equal-clock throughput ratio**. Against the stronger equally qualified counter, the candidate achieves **{fair['equal_clock_throughput_ratio']:.6f}x**. Its logical LUT counts are **{fair['candidate_lut']} versus {fair['baseline_lut']}**, giving a **{fair['equal_clock_throughput_per_lut_ratio']:.6f}x equal-clock throughput/LUT proxy**. Gains over the unqualified counter alone ({old['equal_clock_throughput_ratio']:.6f}x) overstate the advantage attributable to internal-hole skipping; both schedulers benefit from qualification.

This is a completed runnable RTL experimental artifact. It is not a newly trained quantizer, a complete accelerator, a NeurIPS-ready method, a full reproduction of prior architectures, or physical FPGA performance evidence. Known weight/bit sparsity combinations are acknowledged in [related work](RELATED_WORK.md).

## Method and matched controls

The hypothesis, primary slice, and sensitivities were fixed in [SPEC.md](SPEC.md). The on-handshake union includes activation lane i only when weight i is nonzero. Arithmetic still uses all captured operands and remains bit-exact. The sign plane subtracts its shifted partial sum. Cancellation between nonzero weights is not exploited.

Six endpoint implementations use matched widths, lane counts, result widths, tags, input vectors, and ready/valid protocol: parallel, fixed serial, bitmap, qualified bitmap, separate counter span, and equally qualified counter span. Every simulated no-stall output's latency is compared with independently enumerated K+1 cost, including endpoint overhead; interval totals separately account for startup and drain.

The 33 synthesis configurations comprise W4/N4 and W8/N4 for all six mechanisms under generic and DSP-disabled xcup mapping, W8/N8 for the four dynamic schedulers under both flows, and one DSP-allowed W8/N4 parallel mapping. Identical tool versions and settings are used within each comparison. Qualification uses no additional metadata storage, but adds weight-zero detection and qualification logic; optimized LUT/FF costs are measured, not assumed free. Resources are fixed per endpoint, not fitted to test accuracy or selected by favorable outcomes. Throughput/LUT is a partial resource proxy, not matched-area silicon or replicated-system throughput.

## Workload provenance and experimental separation

Inputs are scikit-learn's UCI handwritten-digits subset, with exact pixel/label hashes, attribution and CC BY 4.0 licensing in [toolchain](TOOLCHAIN.md) and `fixtures/provenance.json`. Existing training/validation/test split sizes are 1,077/360/360. This re-splits the original UCI test subset; it is not an official writer-independent benchmark.

All six attributed source checkpoints are reused: dense and restricted-pattern/pruned models for training seeds 7, 31, and 97. No retraining or checkpoint selection occurs here. Inputs use round-to-nearest quantization from 0..16 into signed positive qmax; weights use per-class symmetric scaling from the frozen checkpoint. W8/N4, W4/N4 and W8/N8 are all actually replayed in RTL, not only analytically counted.

Each N4 replay has 57,600 block outputs (360 images, ten classes, sixteen feature blocks); each N8 replay has 28,800. Both use all 64 features. Host integer reductions are cross-checked with independent matrix multiplication. Scaling, bias and classification remain Python operations. Reported per-image service cycles sum block costs; they are not an integrated or memory-overlapped inference latency.

The synthetic grid isolates failure boundaries using nonzero surviving weights, zero probabilities 0/25/50/75/100%, unsigned/signed/all-minus-one activations, seeds 7/31/97, W8/N4 and 512 groups. Those random seeds are workload replicates, not independent hardware measurements or training seeds of a new method. Extra reset/stall tests use seed 4242; longer startup/drain checks use 2718. The test split never selects a scheduling threshold: qualification is exact zero comparison.

## Main resource and service comparison

Arithmetic means across all three W8/N4 pruned checkpoints, each with the same 360 test images:

| Mechanism | RTL cycles/block | Generic cells | Logical LUT | Logical FF | DSP-disabled mapping DSP |
| --- | ---: | ---: | ---: | ---: | ---: |
{table}

The separate DSP-allowed parallel map uses **{dsp['lut']} LUT, {dsp['ff']} FF and {dsp['dsp']} DSP cells**, and still accepts one block per cycle. Parallel arithmetic is faster in cycles than the serial candidate. These DSP/LUT regimes cannot be collapsed into one fair area score; memory bandwidth and the target's DSP budget would determine the practical choice.

For the fair qualified-counter comparison, bitmap saves **{fair['cycles_saved_percent']:.4f}% of service cycles**. The candidate/baseline clock-frequency ratio must exceed **{fair['break_even_candidate_over_baseline_frequency']:.6f}** to retain equal-throughput advantage. This is a derived break-even condition, not a measured clock frequency. Generic/mapped logical synthesis cannot establish KV260 Fmax.

## Ablations, sensitivity and negative findings

The within-scheduler comparison isolates qualification; qualified bitmap versus qualified counter isolates internal-hole scheduling after both receive identical weight-zero information.

| W/N | Checkpoints | Q-bitmap / bitmap throughput | Q-bitmap / Q-counter throughput | Q-bitmap / bitmap throughput per LUT |
| --- | --- | ---: | ---: | ---: |
{chr(10).join(sens)}

For synthetic dense **nonzero** weights, qualification and unqualified bitmap have exactly equal service cycles in all three activation regimes. Qualification's extra logic therefore has no cycle benefit there. Logical resources and input timing must still be paid; no measured physical timing loss is assumed.

At 50% generated zero weights, bitmap qualification yields {synth_gain('unsigned',50):.4f}x on unsigned values, {synth_gain('signed',50):.4f}x on uniformly signed values, and only {synth_gain('negative',50):.4f}x on all-minus-one values. In the latter, any surviving lane fills every bit plane; only all-zero-weight groups take the short path. At 100% zero weights, one-cycle zero output is a useful correctness/limit case, not a realistic application speedup claim. Raw sweeps and all public cases are retained, including dense or weak-benefit conditions.

Group size changes the chance that surviving lanes fill the union, while pruning pattern and activation location determine which removed lanes had unique bits. Nominal zero-weight fraction alone is not a reliable predictor of service savings. No bandwidth reduction is obtained: every endpoint still transfers the full activation and weight vectors.

## Accuracy and uncertainty

All six mechanisms produce identical integer dot matrices and classifications at each checkpoint/precision. Cross-grouping W8/N4 and W8/N8 dot matrices also match. This proves execution equivalence for the replayed inputs; it does not show that quantization or pruning improves accuracy.

| Precision | Checkpoints | Correct predictions for seeds 7 / 31 / 97 |
| --- | --- | --- |
{chr(10).join(accuracies)}

The primary fair ratio's paired-image bootstrap interval is **[{fair['fixed_checkpoint_image_bootstrap_95'][0]:.6f}, {fair['fixed_checkpoint_image_bootstrap_95'][1]:.6f}]x**, using seed 991 and 4,000 resamples. Each resampled image retains all its class blocks and all three fixed checkpoints together. Its between-checkpoint ratio range is **[{fair['seed_ratio_range'][0]:.6f}, {fair['seed_ratio_range'][1]:.6f}]x**.

The bootstrap only describes image sampling conditional on these frozen checkpoints. It does not quantify the population of training seeds, writer-independent generalization, physical clock variability, or independent board replication. Writer correlation may further limit interpretation. Confidence intervals do not turn this small linear classifier into a modern CNN/Transformer benchmark.

## Executed validation

- Ten independent Python tests passed, including exhaustive W3/N2 tuples and seeded signed arithmetic.
- **{summary['simulation_runs']} RTL/generic-netlist runs**, **{summary['checked_outputs']:,} checked outputs**, and **{summary['checked_cycles']:,} checked cycles**; **{summary['reset_canceled']} canceled jobs** explicitly accounted for.
- **{summary['application_runs']} public RTL runs**, totaling **{summary['application_outputs']:,} exact block outputs**.
- Three compiled mutations detected by functional/protocol checks: wrong sign, stalled overwrite, inverted weight qualification.
- Six W3/N2 bounded SAT checks for 12 steps with arbitrary operands, tags, reset and sink readiness. Arithmetic, pending-result membership, tag correspondence and stalled-output stability are checked; this is not unbounded/full-parameter proof.
- **{summary['synthesis_configurations']} synthesis configurations**, zero inferred latches, independent structural/statistical readback of every retained top design, and **{summary['generic_netlist_replays']} generic-netlist stress replays**.

Coverage counts and exact commands are in `results/summary.json` and `commands.json`. Per-run output/stimulus hashes, actual tool-pin checks and measurement-source hashes preserve traceability. One complete candidate public block CSV and all per-image service records are checked in; the one-command run regenerates every run's CSV in `build/`. Synthesis stdout is retained as received and may be partial around ABC/ABC9; independent readback logs substantiate structural and cell-statistics checks.

## Evidence-to-claim mapping

| Claim | Executed evidence | Boundary |
| --- | --- | --- |
| Qualification preserves signed arithmetic | Python/SV independent scoreboards, exhaustive cases, public dot hashes, SAT | Finite tests and small bounded formal |
| Sparse weights reduce service cycles | Public emitted cycle CSVs, independently checked K+1, synthetic sweep | Core service cycles, not application runtime |
| Benefit also reaches the counter | Equally qualified counter ablation on identical operands | Mechanism baseline, not full Dynamic Stripes |
| Control logic has measurable cost | Actual mapped cells, retained netlists, independent readback | Logical mapping, not routed device area/Fmax |
| Prediction changes are zero | Independent integer matrix products and classification checks | Host postprocessing and small reused classifier |
| Method fails to help dense nonzero weights | All zero-probability sweeps and resource comparisons | Physical timing cost remains unknown |

## Engineering skills and research extension

The artifact demonstrates synthesizable parameterized signed RTL, variable-latency control, exact width handling, ready/valid/reset verification, independent scoreboards, mutation testing, bounded formal checks, netlist verification, reproducible synthesis and resource/service analysis. The executed harness is **not UVM**.

The next implementation gate is a K26-constrained Vivado flow plus KV260 execution under matched clocks/interfaces. Add weight-tile reuse, accumulation/requantization and AXI/DMA integration, then measure input-loading, compute and end-to-end times separately. Run an actual UVM environment on an installation proven to execute its library and features; close functional coverage and expand formal/protocol checks before production use.

A thesis contribution could investigate whether group-aware quantization/pruning objectives reduce qualified shared-plane cost across real CNN/Transformer layers, under fixed accuracy and resource/bandwidth budgets. This requires strong modern quantization baselines, validation-only tuning, independently held-out tests, new multi-seed training, an exhaustive nearby literature review, larger workloads, and actual timing/board evidence. Those prerequisites are unmet here. Potential MICRO/HPCA/ASPLOS or NeurIPS relevance is a research direction, not a submission-readiness claim.

## Reproduction and artifacts

```bash
python3 run_project.py
```

See [toolchain](TOOLCHAIN.md), [specification](SPEC.md), [verification](VERIFICATION.md), and [development record](DEVELOPMENT.md). Key artifacts: [comparison data](results/comparison.csv), [paired effects](results/effects.json), [per-image cycles](results/image_cycles.csv), [raw candidate blocks](results/application_blocks.csv), [resource summaries](results/resources.json), and [audit](results/validation.json).

![Measured cycle/resource tradeoffs](results/tradeoffs.svg)
'''
(ROOT/'REPORT.md').write_text(report)
(ROOT/'README.md').write_text(f'''# Weight-qualified bit-plane dot products

A complete reproducible signed-RTL experiment extending shared zero-plane scheduling with zero-weight lane qualification. It asks whether the saved service cycles justify extra control logic, using an equally qualified counter-span baseline and parallel arithmetic controls.

## Reproduce

```bash
python3 run_project.py
```

Linux x86-64, Python 3.12.14; pinned Icarus/YoWASP and analysis packages bootstrap locally. Initial network access is required for dependencies. See [toolchain](TOOLCHAIN.md). The run overwrites generated results and regenerates the full predefined experiment.

## Measured findings

For W8/N4 on all three reused pruned checkpoints and 360 fixed public test images each:

- Bitmap qualification: {q['baseline_cycles_per_block']:.6f} → {q['candidate_cycles_per_block']:.6f} cycles/block, **{q['equal_clock_throughput_ratio']:.4f}x equal-clock throughput**.
- Versus an equally qualified counter: **{fair['equal_clock_throughput_ratio']:.4f}x**, with {fair['candidate_lut']} versus {fair['baseline_lut']} logical LUTs; throughput/LUT proxy **{fair['equal_clock_throughput_per_lut_ratio']:.4f}x**.
- Dense nonzero weights have no cycle improvement; surviving all-minus-one activations mostly erase skipping. Parallel arithmetic remains faster in cycles.
- Scheduling preserves every replayed integer dot result and prediction. No new models are trained.

Validation: {summary['simulation_runs']} RTL/netlist runs, {summary['checked_outputs']:,} checked outputs, ten Python tests, six bounded W3/N2 SAT checks, three detected functional mutations, 33 synthesis/readback configurations and sixteen generic-netlist replays. No inferred latches.

These are simulated core cycles and actual logical synthesis counts, **not routed Fmax, physical board performance, UVM execution, or end-to-end inference speedup**. The public classifier is small and shares the prior project's data/checkpoints. Known combined weight/bit sparsity prior art is acknowledged; no novelty or publication-readiness claim is made.

## Deliverables

- [Specification](SPEC.md), [RTL](rtl), [executed verification](VERIFICATION.md), [report](REPORT.md), [related work](RELATED_WORK.md).
- [Simulation records](results/simulation.json), [public raw blocks](results/application_blocks.csv), [per-image cycles](results/image_cycles.csv), [comparison](results/comparison.csv).
- [Resources](results/resources.json), retained netlists/logs in `results/`, [result audit](results/validation.json), `MANIFEST.json` content hashes.
- [Development decisions](DEVELOPMENT.md) and pinned, attributed `fixtures/`.

![Measured service and resource tradeoffs](results/tradeoffs.svg)
''')
print('English report and project index generated from audited measurements')
