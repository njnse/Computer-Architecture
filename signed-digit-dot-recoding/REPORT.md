# Exact signed-digit dot-product recoding

## Question and measured conclusion

Does exact magnitude recoding reduce shared bit-plane service cycles on genuine signed neural activations, and does that benefit survive conversion/storage cost and a stronger radix-4 Booth control?

On the predefined W8/N4 Tanh slice, all three newly trained checkpoints give an aggregate TC-bitmap cost of **8.491829 cycles/block** and SM-bitmap cost of **7.658252**, a **1.108847x equal-clock throughput ratio**. Their logical LUT counts are **217 and 257**; the equal-clock throughput/LUT proxy is **0.936264x**.

The stronger Booth-bitmap baseline takes **4.987708 cycles/block**. SM's throughput ratio versus Booth is **0.651285x**, requiring **53.5425% more service cycles**. Its throughput/LUT proxy versus Booth is **0.775461x**. A favorable TC comparison alone therefore does not establish a superior signed execution mechanism. Full resource and sensitivity results are retained below rather than selecting the best baseline.

This completes a reproducible RTL experiment with newly trained small MLP workloads. It is not a new quantizer, a publication-ready NeurIPS method, a complete FPGA accelerator or a physical timing result. Exact signed recoding is known prior art; see [verified related work](RELATED_WORK.md).

## Hypothesis, interface and architecture

[SPEC.md](SPEC.md) fixes the primary slice and ReLU/precision/grouping controls before performance inspection. All implementations compute the same signed integer inner product, with O=2W+ceil(log2(N))+1, one active job, one result slot, ordered 8-bit tags, ready/valid backpressure and reset cancellation.

TC processes raw two's-complement activation bits with a negative sign plane. SM captures each unsigned W-bit magnitude and a signed W+1-bit weight conditionally negated by the activation sign. The extra coefficient bit is necessary: negating a W-bit minimum weight must represent +2^(W-1). The activation magnitude also retains W bits to represent abs(-2^(W-1)). Dropping either protection silently corrupts supported corners.

Radix-4 modified Booth stores D=ceil(W/2) signed digits in {-2,-1,0,1,2}. RTL uses an overlapping-bit case table; the independent reference uses `d_j=bit(2j-1)+bit(2j)-2*bit(2j+1)`. Sign extension handles odd widths. The group computes all lane contributions for one digit position per cycle. This is an executed conventional exact signed-digit mechanism, not MSD's restricted learned weight representation or a full prior accelerator reproduction.

Both TC and SM have separate bitmap/counter implementations; Booth has bitmap/counter controls. Every dynamic design receives identical zero-weight qualification. Parallel arithmetic and a simple fixed-W serial endpoint supply additional controls. Every run uses matched operand/result widths, lane count and endpoint traffic. Conversion occurs combinationally before capture and is not assigned a fabricated timing cost; its actual mapped logic and storage are included.

## New workload training, calibration and provenance

New 64→32→10 MLPs are trained on UCI handwritten digits, with Tanh and ReLU, seeds 7/31/97, 120 epochs, batch 64, Adam learning rate .003, weight decay .0001, beta1 .9, beta2 .999 and epsilon 1e-8. Xavier-like Tanh and He-like ReLU initialization are specified in `train_models.py`; CPU BLAS/OpenMP/MKL threads are fixed to one. An independent finite-difference gradient check validates both training paths.

Minimum validation cross entropy selects each checkpoint. Tanh uses its mathematical activation bound of one; ReLU's global hidden activation maximum is determined on validation only. Per-class symmetric output weights and hidden values are quantized by round-to-nearest and clipping to signed qmax. No test labels select a representation, checkpoint, quantization threshold or hardware parameter. There is no hardware-aware loss, pruning, QAT or claim of improved learning from recoding.

The 1,797-image scikit-learn subset is re-split into 1,077/360/360 training/validation/test images using pinned prior split indices. It is the original UCI test subset, not the official writer-independent benchmark. Pixel/label hashes, attribution and CC BY 4.0 licensing are documented in [toolchain](TOOLCHAIN.md) and `fixtures/provenance.json`. Unlike the predecessor, no existing trained weights are reused.

| Model | Validation-selected epoch | Float correct | Negative quantized hidden values | Zero hidden values | Hidden-bound exceedance |
| --- | ---: | ---: | ---: | ---: | ---: |
| tanh_7 | 101 | 350/360 | 53.038% | 0.182% | 0.0000% |
| tanh_31 | 118 | 351/360 | 50.859% | 0.286% | 0.0000% |
| tanh_97 | 98 | 351/360 | 49.436% | 0.182% | 0.0000% |
| relu_7 | 53 | 350/360 | 0.000% | 20.790% | 0.0000% |
| relu_31 | 99 | 352/360 | 0.000% | 17.422% | 0.0174% |
| relu_97 | 71 | 350/360 | 0.000% | 21.233% | 0.0174% |

The first layer/activation executes in host floating-point software. RTL executes the quantized **output-layer block dot products** from real hidden values, not an artificial sign-flipped or recentered dataset. The host reduces blocks, rescales by hidden/weight scales and applies bias/argmax. Per-image service totals are sums of serialized block costs, not measured end-to-end inference latency or a memory-overlapped accelerator.

All six checkpoints and all predefined W8/N4, W4/N4 and W8/N8 cases are actually replayed. N4 outputs 28,800 blocks per model/mechanism; N8 outputs 14,400. Each class uses all 32 hidden features. Test predictions and class dots are cross-checked with independent NumPy integer matrix multiplication.

Training history/checkpoints are retained. One identical-seed retraining hash cross-check establishes deterministic regeneration; those duplicates are not counted as additional independent seeds.

## Measured implementation and service costs

W8/N4 Tanh aggregate across three checkpoints, each evaluated on the same 360 test images:

| Mechanism | RTL cycles/block | Generic cells | Logical LUT | Logical FF | DSP-disabled DSP |
| --- | ---: | ---: | ---: | ---: | ---: |
| parallel | 1.000000 | 2085 | 727 | 28 | 0 |
| tc_fixed | 9.000000 | 567 | 162 | 128 | 0 |
| tc_counter | 8.858090 | 775 | 212 | 126 | 0 |
| tc_bitmap | 8.491829 | 738 | 217 | 128 | 0 |
| sm_counter | 7.915162 | 912 | 258 | 130 | 0 |
| sm_bitmap | 7.658252 | 892 | 257 | 132 | 0 |
| booth_counter | 4.995023 | 1066 | 293 | 136 | 0 |
| booth_bitmap | 4.987708 | 1087 | 306 | 136 | 0 |

Generic primitive counts/types and actual mapped cell types are in `results/resources.json`. Forty-five synthesis configurations cover W4/N4 and W8/N4, eight mechanisms under generic and DSP-disabled xcup mapping; six dynamic W8/N8 mechanisms under both flows; and one DSP-allowed parallel W8/N4 map. All have zero inferred latches. The latter uses **57 LUT, 28 FF and 4 DSP cells**, with one block/cycle. Serial recoding does not outperform parallel arithmetic in cycle throughput.

SM stores N*(W+1) coefficient bits versus TC's N*W weight bits. Booth stores N*3D digit bits rather than N*W raw activations. Actual FF differences also include control optimization. Full input payloads are still transferred; no compression or bandwidth reduction is measured. Equal-clock throughput/LUT is a partial resource proxy, not matched-area silicon or a replicated multi-engine system.

Against TC, SM's candidate/baseline clock-frequency ratio must exceed **0.901838** to preserve throughput benefit. Against Booth it must exceed **1.535425**. These are algebraic break-even ratios only. No actual candidate frequency advantage/loss is assumed.

## Controls, ablations and failure boundaries

| W/N | Workload | SM/TC throughput | SM/TC throughput per LUT | SM/Booth throughput | SM/Booth throughput per LUT |
| --- | --- | ---: | ---: | ---: | ---: |
| 8/4 | tanh | 1.1088x | 0.9363x | 0.6513x | 0.7755x |
| 8/4 | relu | 1.0000x | 0.8444x | 0.7420x | 0.8835x |
| 4/4 | tanh | 1.2276x | 1.0305x | 0.7775x | 0.9081x |
| 4/4 | relu | 1.0000x | 0.8394x | 0.9490x | 1.1084x |
| 8/8 | tanh | 1.1231x | 0.8651x | 0.6264x | 0.8109x |
| 8/8 | relu | 1.0000x | 0.7703x | 0.6631x | 0.8586x |

ReLU has no negative hidden activations. TC/SM bitmap cycles and TC/SM counter cycles are exactly equal on every ReLU checkpoint/precision/grouping, while conversion/storage logic still exists in SM. This directly isolates a no-cycle-benefit case rather than attributing gains to a different trained model. Cross-Tanh/ReLU accuracy differences are not recoding effects: they are separate workload models.

Counter controls isolate internal-hole skipping from representation change. SM bitmap versus SM counter gives **1.033547x** on the primary slice. Booth bitmap versus Booth counter likewise distinguishes digit recoding from hole skipping. All controls receive the same zero-weight information; reporting only fixed W-plane arithmetic would exaggerate the architectural contribution.

Booth bitmap improves service throughput over its counter by only **0.1467%**, but uses **306 versus 293 LUTs**. Its throughput/LUT proxy is **0.958921x**. Fewer radix-4 positions make internal holes rare in these group unions, so the extra bitmap control is not justified by this partial resource metric. This identifies an implementation boundary, not an assertion about all signed workloads or routed clocks.

The synthetic sign/range sweep uses magnitude bounds 3/31/127, negative probabilities 0/50/100%, zero-weight probabilities 0/50%, seeds 7/31/97 and 256 groups. It isolates why near-zero negative TC values fill many planes, why SM improves there, and why dense group unions reduce skipping at larger ranges. Booth may have more active digits than magnitude for individual values such as +2, but fewer for values such as +7. These cases are explicitly checked and all streams retained. They are controlled mechanism tests, not realistic workload population estimates.

## Accuracy and conditional uncertainty

| Activation | Precision | Correct predictions for seeds 7 / 31 / 97 |
| --- | --- | --- |
| tanh | 4 | 352/360 (97.778%) / 350/360 (97.222%) / 348/360 (96.667%) |
| tanh | 8 | 350/360 (97.222%) / 351/360 (97.500%) / 351/360 (97.500%) |
| relu | 4 | 339/360 (94.167%) / 350/360 (97.222%) / 349/360 (96.944%) |
| relu | 8 | 350/360 (97.222%) / 352/360 (97.778%) / 350/360 (97.222%) |

All eight mechanisms have identical integer class-dot matrices and quantized predictions at fixed model/precision; W8/N4 and W8/N8 agree. Quantization may change predictions relative to floating inference. Recoding neither retrains the model nor improves accuracy.

The primary SM/TC paired-image bootstrap interval is **[1.106483, 1.111258]x**; its between-seed ratio range is **[1.107130, 1.112272]x**. SM/Booth's conditional interval is **[0.650198, 0.652397]x**.

Bootstrap seed 991 and 4,000 resamples pair by image and retain all class blocks and all three fixed checkpoints together. Class blocks and repeated deterministic execution are not independent samples. These intervals condition on the fixed trained checkpoints and image subset; they do not quantify a population of training seeds, writer-independent generalization, board variability or physical timing. Writer correlation may further limit interpretation.

## Executed validation and evidence

- Eleven Python tests, including all W3/N2 tuples, signed widths 2..9, 6,000 signed random groups and independent training-gradient finite differences.
- **726 RTL/generic-netlist runs**, **3,700,388 checked outputs**, **18,995,525 checked cycles**, with **348 canceled jobs** accounted for.
- **144 public RTL runs**, **3,456,000 exact block outputs** from newly trained model traces.
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
