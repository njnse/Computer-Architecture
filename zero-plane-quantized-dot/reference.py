"""Independent signed integer math and bit-density analysis."""
def dot(x,w):
    return sum(a*b for a,b in zip(x,w))

def planes(x,width,mode):
    u=0
    for a in x:u|=int(a)&((1<<width)-1)
    return 0 if mode==0 else width if mode==1 else u.bit_length() if mode==2 else (u.bit_length()-(u&-u).bit_length()+1 if u else 0) if mode in [4,5] else u.bit_count()

def pack(values,width):
    return sum((v&((1<<width)-1))<<(i*width) for i,v in enumerate(values))

def bit_dot(x,w,width):
    return sum(sum(weight for a,weight in zip(x,w) if (a&((1<<width)-1))&(1<<b))*(1<<b)*(-1 if b==width-1 else 1) for b in range(width))
