"""ATPG flow: random patterns, then PODEM for the remaining faults, then
reverse-order compaction. Reports fault coverage and test efficiency."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from .bench import Circuit
from .faultsim import Fault, FaultSimulator
from .podem import Podem


@dataclass
class AtpgReport:
    circuit: str
    n_pi: int
    n_po: int
    n_flops: int
    n_gates: int
    faults_total: int
    faults_collapsed: int
    detected_random: int
    detected_podem: int
    redundant: int
    aborted: int
    patterns_random_used: int
    patterns_final: int
    coverage_pct: float
    test_efficiency_pct: float
    random_curve: list[tuple[int, float]] = field(default_factory=list)
    runtime_s: float = 0.0
    patterns: list[dict] = field(default_factory=list, repr=False)

    def row(self) -> dict:
        d = dict(self.__dict__)
        d.pop("random_curve")
        d.pop("patterns")
        return d


def random_patterns(pis: list[str], n: int, rng: np.random.Generator) -> list[dict[str, int]]:
    bits = rng.integers(0, 2, size=(n, len(pis)))
    return [{p: int(b) for p, b in zip(pis, row)} for row in bits]


def run_atpg(c: Circuit, n_random: int = 256, batch: int = 32, seed: int = 1,
             backtrack_limit: int = 2000, compact: bool = True) -> AtpgReport:
    t0 = time.time()
    fs = FaultSimulator(c)
    all_f = fs.all_faults()
    faults = fs.collapse(all_f)
    rng = np.random.default_rng(seed)
    remaining = list(faults)
    kept: list[dict] = []
    curve = []
    used = 0
    # random phase: keep a batch only if it detects something new; stop when a batch is useless
    stale = 0
    while used < n_random and remaining:
        pats = random_patterns(fs.pis, batch, rng)
        det, first = fs.run(pats, remaining)
        used += batch
        if det:
            useful = sorted(set(first.values()))
            kept.extend(pats[i] for i in useful)
            remaining = [f for f in remaining if f not in det]
            stale = 0
        else:
            stale += 1
        curve.append((used, 100.0 * (len(faults) - len(remaining)) / len(faults)))
        if stale >= 4:
            break
    det_random = len(faults) - len(remaining)

    # deterministic phase
    pg = Podem(c, backtrack_limit)
    redundant, aborted, det_podem = [], [], 0
    while remaining:
        f = remaining.pop(0)
        status, pat = pg.generate(f)
        if status == "detected":
            det, _ = fs.run([pat], [f] + remaining)
            if f not in det:
                # PODEM fills X with 0; should always detect - keep honest accounting
                aborted.append(f)
                continue
            kept.append(pat)
            det_podem += 1 + len([g for g in remaining if g in det])
            remaining = [g for g in remaining if g not in det]
        elif status == "redundant":
            redundant.append(f)
        else:
            aborted.append(f)

    detected_total = det_random + det_podem
    # reverse-order compaction
    if compact and kept:
        target = [f for f in faults if f not in set(redundant) | set(aborted)]
        final = []
        left = set(target)
        for pat in reversed(kept):
            if not left:
                break
            det, _ = fs.run([pat], list(left))
            if det:
                final.append(pat)
                left -= det
        kept = list(reversed(final))

    n = len(faults)
    return AtpgReport(
        circuit=c.name, n_pi=len(c.inputs), n_po=len(c.outputs), n_flops=len(c.flops),
        n_gates=c.n_gates(), faults_total=len(all_f), faults_collapsed=n,
        detected_random=det_random, detected_podem=det_podem, redundant=len(redundant),
        aborted=len(aborted), patterns_random_used=used, patterns_final=len(kept),
        coverage_pct=100.0 * detected_total / n,
        test_efficiency_pct=100.0 * (detected_total + len(redundant)) / n,
        random_curve=curve, runtime_s=time.time() - t0, patterns=kept,
    )


def coverage_of(c: Circuit, patterns: list[dict]) -> float:
    fs = FaultSimulator(c)
    faults = fs.collapse(fs.all_faults())
    det, _ = fs.run(patterns, faults)
    return 100.0 * len(det) / len(faults)


def undetected_faults(c: Circuit, patterns: list[dict]) -> list[Fault]:
    fs = FaultSimulator(c)
    faults = fs.collapse(fs.all_faults())
    det, _ = fs.run(patterns, faults)
    return [f for f in faults if f not in det]
