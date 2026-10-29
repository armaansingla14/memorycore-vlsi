"""Benchmark netlists for the ATPG/scan experiments.

* c17 and s27 are the classic public ISCAS-85/-89 benchmarks.
* The other circuits are generated here: ripple-carry adder, array
  multiplier, magnitude comparator, a small redundant circuit (to exercise
  redundancy identification) and ``acc_ctr``, a sequential accumulator +
  counter used for the scan-insertion example.
"""
from __future__ import annotations

C17 = """# ISCAS-85 c17
INPUT(1)
INPUT(2)
INPUT(3)
INPUT(6)
INPUT(7)
OUTPUT(22)
OUTPUT(23)
10 = NAND(1, 3)
11 = NAND(3, 6)
16 = NAND(2, 11)
19 = NAND(11, 7)
22 = NAND(10, 16)
23 = NAND(16, 19)
"""

S27 = """# ISCAS-89 s27
INPUT(G0)
INPUT(G1)
INPUT(G2)
INPUT(G3)
OUTPUT(G17)
G5 = DFF(G10)
G6 = DFF(G11)
G7 = DFF(G13)
G14 = NOT(G0)
G17 = NOT(G11)
G8 = AND(G14, G6)
G15 = OR(G12, G8)
G16 = OR(G3, G8)
G9 = NAND(G16, G15)
G10 = NOR(G14, G11)
G11 = NOR(G5, G9)
G12 = NOR(G1, G7)
G13 = NOR(G2, G12)
"""


class _B:
    """Tiny netlist builder."""

    def __init__(self, name: str):
        self.name = name
        self.ins: list[str] = []
        self.outs: list[str] = []
        self.lines: list[str] = []
        self.k = 0

    def inp(self, n):
        self.ins.append(n)
        return n

    def out(self, n):
        self.outs.append(n)

    def g(self, typ, *ins, name=None):
        self.k += 1
        n = name or f"n{self.k}"
        self.lines.append(f"{n} = {typ}({', '.join(ins)})")
        return n

    def full_adder(self, a, b, c):
        x = self.g("XOR", a, b)
        s = self.g("XOR", x, c)
        co = self.g("OR", self.g("AND", a, b), self.g("AND", x, c))
        return s, co

    def half_adder(self, a, b):
        return self.g("XOR", a, b), self.g("AND", a, b)

    def text(self):
        hdr = [f"# {self.name} (generated)"]
        hdr += [f"INPUT({i})" for i in self.ins] + [f"OUTPUT({o})" for o in self.outs]
        return "\n".join(hdr + self.lines) + "\n"


def ripple_adder(n: int = 8) -> str:
    b = _B(f"rca{n}")
    a = [b.inp(f"a{i}") for i in range(n)]
    bb = [b.inp(f"b{i}") for i in range(n)]
    c = b.inp("cin")
    for i in range(n):
        s, c = b.full_adder(a[i], bb[i], c)
        b.lines.append(f"s{i} = BUF({s})")
        b.out(f"s{i}")
    b.lines.append(f"cout = BUF({c})")
    b.out("cout")
    return b.text()


def array_multiplier(n: int = 4) -> str:
    b = _B(f"mult{n}x{n}")
    a = [b.inp(f"a{i}") for i in range(n)]
    x = [b.inp(f"b{i}") for i in range(n)]
    pp = [[b.g("AND", a[i], x[j]) for i in range(n)] for j in range(n)]
    # row-by-row carry-save style ripple accumulation
    acc = pp[0][:]  # bits weight j..j+n-1 for row j
    outs = [acc[0]]
    carry_row = acc[1:]
    for j in range(1, n):
        row = pp[j]
        new = []
        c = None
        for i in range(n):
            top = carry_row[i] if i < len(carry_row) else None
            if top is None and c is None:
                new.append(row[i])
            elif top is None:
                s, c = b.half_adder(row[i], c)
                new.append(s)
            elif c is None:
                s, c = b.half_adder(row[i], top)
                new.append(s)
            else:
                s, c = b.full_adder(row[i], top, c)
                new.append(s)
        outs.append(new[0])
        carry_row = new[1:] + ([c] if c is not None else [])
    outs += carry_row
    for k, o in enumerate(outs):
        b.lines.append(f"p{k} = BUF({o})")
        b.out(f"p{k}")
    return b.text()


def comparator(n: int = 4) -> str:
    """a > b, a == b for n-bit unsigned inputs (MSB-first iterative)."""
    b = _B(f"cmp{n}")
    a = [b.inp(f"a{i}") for i in range(n)]
    x = [b.inp(f"b{i}") for i in range(n)]
    gt, eq = None, None
    for i in reversed(range(n)):
        e = b.g("XNOR", a[i], x[i])
        g = b.g("AND", a[i], b.g("NOT", x[i]))
        if gt is None:
            gt, eq = g, e
        else:
            gt = b.g("OR", gt, b.g("AND", eq, g))
            eq = b.g("AND", eq, e)
    b.lines.append(f"gt = BUF({gt})")
    b.lines.append(f"eq = BUF({eq})")
    b.out("gt")
    b.out("eq")
    return b.text()


def redundant_example() -> str:
    """f = a.b + a'.c + b.c (b.c is the redundant consensus term)."""
    return """# redundant consensus example (generated)
INPUT(a)
INPUT(b)
INPUT(c)
OUTPUT(f)
na = NOT(a)
t1 = AND(a, b)
t2 = AND(na, c)
t3 = AND(b, c)
f = OR(t1, t2, t3)
"""


def acc_ctr(n: int = 4) -> str:
    """Sequential: acc <= en ? acc + d : acc ; cnt <= cnt + 1.
    Outputs: eq (acc == cnt), par (XOR of acc), ovf (carry out when en)."""
    b = _B(f"acc_ctr{n}")
    en = b.inp("en")
    d = [b.inp(f"d{i}") for i in range(n)]
    acc = [f"acc{i}" for i in range(n)]
    cnt = [f"cnt{i}" for i in range(n)]
    nen = b.g("NOT", en)
    c = None
    for i in range(n):
        if c is None:
            s, c = b.half_adder(acc[i], d[i])
        else:
            s, c = b.full_adder(acc[i], d[i], c)
        nxt = b.g("OR", b.g("AND", en, s), b.g("AND", nen, acc[i]))
        b.lines.append(f"{acc[i]} = DFF({nxt})")
    ovf = b.g("AND", en, c)
    cc = None
    for i in range(n):
        if cc is None:
            nxt = b.g("NOT", cnt[i])
            cc = cnt[i]
        else:
            nxt = b.g("XOR", cnt[i], cc)
            cc = b.g("AND", cnt[i], cc)
        b.lines.append(f"{cnt[i]} = DFF({nxt})")
    eqs = [b.g("XNOR", acc[i], cnt[i]) for i in range(n)]
    eq = b.g("AND", *eqs)
    par = b.g("XOR", *acc)
    b.lines.append(f"eq = BUF({eq})")
    b.lines.append(f"par = BUF({par})")
    b.lines.append(f"ovf = BUF({ovf})")
    for o in ("eq", "par", "ovf"):
        b.out(o)
    return b.text()


def all_benchmarks() -> dict[str, str]:
    return {
        "c17": C17,
        "s27": S27,
        "rca8": ripple_adder(8),
        "mult4x4": array_multiplier(4),
        "cmp8": comparator(8),
        "cmp16": comparator(16),
        "mult8x8": array_multiplier(8),
        "redundant": redundant_example(),
        "acc_ctr4": acc_ctr(4),
    }
