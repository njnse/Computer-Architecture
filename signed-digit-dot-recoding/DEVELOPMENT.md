# Decisions and exploratory validation

The question, primary Tanh slice, ReLU no-gain control, widths/lane sensitivities and radix-4 baseline were frozen in `SPEC.md` before performance evaluation. Exact arithmetic was chosen rather than changing weights/activations or restricting representable values. Both SM and Booth have bitmap/counter controls, and all dynamic schedulers receive the same zero-weight information.

The first independent model run verified gradients and all six validation-selected checkpoints. A planned identical-seed retraining hash cross-check verifies deterministic regeneration; it does not add independent training samples. The experiment includes all three seeds for both activations, irrespective of accuracy or cycle gains. No checkpoint or input distribution is selected by hardware performance.

Known signed-digit and magnitude techniques are explicitly acknowledged. This artifact does not claim a new quantizer or priority in signed sparse arithmetic. Stronger exact Booth controls are included even if they outperform the candidate. All resource regressions and positive/no-gain cases are retained.

The signed-minimum corner determines the design: magnitude needs W unsigned bits, and sign-adjusted weights need W+1 signed bits. Mutation testing deliberately removes those protections, misencodes a Booth digit and its odd-width sign extension, and introduces a stalled-output overwrite. Only functional/protocol rejections count as detection.
