"""Independent hand-computed checks; does not mirror RTL syntax."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reference import arithmetic,encode
from workload import choose_mask,quantize
import numpy as np

class ReferenceTests(unittest.TestCase):
    def test_dense_signed_extremes(self):
        self.assertEqual(arithmetic([-8,-8,-8,-8],[-8,-8,-8,-8],0,0),(256,0))
        self.assertEqual(arithmetic([-8,7,-8,7],[7,-8,7,-8],0,0),(-224,0))
    def test_sparse_indices(self):
        self.assertEqual(arithmetic([2,3,5,7],[-4,6,99,99],12,1),(34,0))
        self.assertEqual(arithmetic([2,3,5,7],[-4,6,99,99],3,2),(18,0))
    def test_pair_all_patterns(self):
        expected=[32,28,48,44]
        for m,v in enumerate(expected):self.assertEqual(arithmetic([2,3,5,7],[-4,8,0,0],m,3),(v,0))
    def test_invalid_metadata(self):
        for m in [0,5,10,15,1,2,3]:self.assertEqual(arithmetic([1]*4,[2]*4,m,1),(0,1))
        for m in [6,7,14,15]:self.assertEqual(arithmetic([1]*4,[2]*4,m,2),(0,1))
    def test_encode_roundtrip(self):
        x=[-8,7,-2,3];w=[5,0,0,-6]
        for mode in [0,1,2,3]:self.assertEqual(arithmetic(*encode(x,w,[0,3],mode),mode),(-58,0))
    def test_mask_energy_optimum_and_pair_penalty(self):
        w=np.tile([10.,9.,2.,1.],(10,16))
        unrestricted=choose_mask(w,'index');pair=choose_mask(w,'pair')
        self.assertEqual(int(unrestricted.sum()),320);self.assertEqual(int(pair.sum()),320)
        self.assertEqual(float(np.square(w[~unrestricted]).sum()),800.)
        self.assertEqual(float(np.square(w[~pair]).sum()),13120.)
    def test_quantization_bounds_and_zero_rows(self):
        w=np.zeros((10,64));w[0,:4]=[-10.,-5.,5.,10.]
        q,scale=quantize(w,4)
        self.assertEqual(q[0,:4].tolist(),[-7,-4,4,7])
        self.assertTrue(np.isfinite(scale).all());self.assertFalse(q[1:].any())

if __name__=='__main__':unittest.main()
