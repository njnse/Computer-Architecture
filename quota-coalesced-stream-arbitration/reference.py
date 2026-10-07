"""Independent scheduling model, traffic provenance, and handshake observations."""
from collections import deque
import random

SCENARIOS = ["saturated", "sink_stalls", "asymmetric", "bursty", "light", "phase_change", "reset_stress"]
EVALUATION_SEEDS = [11, 29, 47, 101, 211]


class Reference:
    def __init__(self, n, quota, fixed):
        self.n, self.quota, self.fixed = n, quota, fixed
        self.reset()

    def reset(self):
        self.order = deque(range(self.n))
        self.active, self.budget, self.held = None, 0, None

    def observe(self, valid, ready, reset):
        if reset:
            self.reset()
            return None
        pending = [i for i in self.order if valid[i]]
        if not pending:
            self.budget = 0
            self.held = None
            return None
        if self.held is not None:
            choice = self.held
        elif self.fixed:
            choice = min(pending)
        elif self.budget and valid[self.active]:
            choice = self.active
        else:
            choice = pending[0]
        if not ready:
            self.held = choice
        else:
            self.held = None
            self.budget = self.budget - 1 if self.budget and choice == self.active else self.quota - 1
            self.active = choice
            while self.order[0] != choice:
                self.order.rotate(-1)
            self.order.rotate(-1)
        return choice


def traffic(n, scenario, seed, cycles):
    """Open-loop arrivals, independent of policy; no externally licensed traces."""
    rng = random.Random(seed)
    arrivals, ready, resets = [], [], []
    for t in range(cycles):
        reset = t < 2 or (scenario == "reset_stress" and t % 257 in (0, 1))
        r = True
        a = [0] * n
        if scenario in ("saturated", "sink_stalls", "reset_stress"):
            a = [1] * n
        elif scenario == "asymmetric":
            a = [1 if i == 0 else int(rng.random() < 0.035) for i in range(n)]
        elif scenario == "bursty":
            a = [8 if (t + 17 * i) % 97 == 0 else 0 for i in range(n)]
        elif scenario == "light":
            a = [int(rng.random() < 0.60 / n) for _ in range(n)]
        elif scenario == "phase_change":
            dominant = (t // 512) % n
            a = [int(rng.random() < (0.80 if i == dominant else 0.10 / n)) for i in range(n)]
        elif scenario == "protocol":
            reset = t < 2 or t in (70,71)
            r = not (2 <= t < 10 or 60 <= t < 76)
            if t == 2: a[-1] = 1
            if t == 4: a[0] += 1
            if t == 6: a = [x+1 for x in a]
            if t == 60: a = [4]*n
            if t == 80: a = [2]*n
        if scenario in ("sink_stalls", "reset_stress"):
            # Repeatable long stalls plus independent ready samples.
            r = t % 97 >= 13 and rng.random() < 0.75
        if reset:
            a = [0] * n
        arrivals.append(a); ready.append(r); resets.append(reset)
    return arrivals, ready, resets


def make_vectors(path, n, width, quota, fixed, scenario, seed, cycles=4096, warmup=512):
    arrivals, readies, resets = traffic(n, scenario, seed, cycles)
    model = Reference(n, quota, fixed)
    queues = [deque() for _ in range(n)]
    serial = [0] * n
    wait = [0] * n
    service = [0] * n
    head_latencies, waits = [], []
    switches = fires = stalls = opportunities = arrivals_eval = canceled = 0
    total_fires = total_stalls = 0
    last = None
    coverage = dict(reset_while_pending=0, late_arrival_during_stall=0,
                    all_idle=0, single_pending=0, concurrent_pending=0, sink_stall=0,
                    pointer_wrap=0, quota_runs=0)
    previous_stall = False
    previous_valid = [False] * n
    previous_choice = None
    max_pending_age = 0
    trace = []
    lines = []
    for t in range(cycles):
        reset, ready = resets[t], readies[t]
        if reset:
            pending = sum(len(q) for q in queues)
            if pending:
                coverage["reset_while_pending"] += 1
                canceled += pending
            queues = [deque() for _ in range(n)]
            wait = [0] * n
            last = None
        for i, count in enumerate(arrivals[t]):
            for _ in range(count):
                # Distinct deterministic source streams; WIDTH=1 also tests truncation.
                data = ((serial[i] * 73) ^ (i * 151) ^ (serial[i] >> 3)) & ((1 << width) - 1)
                queues[i].append((data, t))
                serial[i] += 1
                if t >= warmup:
                    arrivals_eval += 1
        valid = [bool(q) for q in queues]
        packed = sum((q[0][0] if q else 0) << (i * width) for i, q in enumerate(queues))
        choice = model.observe(valid, ready, reset)
        ev = choice is not None
        fire = ev and ready
        data = queues[choice][0][0] if ev else 0
        grant = (1 << choice) if fire else 0
        lines.append(f"{int(reset)} {int(ready)} {sum(int(v)<<i for i,v in enumerate(valid)):x} {packed:x} {int(ev)} {choice if ev else 0} {grant:x} {data:x}\n")
        if not reset:
            number = sum(valid)
            coverage["all_idle"] += number == 0
            coverage["single_pending"] += number == 1
            coverage["concurrent_pending"] += number > 1
            coverage["sink_stall"] += ev and not ready
            coverage["late_arrival_during_stall"] += previous_stall and any(v and not p for v, p in zip(valid, previous_valid))
            if fire and previous_choice == n - 1 and choice == 0:
                coverage["pointer_wrap"] += 1
            if fire and previous_choice == choice:
                coverage["quota_runs"] += 1
            if t >= warmup:
                opportunities += ready and number > 0
                stalls += ev and not ready
            for i in range(n):
                if not valid[i]:
                    wait[i] = 0
                elif fire and choice == i:
                    if t >= warmup:
                        waits.append(wait[i])
                    wait[i] = 0
                elif fire:
                    wait[i] += 1
                if not fixed:
                    assert wait[i] <= (n - 1) * quota, (n, quota, scenario, t, i, wait)
                if t >= warmup and valid[i]:
                    max_pending_age = max(max_pending_age, t - queues[i][0][1])
            if fire:
                _, arrival = queues[choice].popleft()
                total_fires += 1
                if t >= warmup:
                    fires += 1
                    service[choice] += 1
                    head_latencies.append(t - arrival)
                    switches += last is not None and last != choice
                    last = choice
                previous_choice = choice
            if ev and not ready:
                total_stalls += 1
        previous_stall, previous_valid = ev and not ready, valid
        if t < 96:
            trace.append(dict(cycle=t, reset=int(reset), ready=int(ready), valid_mask=sum(int(v)<<i for i,v in enumerate(valid)), source=choice, fire=int(fire)))
    path.write_text("".join(lines))
    sorted_lat = sorted(head_latencies)
    sorted_wait = sorted(waits)
    def percentile(values, p):
        return values[min(len(values)-1, int((len(values)-1)*p))] if values else 0
    jain = sum(service)**2/(n*sum(x*x for x in service)) if any(service) else 0
    result = dict(n=n,width=width,quota=quota,fixed=fixed,scenario=scenario,seed=seed,
                  cycles=cycles,warmup=warmup,evaluation_cycles=cycles-warmup,
                  fires=fires,opportunities=opportunities,sink_stalls=stalls,
                  throughput=fires/(cycles-warmup),switches=switches,
                  switches_per_transfer=switches/fires if fires else 0,jain=jain,
                  queue_latency_p50=percentile(sorted_lat,.5),queue_latency_p99=percentile(sorted_lat,.99),
                  serviced_wait_max=max(waits,default=0),serviced_wait_p99=percentile(sorted_wait,.99),
                  max_pending_age=max_pending_age,reset_canceled=canceled,unserved_ports=sum(x==0 for x in service),
                  total_fires=total_fires,total_stalls=total_stalls,
                  service_counts=service,coverage=coverage,trace=trace)
    assert fires == opportunities, "work conservation violated"
    return result


def self_test():
    """Independent closed form and explicit protocol/idle cases, not duplicate runs."""
    for n in (1,3,4,8):
        for q in (1,2,4,8):
            ref = Reference(n,q,False)
            ref.observe([False]*n,False,True)
            got = [ref.observe([True]*n,True,False) for _ in range(2*n*q)]
            assert got == [(t//q)%n for t in range(2*n*q)]
    r = Reference(3,4,False)
    assert r.observe([False,True,False],False,False) == 1
    assert r.observe([True,True,True],False,False) == 1
    assert r.observe([True,True,True],True,False) == 1
    r.observe([False]*3,True,False)
    assert r.observe([True]*3,True,False) == 2, "idle must preserve round-robin history"
    return 17
