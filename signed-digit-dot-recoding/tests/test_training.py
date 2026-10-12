import unittest
import numpy as np
from train_models import loss_and_grad


class TrainingGradientTests(unittest.TestCase):
    def test_independent_finite_difference(self):
        rng=np.random.default_rng(119)
        x=rng.normal(size=(5,4));y=np.array([0,1,1,0,1])
        p={'w1':rng.normal(size=(4,3))*.2,'b1':rng.normal(size=3)*.2,
           'w2':rng.normal(size=(3,2))*.2,'b2':rng.normal(size=2)*.2}
        for activation in ['tanh','relu']:
            _,grads=loss_and_grad(x,y,p,activation)
            for k in p:
                for idx in np.ndindex(p[k].shape):
                    old=p[k][idx];eps=1e-6
                    p[k][idx]=old+eps;plus=loss_and_grad(x,y,p,activation)[0]
                    p[k][idx]=old-eps;minus=loss_and_grad(x,y,p,activation)[0]
                    p[k][idx]=old
                    self.assertAlmostEqual((plus-minus)/(2*eps),grads[k][idx],places=6)
