import itertools,random,unittest
from reference import dot,planes,bit_dot,pack
class Arithmetic(unittest.TestCase):
 def test_exhaustive_signed(self):
  for x,w in itertools.product(range(-8,8),repeat=2):self.assertEqual(dot([x],[w]),bit_dot([x],[w],4))
 def test_random_groups(self):
  r=random.Random(4242)
  for n in [1,4,8]:
   for _ in range(2000):
    x=[r.randrange(-128,128) for _ in range(n)];w=[r.randrange(-128,128) for _ in range(n)]
    self.assertEqual(dot(x,w),bit_dot(x,w,8))
 def test_signed_top(self):self.assertEqual(bit_dot([-128,127],[-128,-128],8),128)
 def test_union_not_sum(self):self.assertEqual(planes([1,4,0,1],8,3),2)
 def test_internal_holes(self):self.assertEqual((planes([5],8,2),planes([5],8,3)),(3,2))
 def test_zero(self):self.assertEqual([planes([0]*4,8,m) for m in range(4)],[0,8,0,0])
 def test_negative_dense(self):self.assertEqual(planes([-1]*4,8,3),8)
 def test_packing(self):self.assertEqual(pack([-1,-8,7],4),0x78f)
if __name__=='__main__':unittest.main()
