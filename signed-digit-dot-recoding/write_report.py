"""Generate English report and README from audited, executed measurements."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
R=ROOT/'results'
load=lambda name:json.loads((R/name).read_text())
summary=load('summary.json');effects=load('effects.json');app=load('application.json')
resources=load('resources.json');audit=load('validation.json');models=load('models.json')
profiles=load('activation_profiles.json')
assert audit['passed']


def effect(base,candidate,width=8,lanes=4,activation='tanh'):
    return next(x for x in effects if (x['baseline'],x['candidate'],x['width'],x['lanes'],x['activation'])==(base,candidate,width,lanes,activation))


tc=effect('tc_bitmap','sm_bitmap')
booth=effect('booth_bitmap','sm_bitmap')
span=effect('sm_counter','sm_bitmap')
booth_control=effect('booth_counter','booth_bitmap')
main=[]
for variant in ['parallel','tc_fixed','tc_counter','tc_bitmap','sm_counter','sm_bitmap','booth_counter','booth_bitmap']:
    rows=[x for x in app if (x['width'],x['lanes'],x['activation'],x['variant'])==(8,4,'tanh',variant)]
    cost=sum(x['mean_cycles_per_block'] for x in rows)/3
    mapped=next(x for x in resources if (x['width'],x['lanes'],x['variant'],x['flow'])==(8,4,variant,'xcup_nodsp'))
    generic=next(x for x in resources if (x['width'],x['lanes'],x['variant'],x['flow'])==(8,4,variant,'generic'))
    main.append(f"| {variant} | {cost:.6f} | {generic['cells']} | {mapped['lut']} | {mapped['ff']} | {mapped['dsp']} |")
sensitivity=[]
for width,n in [(8,4),(4,4),(8,8)]:
    for activation in ['tanh','relu']:
        a=effect('tc_bitmap','sm_bitmap',width,n,activation)
        b=effect('booth_bitmap','sm_bitmap',width,n,activation)
        sensitivity.append(f"| {width}/{n} | {activation} | {a['equal_clock_throughput_ratio']:.4f}x | {a['equal_clock_throughput_per_lut_ratio']:.4f}x | {b['equal_clock_throughput_ratio']:.4f}x | {b['equal_clock_throughput_per_lut_ratio']:.4f}x |")
accuracies=[]
for activation in ['tanh','relu']:
    for width in [4,8]:
        rows=sorted([x for x in app if (x['width'],x['lanes'],x['activation'],x['variant'])==(width,4,activation,'sm_bitmap')],key=lambda x:x['model_seed'])
        accuracies.append(f"| {activation} | {width} | "+' / '.join(f"{x['correct']}/360 ({100*x['correct']/360:.3f}%)" for x in rows)+' |')
training=[]
for key,m in models.items():
    p=next(x for x in profiles if x['width']==8 and x['lanes']==4 and x['activation']==m['activation'] and x['seed']==m['seed'])
    training.append(f"| {key} | {m['selected_epoch']} | {m['floating_test_correct']}/360 | {100*p['negative_fraction']:.3f}% | {100*p['activation_zero_fraction']:.3f}% | {100*p['hidden_clipped_fraction']:.4f}% |")
dsp=next(x for x in resources if x['flow']=='xcup_dsp')
vsbooth_cycle_increase=100*(1/booth['equal_clock_throughput_ratio']-1)
report=f'''# Exact signed-digit dot-product recoding

## Question and measured conclusion

Does exact magnitude recoding reduce shared bit-plane service cycles on genuine signed neural activations, and does that benefit survive conversion/storage cost and a stronger radix-4 Booth control?

On the predefined W8/N4 Tanh slice, all three newly trained checkpoints give an aggregate TC-bitmap cost of **{tc['baseline_cycles_per_block']:.6f} cycles/block** and SM-bitmap cost of **{tc['candidate_cycles_per_block']:.6f}**, a **{tc['equal_clock_throughput_ratio']:.6f}x equal-clock throughput ratio**. Their logical LUT counts are **{tc['baseline_lut']} and {tc['candidate_lut']}**; the equal-clock throughput/LUT proxy is **{tc['equal_clock_throughput_per_lut_ratio']:.6f}x**.

The stronger Booth-bitmap baseline takes **{booth['baseline_cycles_per_block']:.6f} cycles/block**. SM's throughput ratio versus Booth is **{booth['equal_clock_throughput_ratio']:.6f}x**, requiring **{vsbooth_cycle_increase:.4f}% more service cycles**. Its throughput/LUT proxy versus Booth is **{booth['equal_clock_throughput_per_lut_ratio']:.6f}x**. A favorable TC comparison alone therefore does not establish a superior signed execution mechanism. Full resource and sensitivity results are retained below rather than selecting the best baseline.

This completes a reproducible RTL experiment with newly trained small MLP workloads. It is not a new quantizer, a publication-ready NeurIPS method, a complete FPGA accelerator or a physical timing result. Exact signed recoding is known prior art; see [verified related work](RELATED_WORK.md).

## Hypothesis, interface and architecture

[SPEC.md](SPEC.md) fixes the primary slice and ReLU/precision/grouping controls before performance inspection. All implementations compute the same signed integer inner product, with O=2W+ceil(log2(N))+1, one active job, one result slot, ordered 8-bit tags, ready/valid backpressure and reset cancellation.

TC processes raw two's-complement activation bits with a negative sign plane. SM captures each unsigned W-bit magnitude and a signed W+1-bit weight conditionally negated by the activation sign. The extra coefficient bit is necessary: negating a W-bit minimum weight must represent +2^(W-1). The activation magnitude also retains W bits to represent abs(-2^(W-1)). Dropping either protection silently corrupts supported corners.

Radix-4 modified Booth stores D=ceil(W/2) signed digits in {{-2,-1,0,1,2}}. RTL uses an overlapping-bit case table; the independent reference uses `d_j=bit(2j-1)+bit(2j)-2*bit(2j+1)`. Sign extension handles odd widths. The group computes all lane contributions for one digit position per cycle. This is an executed conventional exact signed-digit mechanism, not MSD's restricted learned weight representation or a full prior accelerator reproduction.

Both TC and SM have separate bitmap/counter implementations; Booth has bitmap/counter controls. Every dynamic design receives identical zero-weight qualification. Parallel arithmetic and a simple fixed-W serial endpoint supply additional controls. Every run uses matched operand/result widths, lane count and endpoint traffic. Conversion occurs combinationally before capture and is not assigned a fabricated timing cost; its actual mapped logic and storage are included.

## New workload training, calibration and provenance

New 64→32→10 MLPs are trained on UCI handwritten digits, with Tanh and ReLU, seeds 7/31/97, 120 epochs, batch 64, Adam learning rate .003, weight decay .0001, beta1 .9, beta2 .999 and epsilon 1e-8. Xavier-like Tanh and He-like ReLU initialization are specified in `train_models.py`; CPU BLAS/OpenMP/MKL threads are fixed to one. An independent finite-difference gradient check validates both training paths.

Minimum validation cross entropy selects each checkpoint. Tanh uses its mathematical activation bound of one; ReLU's global hidden activation maximum is determined on validation only. Per-class symmetric output weights and hidden values are quantized by round-to-nearest and clipping to signed qmax. No test labels select a representation, checkpoint, quantization threshold or hardware parameter. There is no hardware-aware loss, pruning, QAT or claim of improved learning from recoding.

The 1,797-image scikit-learn subset is re-split into 1,077/360/360 training/validation/test images using pinned prior split indices. It is the original UCI test subset, not the official writer-independent benchmark. Pixel/label hashes, attribution and CC BY 4.0 licensing are documented in [toolchain](TOOLCHAIN.md) and `fixtures/provenance.json`. Unlike the predecessor, no existing trained weights are reused.

| Model | Validation-selected epoch | Float correct | Negative quantized hidden values | Zero hidden values | Hidden-bound exceedance |
| --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(training)}

The first layer/activation executes in host floating-point software. RTL executes the quantized **output-layer block dot products** from real hidden values, not an artificial sign-flipped or recentered dataset. The host reduces blocks, rescales by hidden/weight scales and applies bias/argmax. Per-image service totals are sums of serialized block costs, not measured end-to-end inference latency or a memory-overlapped accelerator.

All six checkpoints and all predefined W8/N4, W4/N4 and W8/N8 cases are actually replayed. N4 outputs 28,800 blocks per model/mechanism; N8 outputs 14,400. Each class uses all 32 hidden features. Test predictions and class dots are cross-checked with independent NumPy integer matrix multiplication.

Training history/checkpoints are retained. One identical-seed retraining hash cross-check establishes deterministic regeneration; those duplicates are not counted as additional independent seeds.

## Measured implementation and service costs

W8/N4 Tanh aggregate across three checkpoints, each evaluated on the same 360 test images:

| Mechanism | RTL cycles/block | Generic cells | Logical LUT | Logical FF | DSP-disabled DSP |
| --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(main)}

Generic primitive counts/types and actual mapped cell types are in `results/resources.json`. Forty-five synthesis configurations cover W4/N4 and W8/N4, eight mechanisms under generic and DSP-disabled xcup mapping; six dynamic W8/N8 mechanisms under both flows; and one DSP-allowed parallel W8/N4 map. All have zero inferred latches. The latter uses **{dsp['lut']} LUT, {dsp['ff']} FF and {dsp['dsp']} DSP cells**, with one block/cycle. Serial recoding does not outperform parallel arithmetic in cycle throughput.

SM stores N*(W+1) coefficient bits versus TC's N*W weight bits. Booth stores N*3D digit bits rather than N*W raw activations. Actual FF differences also include control optimization. Full input payloads are still transferred; no compression or bandwidth reduction is measured. Equal-clock throughput/LUT is a partial resource proxy, not matched-area silicon or a replicated multi-engine system.

Against TC, SM's candidate/baseline clock-frequency ratio must exceed **{tc['break_even_candidate_over_baseline_frequency']:.6f}** to preserve throughput benefit. Against Booth it must exceed **{booth['break_even_candidate_over_baseline_frequency']:.6f}**. These are algebraic break-even ratios only. No actual candidate frequency advantage/loss is assumed.

## Controls, ablations and failure boundaries

| W/N | Workload | SM/TC throughput | SM/TC throughput per LUT | SM/Booth throughput | SM/Booth throughput per LUT |
| --- | --- | ---: | ---: | ---: | ---: |
{chr(10).join(sensitivity)}

ReLU has no negative hidden activations. TC/SM bitmap cycles and TC/SM counter cycles are exactly equal on every ReLU checkpoint/precision/grouping, while conversion/storage logic still exists in SM. This directly isolates a no-cycle-benefit case rather than attributing gains to a different trained model. Cross-Tanh/ReLU accuracy differences are not recoding effects: they are separate workload models.

Counter controls isolate internal-hole skipping from representation change. SM bitmap versus SM counter gives **{span['equal_clock_throughput_ratio']:.6f}x** on the primary slice. Booth bitmap versus Booth counter likewise distinguishes digit recoding from hole skipping. All controls receive the same zero-weight information; reporting only fixed W-plane arithmetic would exaggerate the architectural contribution.

Booth bitmap improves service throughput over its counter by only **{100*(booth_control['equal_clock_throughput_ratio']-1):.4f}%**, but uses **{booth_control['candidate_lut']} versus {booth_control['baseline_lut']} LUTs**. Its throughput/LUT proxy is **{booth_control['equal_clock_throughput_per_lut_ratio']:.6f}x**. Fewer radix-4 positions make internal holes rare in these group unions, so the extra bitmap control is not justified by this partial resource metric. This identifies an implementation boundary, not an assertion about all signed workloads or routed clocks.

The synthetic sign/range sweep uses magnitude bounds 3/31/127, negative probabilities 0/50/100%, zero-weight probabilities 0/50%, seeds 7/31/97 and 256 groups. It isolates why near-zero negative TC values fill many planes, why SM improves there, and why dense group unions reduce skipping at larger ranges. Booth may have more active digits than magnitude for individual values such as +2, but fewer for values such as +7. These cases are explicitly checked and all streams retained. They are controlled mechanism tests, not realistic workload population estimates.

## Accuracy and conditional uncertainty

| Activation | Precision | Correct predictions for seeds 7 / 31 / 97 |
| --- | --- | --- |
{chr(10).join(accuracies)}

All eight mechanisms have identical integer class-dot matrices and quantized predictions at fixed model/precision; W8/N4 and W8/N8 agree. Quantization may change predictions relative to floating inference. Recoding neither retrains the model nor improves accuracy.

The primary SM/TC paired-image bootstrap interval is **[{tc['fixed_checkpoint_image_bootstrap_95'][0]:.6f}, {tc['fixed_checkpoint_image_bootstrap_95'][1]:.6f}]x**; its between-seed ratio range is **[{tc['seed_ratio_range'][0]:.6f}, {tc['seed_ratio_range'][1]:.6f}]x**. SM/Booth's conditional interval is **[{booth['fixed_checkpoint_image_bootstrap_95'][0]:.6f}, {booth['fixed_checkpoint_image_bootstrap_95'][1]:.6f}]x**.

Bootstrap seed 991 and 4,000 resamples pair by image and retain all class blocks and all three fixed checkpoints together. Class blocks and repeated deterministic execution are not independent samples. These intervals condition on the fixed trained checkpoints and image subset; they do not quantify a population of training seeds, writer-independent generalization, board variability or physical timing. Writer correlation may further limit interpretation.

## Executed validation and evidence

- Eleven Python tests, including all W3/N2 tuples, signed widths 2..9, 6,000 signed random groups and independent training-gradient finite differences.
- **{summary['simulation_runs']} RTL/generic-netlist runs**, **{summary['checked_outputs']:,} checked outputs**, **{summary['checked_cycles']:,} checked cycles**, with **{summary['reset_canceled']} canceled jobs** accounted for.
- **144 public RTL runs**, **{summary['application_outputs']:,} exact block outputs** from newly trained model traces.
- Five compiled functional/protocol mutations detected; compilation failures do not count.
- Eight bounded SAT checks, W3/N2, 12 steps, arbitrary operands/reset/readiness/tags. Exact output, ordering membership, tag and stalled-output stability are checked. No unbounded/full-parameter proof.
- Forty-five actual synthesis configurations/readbacks, no inferred latches, and twenty-two generic-netlist stress replays.

`results/validation.json` audits model-selection history, sources/pins, raw result hashes, public integer matrices, ReLU no-gain control, retained netlists and counts. Synthesis stdout may be partial around ABC/ABC9; logs are retained as received and each netlist receives an independent complete structural/statistics readback. Mapped vendor timing simulation is not executed.

## Evidence-to-claim mapping

| Claim | Evidence | Boundary |
| --- | --- | --- |
| Signed recoding is exact, including minima/odd widths | Direct Python/SV oracles, exhaustive RTL, bounded SAT, min-width mutations | Finite tested parameters and bounded proof |
| Traces contain real signed neural intermediates | Newly trained checkpoints, source hashes, activation profiles, validation selection audit | Small MLP, floating host first layer |
| SM reduces some TC service costs | Emitted output-cycle CSVs and independent union formula | Core service cycles, not physical latency |
| Stronger signed controls change the conclusion | Actual Booth bitmap/counter RTL, identical stimuli | Mechanism baseline, not full MSD accelerator |
| ReLU gets no SM cycle benefit | All matched TC/SM ReLU replay costs | Additional physical clock cost remains unknown |
| Conversion/storage cost matters | Actual generic/mapped cell types, retained netlists and readback | Logical family mapping, not routed device area/Fmax |
| Learning and numerical outputs are reproducible | Finite-difference gradients, training history, deterministic checkpoint hashes, golden matrices | No new hardware-aware algorithm or large-model evidence |

## Engineering skills, limitations and thesis extension

This artifact demonstrates parameterized signed RTL, recoding and width discipline, variable-latency control, an independent scoreboard, reset/backpressure verification, error injection, bounded formal, post-synthesis simulation and measured resource/service tradeoffs. The SV harness is not UVM. A UVM-capable installation, production coverage closure, CDC checks, full-size formal induction, exact-device timing and physical-board tests remain unexecuted.

The next implementation gate is a K26-constrained Vivado flow and KV260 measurements under matched interfaces/clocks. Preprocessing may lengthen the critical input path; only actual routing/timing can determine whether a cycle improvement survives. Add accumulation/requantization and AXI/DMA integration, then separate transfer, compute and end-to-end latency. No power or physical energy estimates are reported.

A master's research question could generalize representation selection to real CNN/Transformer layers under measured resource/clock/accuracy budgets, with strong signed-digit and mixed LUT/DSP controls. A NeurIPS direction would additionally require a demonstrably new learning objective or quantization method, validation-only tuning, multiple larger models/datasets, more independent training seeds, primary-literature novelty assessment and actual implementation evidence. Those requirements remain unmet; this bounded artifact is not a completed thesis or conference-ready paper.

## Reproduction and artifacts

```bash
python3 run_project.py
```

See [spec](SPEC.md), [verification](VERIFICATION.md), [toolchain](TOOLCHAIN.md), [related work](RELATED_WORK.md) and [development record](DEVELOPMENT.md). Key outputs are [comparison data](results/comparison.csv), [paired effects](results/effects.json), [training history](results/training_history.json), [models](results/models.json), [public block CSV](results/application_blocks.csv), [resources](results/resources.json), retained logs/netlists and [audit](results/validation.json).

![Signed representation tradeoffs](results/tradeoffs.svg)
'''
(ROOT/'REPORT.md').write_text(report)
(ROOT/'README.md').write_text(f'''# Exact signed-digit dot-product recoding

An executed synthesizable RTL comparison of two's complement, exact magnitude recoding and radix-4 Booth, with bitmap/counter controls and newly trained Tanh/ReLU MLP hidden-layer traces.

## Reproduce

```bash
python3 run_project.py
```

Linux x86-64, Python 3.12.14, pinned local Icarus/YoWASP tools and analysis dependencies. Initial bootstrap needs HTTPS access. Reproduction trains six checkpoints and regenerates the full simulation, synthesis, validation and report pipeline. See [toolchain](TOOLCHAIN.md).

## Measured findings

For W8/N4 on all three new Tanh checkpoints and 360 fixed test images each:

- TC bitmap: **{tc['baseline_cycles_per_block']:.6f} cycles/block**; SM bitmap: **{tc['candidate_cycles_per_block']:.6f}**, or **{tc['equal_clock_throughput_ratio']:.4f}x equal-clock throughput**.
- SM/TC throughput per logical LUT: **{tc['equal_clock_throughput_per_lut_ratio']:.4f}x**; SM/Booth throughput: **{booth['equal_clock_throughput_ratio']:.4f}x**. Conversion/storage cost and the stronger baseline must be considered.
- ReLU TC/SM cycles are identical, so SM has no cycle gain on this control. Parallel arithmetic remains faster in cycles.
- All eight mechanisms preserve the same quantized integer dots and predictions. Training supplies workload realism; it is not a new quantization algorithm.

Validation: {summary['simulation_runs']} RTL/netlist runs, {summary['checked_outputs']:,} checked outputs, eleven Python tests, eight bounded W3/N2 checks, five detected compiled mutations, 45 synthesis/readback configurations and 22 generic-netlist replays. No inferred latches.

These are RTL service cycles and actual logical synthesis metrics, **not UVM execution, physical FPGA timing, power, board throughput or end-to-end inference speedup**. Small-MLP evidence and selective literature review do not establish thesis/conference submission readiness.

## Deliverables

[Specification](SPEC.md), [RTL](rtl), [executed verification](VERIFICATION.md), [report](REPORT.md), [training source](train_models.py), [models/history](results), [comparison](results/comparison.csv), [raw block outputs](results/application_blocks.csv), [resource summaries](results/resources.json), [audit](results/validation.json), compact logs/netlists, pinned dependencies and content manifest.

![Measured signed representation tradeoffs](results/tradeoffs.svg)
''')
print('Report and README written from audited measured results')
