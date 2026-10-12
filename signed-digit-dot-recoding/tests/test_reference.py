import itertools
import random
import unittest
from reference import VARIANTS,booth_digits,cycles,decomposed,dot,pack


class ReferenceTests(unittest.TestCase):
    def test_exhaustive_two_lane_representations(self):
        for values in itertools.product(range(-4,4),repeat=4):
            xs,ws=values[:2],values[2:]
            for v in ['tc_bitmap','sm_bitmap','booth_bitmap']:
                self.assertEqual(decomposed(xs,ws,3,v),dot(xs,ws))

    def test_booth_all_odd_even_values(self):
        for width in range(2,10):
            for x in range(-(1<<(width-1)),1<<(width-1)):
                self.assertEqual(sum(d*(1<<(2*j)) for j,d in enumerate(booth_digits(x,width))),x)

    def test_signed_random_groups(self):
        rng=random.Random(4242)
        for width,n in itertools.product([4,8],[1,4,8]):
            for _ in range(1000):
                xs=[rng.randrange(-(1<<(width-1)),1<<(width-1)) for _ in range(n)]
                ws=[0 if rng.random()<.5 else rng.randrange(-(1<<(width-1)),1<<(width-1)) for _ in range(n)]
                for v in ['tc_bitmap','sm_bitmap','booth_bitmap']:
                    self.assertEqual(decomposed(xs,ws,width,v),dot(xs,ws))

    def test_minimum_activation_and_weight(self):
        for v in VARIANTS:self.assertEqual(decomposed([-128]*4,[-128]*4,8,v),65536)

    def test_minus_one_failure_and_recoding(self):
        self.assertEqual(cycles([-1]*4,[1]*4,8,'tc_bitmap'),9)
        self.assertEqual(cycles([-1]*4,[1]*4,8,'sm_bitmap'),2)
        self.assertEqual(cycles([-1]*4,[1]*4,8,'booth_bitmap'),2)

    def test_positive_no_magnitude_cycle_gain(self):
        for x in range(128):
            self.assertEqual(cycles([x],[7],8,'tc_bitmap'),cycles([x],[7],8,'sm_bitmap'))

    def test_booth_can_be_better_or_worse(self):
        self.assertLess(cycles([7],[1],8,'booth_bitmap'),cycles([7],[1],8,'sm_bitmap'))
        self.assertGreater(cycles([2],[1],8,'booth_bitmap'),cycles([2],[1],8,'sm_bitmap'))

    def test_zero_weight_and_cancellation(self):
        for v in ['tc_bitmap','sm_bitmap','booth_bitmap']:
            self.assertEqual(cycles([-128,127],[0,0],8,v),1)
            self.assertGreater(cycles([5,5],[2,-2],8,v),1)
            self.assertEqual(decomposed([5,5],[2,-2],8,v),0)

    def test_odd_width_top_sign_extension(self):
        self.assertEqual(booth_digits(-4,3),[0,-1])
        self.assertEqual(booth_digits(3,3),[-1,1])

    def test_pack_lane_order(self):
        self.assertEqual(pack([-1,-8],4),0x8f)
