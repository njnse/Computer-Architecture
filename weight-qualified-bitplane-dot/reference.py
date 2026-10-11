"""Independent exact arithmetic and scheduler-cost checks."""
def dot(xs, ws):
    if len(xs) != len(ws):
        raise ValueError("Mismatched lanes")
    return sum(int(x) * int(w) for x, w in zip(xs, ws))


def pack(xs, width):
    mask = (1 << width) - 1
    return sum((int(x) & mask) << (i * width) for i, x in enumerate(xs))


def active(xs, ws, width, qualified=False):
    mask = (1 << width) - 1
    positions = set()
    for x, w in zip(xs, ws):
        if qualified and int(w) == 0:
            continue
        positions.update(b for b in range(width) if (int(x) & mask) & (1 << b))
    return positions


def cycles(xs, ws, width, mode, qualified=False):
    if mode == 0:
        return 1
    if mode == 1:
        return width + 1
    positions = active(xs, ws, width, qualified)
    if not positions:
        return 1
    if mode == 3:
        return len(positions) + 1
    if mode == 5:
        return max(positions) - min(positions) + 2
    raise ValueError("Unsupported mode")


def bit_decomposition(xs, ws, width, qualified=False):
    result = 0
    for b in sorted(active(xs, ws, width, qualified)):
        subtotal = sum(int(w) for x, w in zip(xs, ws) if int(x) & (1 << b))
        result += (-1 if b == width - 1 else 1) * (subtotal << b)
    return result
