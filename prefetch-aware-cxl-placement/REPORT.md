# Experimental Report

## Question and scope

When local memory is limited, does ranking pages by sampled residual demand wait improve placement over sampled access counts? What happens when the training behavior becomes stale?

This artifact implements a controlled analytical experiment. It completes the experiment described here; it does not implement the full hardware–OS mechanism in the accompanying proposal. It makes no verified novelty or conference-readiness claim.

## Model

Each demand has a page identifier, prefetch lead time, and exposed-wait fraction. Its modeled contribution is:

    wait = max(0, tier_latency - prefetch_lead) * exposed_fraction
    modeled cost = 50 ns * demand count + sum(wait) + migration cost

The exposed fraction is prescribed by the workload, not measured from an out-of-order CPU. This is a deliberately separable model: no link contention, caches, scheduling, dependent instruction execution, TLB, or actual CXL protocol is simulated. Treat the sum as a cost functional, not actual application runtime.

Local latency is 100 ns. Remote latency is swept over 200, 300, and 400 ns. Sixteen abstract pages compete for 2, 4, or 8 local-page slots. Values are illustrative assumptions, not device calibration.

Each seed generates independent 2,400-demand training and evaluation streams. Eight stream pages receive 72% of accesses; eight other pages receive the remainder. Frequency-aligned workloads have zero prefetch lead and fully exposed wait. Prefetch-hidden workloads give stream pages 180–320 ns of prefetch lead and 25% exposed wait; other pages have zero lead and fully exposed wait. Phase-reversal workloads train on prefetch-hidden behavior, then invert which group benefits from prefetch lead and low exposure.

Frequency ranks sampled demand counts. Residual ranks the sampled difference between remote and local wait, using the prescribed lead/exposure and known model latencies. Both use the same Bernoulli sampling decisions, rates, capacity, and deterministic tie breaking. Ten independently generated seed pairs are used. Evaluation events do not inform either deployable policy.

The static service oracle ranks true evaluation-stream service savings. Its use of evaluation data is intentionally optimistic. Its placement is exactly optimal for service cost in this additive model, verified against exhaustive enumeration on a small workload. It ignores migration during selection and is therefore not optimal for total cost.

Initial local pages are identifiers 0 through capacity minus one. Each newly promoted page displaces one resident. Migration pair costs are 0, 5,000, or 20,000 ns, including both transfers by assumption. Policies currently select without a migration-benefit gate; the sweep evaluates that omission. There is one placement decision per evaluation window, not continuous online adaptation.

## Results

The predefined summary slice uses four local pages, 300 ns remote latency, 10% sampling, and 5,000 ns per migration pair. Values below are arithmetic means of each seed's fixed-placement-cost/policy-cost ratio.

| Workload | Frequency | Residual | Static service oracle |
| --- | ---: | ---: | ---: |
| Frequency-aligned | 0.980x | 0.980x | 0.998x |
| Prefetch-hidden | 0.964x | 1.118x | 1.144x |
| Phase reversal | 0.974x | 0.713x | 0.995x |

For prefetch-hidden workloads, residual's speedup ranges from 1.105x to 1.126x across seeds. For phase reversal it ranges from 0.698x to 0.722x. Ranges describe this workload generator; they are not confidence intervals for real applications.

The mean paired frequency-cost/residual-cost ratio is 1.160x in the prefetch-hidden slice and 0.732x after reversal. This paired comparison differs from dividing the aggregate means.

The key positive result is that the frequency policy promotes pages whose costs are already substantially hidden. The residual policy instead allocates capacity to the lower-frequency, exposed demands. This is an existence demonstration under controlled assumptions, not evidence that the ranking is superior across real workloads.

The negative result is more consequential for the proposed architecture: residual observations become dangerously stale after reversal. The model's phase reversal is intentionally abrupt and adversarial; it shows a failure mechanism, not its prevalence.

## Sampling and migration sensitivity

For four local pages and 300 ns remote latency, the mean paired frequency-cost/residual-cost ratios are:

| Workload | Sampling | No migration cost | 5 us per pair | 20 us per pair |
| --- | ---: | ---: | ---: | ---: |
| Prefetch-hidden | 1% | 1.168x | 1.123x | 1.019x |
| Prefetch-hidden | 10% | 1.199x | 1.160x | 1.070x |
| Prefetch-hidden | 100% | 1.200x | 1.146x | 1.020x |
| Phase reversal | 10% | 0.736x | 0.732x | 0.723x |

Higher sampling is not monotonically better once migration is charged. Even in the stationary workload, finite-window frequency rankings cause different resident-page retention and copying behavior. Removing migration cost isolates the service benefit; charging it exposes the need for a net-benefit gate.

The full sweep covers 810 workload/configuration/seed combinations, three policy choices, and three migration costs: 7,290 records. Inspect individual rows rather than generalizing from the illustrative slice alone.

## Validation

Six tests passed: prefetch timing arithmetic, local-memory monotonicity, exhaustive verification of the service oracle, a hotness/residual counterexample, equality between the signal and counterfactual service savings, and deterministic sampling. The CSV and figure were produced by executing the checked-in source.

These checks validate this model's implementation; they do not validate its architectural realism. Common sampling random numbers reduce an avoidable comparison confound.

## Limits and next research steps

The proposed signal is privileged: lead and exposure are provided exactly by generated events. Practical hardware would have noisy, bounded estimates. The model also assumes prefetch lead and exposure do not change with placement; real queue contention and instruction execution can invalidate that assumption.

Sampling lookup overhead, metadata storage, migration stalls, bandwidth competition, and shared pages require explicit implementation before a net architectural benefit can be claimed. The present constant pair cost cannot establish CXL-specific feasibility. Real program traces and cycle-accurate validation are missing.

The next experiments should add a training-only migration gate and cooldown, a phase-change detector, bounded noisy counters, and stronger latency/stall-aware policies. Then implement the signal in a validated two-tier simulator and test public application workloads. A simulator-only oracle should quantify how much predictive accuracy survives replacing the prescribed exposure fraction with observable events.

## Related work and thesis contribution

A live academic literature review was unavailable in this session. No bibliography or claim of priority is asserted. Before committing to a thesis, verify the closest work in prefetch-aware tiering, feedback-directed prefetching, stall-aware page migration, and criticality/MLP-aware memory management.

The candidate thesis contribution remains a bounded hardware signal and stable migration controller for prefetch-conditioned placement. This artifact supplies a reproducible positive case and a concrete failure case to guide that design. HPCA is a possible target after literature verification and substantially stronger architectural evidence.
