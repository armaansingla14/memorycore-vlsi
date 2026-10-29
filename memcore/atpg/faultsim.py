"""Bit-parallel logic simulation and single stuck-at fault simulation.

Patterns are packed into Python integers (bit k = pattern k), so one pass
evaluates up to thousands of patterns. The circuit is simulated in its
full-scan combinational view (pseudo PIs/POs, see bench.Circuit).

Fault model: single stuck-at on lines. Every net has a *stem* line; nets
with fanout > 1 also have one *branch* line per fanout pin. Equivalence
collapsing removes, for each gate, the input faults that are equivalent to
an output fault (controlling-value faults of AND/NAND/OR/NOR, all input
faults of NOT/BUF).
"""
from __future__ import annotations

from dataclasses import dataclass

from .bench import Circuit

CTRL = {"AND": (0, 0), "NAND": (0, 1), "OR": (1, 0), "NOR": (1, 1)}  # (controlling value, inversion)


@dataclass(frozen=True)
class Fault:
    net: str
    stuck: int
    gate: str | None = None   # for a branch fault: the reading gate's output net
    pin: int = -1             # ... and its input index

    def __str__(self):
        loc = self.net if self.gate is None else f"{self.net}->{self.gate}.{self.pin}"
        return f"{loc}/sa{self.stuck}"


def eval_gate(typ: str, vals: list[int], mask: int) -> int:
    if typ == "AND" or typ == "NAND":
        r = mask
        for v in vals:
            r &= v
        return r if typ == "AND" else ~r & mask
    if typ == "OR" or typ == "NOR":
        r = 0
        for v in vals:
            r |= v
        return r if typ == "OR" else ~r & mask
    if typ == "XOR" or typ == "XNOR":
        r = 0
        for v in vals:
            r ^= v
        return r if typ == "XOR" else ~r & mask
    if typ == "NOT":
        return ~vals[0] & mask
    if typ == "BUF":
        return vals[0]
    raise ValueError(typ)


class FaultSimulator:
    def __init__(self, circuit: Circuit):
        self.c = circuit
        self.pis = circuit.pseudo_inputs
        self.pos = circuit.pseudo_outputs
        self.fo = circuit.fanout()
        self.pos_index = {}
        for i, n in enumerate(self.pos):
            self.pos_index.setdefault(n, []).append(i)
        self._pos_set = set(self.pos)
        self._cone: dict[str, list[str]] = {}
        self._rank = {n: i for i, n in enumerate(circuit.order)}

    # ------------------------------------------------------------------ faults
    def all_faults(self) -> list[Fault]:
        faults = []
        nets = list(self.pis) + list(self.c.order)
        for n in nets:
            for v in (0, 1):
                faults.append(Fault(n, v))
            fo = self.fo.get(n, [])
            if len(fo) > 1 or (fo and n in self._pos_set):
                for g, k in fo:
                    for v in (0, 1):
                        faults.append(Fault(n, v, g, k))
        return faults

    def collapse(self, faults: list[Fault]) -> list[Fault]:
        drop = set()
        for out in self.c.order:
            g = self.c.gates[out]
            for k, i in enumerate(g.ins):
                fo = self.fo.get(i, [])
                branch = len(fo) > 1 or (fo and i in self._pos_set)
                line = (lambda v, i=i, k=k, out=out: Fault(i, v, out, k)) if branch else (lambda v, i=i: Fault(i, v))
                if g.type in CTRL:
                    c, _ = CTRL[g.type]
                    drop.add(line(c))
                elif g.type in ("NOT", "BUF"):
                    drop.add(line(0))
                    drop.add(line(1))
        return [f for f in faults if f not in drop]

    # ------------------------------------------------------------- simulation
    def simulate(self, pi_words: dict[str, int], mask: int, fault: Fault | None = None,
                 good: dict[str, int] | None = None) -> dict[str, int]:
        """Evaluate all nets. With ``fault`` and ``good`` given, only the fault's
        forward cone is re-evaluated."""
        if fault is None:
            v = dict(pi_words)
            for out in self.c.order:
                g = self.c.gates[out]
                v[out] = eval_gate(g.type, [v[i] for i in g.ins], mask)
            return v
        v = dict(good)
        const = mask if fault.stuck else 0
        if fault.gate is None:
            v[fault.net] = const
            cone = self.cone(fault.net)
        else:
            cone = [fault.gate] + self.cone(fault.gate)
        for out in cone:
            g = self.c.gates[out]
            ins = [v[i] for i in g.ins]
            if fault.gate == out:
                ins[fault.pin] = const
            v[out] = eval_gate(g.type, ins, mask)
            if fault.gate is None and out == fault.net:
                v[out] = const
        return v

    def cone(self, net: str) -> list[str]:
        """Gates (by output net) in the transitive fanout of ``net``, topological order."""
        hit = self._cone.get(net)
        if hit is not None:
            return hit
        seen = set()
        stack = [g for g, _ in self.fo.get(net, [])]
        while stack:
            g = stack.pop()
            if g in seen:
                continue
            seen.add(g)
            stack.extend(x for x, _ in self.fo.get(g, []))
        cone = sorted(seen, key=self._rank.__getitem__)
        self._cone[net] = cone
        return cone

    def detects(self, fault: Fault, good: dict[str, int], mask: int) -> int:
        """Bit mask of patterns that detect ``fault``."""
        bad = self.simulate({}, mask, fault, good)
        diff = 0
        for o in self.pos:
            diff |= good[o] ^ bad[o]
        return diff & mask

    def run(self, patterns: list[dict[str, int]], faults: list[Fault], drop: bool = True):
        """Fault-simulate a list of patterns (each pattern: net -> 0/1).

        Returns (detected set, first-detecting pattern index per fault).
        """
        first: dict[Fault, int] = {}
        remaining = list(faults)
        for base in range(0, len(patterns), 256):
            chunk = patterns[base:base + 256]
            mask = (1 << len(chunk)) - 1
            words = {n: 0 for n in self.pis}
            for k, pat in enumerate(chunk):
                for n in self.pis:
                    if pat.get(n, 0):
                        words[n] |= 1 << k
            good = self.simulate(words, mask)
            still = []
            for f in remaining:
                d = self.detects(f, good, mask)
                if d:
                    first[f] = base + (d & -d).bit_length() - 1
                    if not drop:
                        still.append(f)
                else:
                    still.append(f)
            remaining = still
        return set(first), first

    def responses(self, pattern: dict[str, int]) -> dict[str, int]:
        words = {n: pattern.get(n, 0) for n in self.pis}
        v = self.simulate(words, 1)
        return {o: v[o] for o in self.pos}
