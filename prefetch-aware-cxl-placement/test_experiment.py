import itertools
import unittest
from experiment import Demand, benefit, cost, generate, oracle, policy, wait


class ModelTests(unittest.TestCase):
    def test_prefetch_hides_only_available_lead(self):
        self.assertEqual(wait(Demand(0, 150, 0.5), 300), 75)
        self.assertEqual(wait(Demand(0, 150, 0.5), 100), 0)

    def test_local_never_increases_service_cost(self):
        events = generate(17, "prefetch-hidden")
        self.assertLessEqual(cost(events, frozenset(range(16)), 100, 300),
                             cost(events, frozenset(), 100, 300))

    def test_oracle_matches_exhaustive_static_placement(self):
        events = [Demand(i, i * 40, 1 / (i + 1)) for i in range(6)]
        chosen = oracle(events, 2, 100, 300)
        exhaustive = min(cost(events, frozenset(p), 100, 300)
                         for p in itertools.combinations(range(16), 2))
        self.assertAlmostEqual(cost(events, chosen, 100, 300), exhaustive)

    def test_residual_ranking_differs_from_hotness(self):
        events = [Demand(0, 300, 1)] * 100 + [Demand(8, 0, 1)] * 10
        self.assertEqual(policy(events, "frequency", 1, 1, 0, 100, 300), {0})
        self.assertEqual(policy(events, "residual", 1, 1, 0, 100, 300), {8})

    def test_signal_equals_counterfactual_service_reduction(self):
        events = generate(7, "prefetch-hidden", 100)
        scores = benefit(events, 100, 300)
        baseline = cost(events, frozenset(), 100, 300)
        for page in range(16):
            self.assertAlmostEqual(scores[page],
                baseline - cost(events, frozenset([page]), 100, 300))

    def test_sampling_reproducible(self):
        events = generate(1, "prefetch-hidden")
        self.assertEqual(policy(events, "residual", 4, .1, 5, 100, 300),
                         policy(events, "residual", 4, .1, 5, 100, 300))


if __name__ == "__main__":
    unittest.main()
