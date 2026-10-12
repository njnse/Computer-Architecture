"""Direct arithmetic and independently derived representation/cost models."""
VARIANTS={'parallel':(0,0,'binary'),'tc_fixed':(1,0,'binary'),
          'tc_bitmap':(3,0,'binary'),'tc_counter':(5,0,'binary'),
          'sm_bitmap':(3,1,'binary'),'sm_counter':(5,1,'binary'),
          'booth_bitmap':(3,0,'booth'),'booth_counter':(5,0,'booth')}


def dot(xs,ws):
    if len(xs)!=len(ws):raise ValueError('Mismatched lanes')
    return sum(int(x)*int(w) for x,w in zip(xs,ws))


def pack(xs,width):
    mask=(1<<width)-1
    return sum((int(x)&mask)<<(i*width) for i,x in enumerate(xs))


def booth_digits(x,width):
    # Algebraic overlapping-bit identity, independent of the RTL case table.
    bit=lambda pos: 0 if pos<0 else ((int(x)>>pos)&1)
    return [bit(2*j-1)+bit(2*j)-2*bit(2*j+1) for j in range((width+1)//2)]


def active(xs,ws,width,variant):
    mode,magnitude,representation=VARIANTS[variant]
    positions=set()
    for x,w in zip(xs,ws):
        if int(w)==0:continue
        if representation=='booth':
            positions.update(j for j,d in enumerate(booth_digits(x,width)) if d)
        else:
            value=abs(int(x)) if magnitude else int(x)&((1<<width)-1)
            positions.update(b for b in range(width) if value&(1<<b))
    return positions


def cycles(xs,ws,width,variant):
    mode,magnitude,representation=VARIANTS[variant]
    if mode==0:return 1
    if mode==1:return width+1
    positions=active(xs,ws,width,variant)
    if not positions:return 1
    return (len(positions) if mode==3 else max(positions)-min(positions)+1)+1


def decomposed(xs,ws,width,variant):
    mode,magnitude,representation=VARIANTS[variant]
    result=0
    for x,w in zip(xs,ws):
        x,w=int(x),int(w)
        if representation=='booth':
            result+=sum(d*w*(1<<(2*j)) for j,d in enumerate(booth_digits(x,width)))
        elif magnitude:
            result+=sum(((-w) if x<0 else w)*(1<<j) for j in range(width) if abs(x)&(1<<j))
        else:
            result+=sum((-1 if j==width-1 else 1)*w*(1<<j) for j in range(width) if (x&((1<<width)-1))&(1<<j))
    return result
