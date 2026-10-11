# Experiment decisions and exploratory record

The question and public comparison slice were fixed in `SPEC.md` before measurement. The mechanism and independent equally qualified counter control were implemented together. The mathematical benefit is expected only when zero-weight lanes otherwise contribute unique activation bits; dense nonzero weights must retain identical service cycles. All generated sparse/dense and signed/unsigned failure-boundary results are retained.

The first Yosys version probe failed because its default cache directory was under the read-only worker home. Setting `XDG_CACHE_HOME` to a writable workspace cache resolved it; the successful version probe established Yosys 0.69 revision 9f75ca1f9. This was an environment failure, not a numerical counterexample or a measured hardware regression.

No checkpoints were retrained or selected using these measurements. All three source training seeds are included for both dense and restricted-pattern checkpoints. No classification accuracy improvement is attributed to a scheduling-only change. Group widths and synthetic scenarios were chosen for mechanism sensitivity; multiplying configuration counts is not a replacement for application diversity.

The artifact is a distinct extension of the prior shared-bit-union study, with a new qualification mechanism and independent matched controls. Known zero-weight/bit-sparsity prior art is explicitly acknowledged. No conceptual priority is claimed.
