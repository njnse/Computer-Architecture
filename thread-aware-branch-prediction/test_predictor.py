import unittest
from experiment import Predictor, trace


class PredictorTests(unittest.TestCase):
    def test_saturation_and_initial_prediction(self):
        p=Predictor(32,0,"shared-local")
        self.assertEqual(p.step(0,0,True),1)
        for _ in range(10):
            p.step(0,0,True)
        self.assertEqual(p.table[0],3)
        for _ in range(10):
            p.step(0,0,False)
        self.assertEqual(p.table[0],0)

    def test_partition_never_touches_other_thread(self):
        p=Predictor(32,4,"partitioned-local")
        before=p.table[8:].copy()
        for _ in range(20):
            p.step(0,0,True)
        self.assertEqual(before,p.table[8:])

    def test_history_isolation(self):
        p=Predictor(32,4,"shared-local")
        p.step(0,0,True)
        self.assertEqual(p.histories,[1,0,0,0])
        self.assertEqual(p.index(1,0),0)

    def test_history_mask(self):
        p=Predictor(32,3,"shared-global")
        for _ in range(10):
            p.step(0,0,True)
        self.assertEqual(p.global_history,7)

    def test_opposite_constant_stream_counterexample(self):
        shared=Predictor(32,0,"shared-local")
        private=Predictor(32,0,"partitioned-local")
        events=[(i%2,0,i%2==0) for i in range(100)]
        self.assertEqual(sum(shared.step(*e) for e in events),100)
        self.assertEqual(sum(private.step(*e) for e in events),1)

    def test_zero_history_global_equals_local(self):
        a=Predictor(32,0,"shared-global")
        b=Predictor(32,0,"shared-local")
        for e in trace(3,"capacity-pressure",16,500):
            self.assertEqual(a.step(*e),b.step(*e))

    def test_trace_reproducibility_and_balance(self):
        events=trace(1,"opposing-bias",256)
        self.assertEqual(events,trace(1,"opposing-bias",256))
        self.assertEqual([sum(t==i for t,p,o in events[2048:]) for i in range(4)],[2048]*4)


if __name__=="__main__":
    unittest.main()
