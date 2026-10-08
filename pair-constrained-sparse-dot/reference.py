"""Independent integer arithmetic and FIFO-based cycle reference."""
from collections import deque
import itertools,random

NAMES=['dense','index','code','pair','fixed']
PAIRS=list(itertools.combinations(range(4),2))

def pack(values,width):
    return sum((int(v)&((1<<width)-1))<<(i*width) for i,v in enumerate(values))

def arithmetic(x,w,meta,mode):
    expanded=[0]*4
    if mode==0:
        expanded=list(w)
    else:
        if mode==1:
            selected=[meta%4,meta//4]
            if selected[0]>=selected[1]: return 0,1
        elif mode==2:
            if meta%8>=6:return 0,1
            selected=PAIRS[meta%8]
        elif mode==3:selected=[meta%2,2+(meta//2)%2]
        else:selected=[0,2]
        for position,value in zip(selected,w):expanded[position]=value
    return sum(a*b for a,b in zip(x,expanded)),0

def encode(x,w,positions,mode):
    if mode==0:return x,w,0
    meta=(positions[0]+4*positions[1] if mode==1 else PAIRS.index(tuple(positions)) if mode==2 else positions[0]+2*(positions[1]-2) if mode==3 else 0)
    return x,[w[positions[0]],w[positions[1]],0,0],meta

def random_transactions(width,seed,count):
    r=random.Random(seed)
    lo,hi=-(1<<(width-1)),(1<<(width-1))-1
    choices=[lo,hi,0,1,-1]
    for n in range(count):
        vals=[r.choice(choices) if n%3==0 else r.randint(lo,hi) for _ in range(8)]
        yield vals[:4],vals[4:],n%16

def exhaustive_transactions(mode):
    values=range(-2,2)
    if mode==0:
        for v in itertools.product(values,repeat=8):yield list(v[:4]),list(v[4:]),0
    else:
        metas=(range(16) if mode==1 else range(8) if mode==2 else range(4) if mode==3 else [0])
        for meta in metas:
            for v in itertools.product(values,repeat=6):yield list(v[:4]),list(v[4:])+[0,0],meta

def write_vectors(path,width,mode,transactions,traffic='continuous',seed=7,resets=False):
    """Drive a compliant held-until-accepted source and model a one-entry FIFO."""
    r=random.Random(seed)
    stream=iter(transactions)
    pending=None
    exhausted=False
    queue=deque()
    cycle=0
    rows=0
    with path.open('w') as f:
        while True:
            rst=int(cycle<2 or (resets and cycle in (103,104,777,1337)))
            if pending is None and not exhausted and (traffic=='continuous' or r.random()<0.75):
                try:pending=next(stream)
                except StopIteration:exhausted=True
            ready=(1 if traffic=='continuous' else int(cycle%53>=17 and r.random()<0.65))
            if exhausted:ready=1
            valid=int(pending is not None)
            x,w,meta=pending if pending is not None else ([0]*4,[0]*4,0)
            sr=int(not rst and (not queue or ready))
            mv=int(not rst and bool(queue))
            md,me=queue[0] if queue else (0,0)
            f.write(f'{rst} {valid} {ready} {pack(x,width):x} {pack(w,width):x} {meta:x} {sr} {mv} {md} {me}\n')
            if rst:queue.clear()
            else:
                if mv and ready:queue.popleft()
                if valid and sr:
                    queue.append(arithmetic(x,w,meta,mode))
                    pending=None
            cycle+=1;rows+=1
            if exhausted and pending is None and not queue:break
            if cycle>10000000:raise RuntimeError('Reference failed to drain')
        # Check the drained state after the final transfer.
        f.write('0 0 1 0 0 0 1 0 0 0\n')
    return rows+1
