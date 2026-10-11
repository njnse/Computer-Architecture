import itertools
import random
import unittest
from reference import active, bit_decomposition, cycles, dot, pack


class ReferenceTests(unittest.TestCase):
    def test_exhaustive_signed_two_lane(self):
        for x0, x1, w0, w1 in itertools.product(range(-4, 4), repeat=4):
            for qualified in [False, True]:
                self.assertEqual(bit_decomposition([x0, x1], [w0, w1], 3, qualified), dot([x0, x1], [w0, w1]))

    def test_random_qualification_preserves_dot(self):
        rng = random.Random(4242)
        for width, lanes in itertools.product([4, 8], [1, 4, 8]):
            for _ in range(1000):
                xs = [rng.randrange(-(1 << (width-1)), 1 << (width-1)) for _ in range(lanes)]
                ws = [0 if rng.random() < .6 else rng.randrange(-(1 << (width-1)), 1 << (width-1)) for _ in range(lanes)]
                self.assertEqual(bit_decomposition(xs, ws, width, True), dot(xs, ws))

    def test_removed_negative_lane(self):
        self.assertEqual(cycles([-1, 5], [0, 2], 8, 3, False), 9)
        self.assertEqual(cycles([-1, 5], [0, 2], 8, 3, True), 3)
        self.assertEqual(dot([-1, 5], [0, 2]), 10)

    def test_nonzero_negative_lane_cannot_be_removed(self):
        self.assertEqual(cycles([-1, 5], [1, 2], 8, 3, True), 9)

    def test_all_weights_zero(self):
        self.assertEqual(cycles([-128, -1, 127, 42], [0]*4, 8, 3, True), 1)
        self.assertEqual(cycles([-128, -1, 127, 42], [0]*4, 8, 5, True), 1)

    def test_dense_weights_identical_schedule(self):
        for mode in [3, 5]:
            self.assertEqual(cycles([1, 4, 5], [1, -2, 7], 8, mode, True), cycles([1, 4, 5], [1, -2, 7], 8, mode, False))

    def test_span_stronger_than_fixed(self):
        self.assertEqual(cycles([1, 4], [2, 3], 8, 5), 4)
        self.assertEqual(cycles([1, 4], [2, 3], 8, 3), 3)

    def test_qualification_monotonicity(self):
        rng = random.Random(991)
        for _ in range(1000):
            xs = [rng.randrange(-128, 128) for _ in range(8)]
            ws = [rng.choice([0, 0, 1, -1]) for _ in range(8)]
            self.assertTrue(active(xs, ws, 8, True) <= active(xs, ws, 8, False))
            for mode in [3, 5]:
                self.assertLessEqual(cycles(xs, ws, 8, mode, True), cycles(xs, ws, 8, mode, False))

    def test_lane_pack_and_minimum(self):
        self.assertEqual(pack([-1, -8], 4), 0x8f)
        self.assertEqual(bit_decomposition([-128]*4, [-128]*4, 8, True), 65536)

    def test_cancellation_is_not_weight_zero(self):
        self.assertEqual(dot([5, 5], [2, -2]), 0)
        self.assertGreater(cycles([5, 5], [2, -2], 8, 3, True), 1)
