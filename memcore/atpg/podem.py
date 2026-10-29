"""PODEM deterministic test generation for single stuck-at faults.

Values are kept as (good, faulty) pairs over {0, 1, X}; the D-calculus
values are D = (1, 0) and D' = (0, 1). Decisions are made only on
(pseudo) primary inputs; implication is a full three-valued simulation of
the good and the faulty circuit, which is adequate for the small netlists
in this project.
"""
from __future__ import annotations

from .bench import Circuit
from .faultsim import CTRL, Fault

X = 2
INVERTING = {"NAND", "NOR", "NOT", "XNOR"}


def _eval3(typ: str, vals: list[int]) -> int:
    if typ in ("AND", "NAND"):
        r = 0 if 0 in vals else (X if X in vals else 1)
    elif typ in ("OR", "NOR"):
        r = 1 if 1 in vals else (X if X in vals else 0)
    elif typ in ("XOR", "XNOR"):
        if X in vals:
            return X
        r = sum(vals) & 1
    elif typ in ("NOT", "BUF"):
        r = vals[0]
    else:
        raise ValueError(typ)
    if r == X:
        return X
    return r ^ 1 if typ in INVERTING else r


class Podem:
    def __init__(self, circuit: Circuit, backtrack_limit: int = 2000):
        self.c = circuit
        self.pis = circuit.pseudo_inputs
        self.pos = circuit.pseudo_outputs
        self.limit = backtrack_limit
        self.fo = circuit.fanout()

    def _imply(self, assign: dict[str, int], f: Fault):
        good = dict(assign)
        bad = dict(assign)
        if f.gate is None and f.net in bad:
            bad[f.net] = f.stuck
        for out in self.c.order:
            g = self.c.gates[out]
            good[out] = _eval3(g.type, [good[i] for i in g.ins])
            fins = [bad[i] for i in g.ins]
            if f.gate == out:
                fins[f.pin] = f.stuck
            bad[out] = _eval3(g.type, fins)
            if f.gate is None and f.net == out:
                bad[out] = f.stuck
        return good, bad

    def _detected(self, good, bad) -> bool:
        return any(good[o] != X and bad[o] != X and good[o] != bad[o] for o in self.pos)

    def _d_frontier(self, good, bad, f: Fault) -> list[str]:
        front = []
        for out in self.c.order:
            if good[out] != X and bad[out] != X:
                continue
            g = self.c.gates[out]
            for k, i in enumerate(g.ins):
                gi, bi = good[i], bad[i]
                if f.gate == out and f.pin == k:
                    bi = f.stuck
                if gi != X and bi != X and gi != bi:
                    front.append(out)
                    break
        return front

    def _objective(self, good, bad, f: Fault):
        site = f.net
        if good[site] == X:
            return site, 1 - f.stuck
        if good[site] == f.stuck:
            return None
        front = self._d_frontier(good, bad, f)
        if not front:
            return None
        # prefer the D-frontier gate closest to an output (last in topo order)
        out = front[-1]
        g = self.c.gates[out]
        nc = 1 - CTRL[g.type][0] if g.type in CTRL else 0
        for i in g.ins:
            if good[i] == X:
                return i, nc
        return None

    def _backtrace(self, net: str, v: int, good) -> tuple[str, int]:
        while net not in self.pis:
            g = self.c.gates[net]
            if g.type in INVERTING:
                v ^= 1
            nxt = None
            for i in g.ins:
                if good[i] == X:
                    nxt = i
                    break
            if nxt is None:
                nxt = g.ins[0]
            if g.type in ("XOR", "XNOR"):
                known = sum(good[i] for i in g.ins if good[i] != X and i != nxt) & 1
                v ^= known
            net = nxt
        return net, v

    def generate(self, f: Fault):
        """Return (status, pattern). status in {'detected', 'redundant', 'aborted'}."""
        assign = {p: X for p in self.pis}
        stack: list[tuple[str, int, bool]] = []
        backtracks = 0
        while True:
            good, bad = self._imply(assign, f)
            if self._detected(good, bad):
                return "detected", {p: (0 if v == X else v) for p, v in assign.items()}
            obj = self._objective(good, bad, f)
            if obj is not None:
                pi, v = self._backtrace(obj[0], obj[1], good)
                if assign[pi] == X:
                    assign[pi] = v
                    stack.append((pi, v, False))
                    continue
            # backtrack
            while stack:
                pi, v, flipped = stack.pop()
                if not flipped:
                    backtracks += 1
                    if backtracks > self.limit:
                        return "aborted", None
                    assign[pi] = 1 - v
                    stack.append((pi, 1 - v, True))
                    break
                assign[pi] = X
            else:
                return "redundant", None
