"""Global corners and Pelgrom local mismatch for generated MOSFET instances.

Coefficients are approximate textbook-scale values for a 180 nm-class
process (A_VT ~ 4.5-5 mV.um), not foundry data.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

AVT = {"n": 4.5e-3, "p": 5.0e-3}       # V*um
ABETA = {"n": 0.010, "p": 0.012}      # fraction*um

# name: (dVt_n, dVt_p, mu_n, mu_p); positive dVt slows the device
CORNERS = {
    "tt": (0.0, 0.0, 1.0, 1.0),
    "ff": (-0.045, -0.045, 1.08, 1.08),
    "ss": (0.045, 0.045, 0.92, 0.92),
    "fs": (-0.045, 0.045, 1.08, 0.92),
    "sf": (0.045, -0.045, 0.92, 1.08),
}


@dataclass
class Process:
    corner: str = "tt"
    rng: np.random.Generator | None = None
    record: dict = field(default_factory=dict)
    _draws: dict = field(default_factory=dict, repr=False)

    @classmethod
    def at(cls, corner: str = "tt", seed: int | None = None) -> "Process":
        if corner not in CORNERS:
            raise ValueError(corner)
        return cls(corner, np.random.default_rng(seed) if seed is not None else None)

    def mos(self, name, d, g, s, b, kind, w, l) -> str:
        dvn, dvp, mun, mup = CORNERS[self.corner]
        dvt, mu = (dvn, mun) if kind == "n" else (dvp, mup)
        # The same device name always gets the same mismatch draw, so a
        # device can be instantiated in several half-circuits consistently.
        key = name.split(".")[0]
        if key in self._draws:
            dmm, bmm = self._draws[key]
        else:
            dmm, bmm = 0.0, 1.0
            if self.rng is not None:
                area = w * l * 1e12
                dmm = float(self.rng.normal(0, AVT[kind] / np.sqrt(area)))
                bmm = float(1 + self.rng.normal(0, ABETA[kind] / np.sqrt(area)))
            self._draws[key] = (dmm, bmm)
        self.record[name] = dmm
        tot = dvt + dmm
        delvto = tot if kind == "n" else -tot
        model = "nch" if kind == "n" else "pch"
        inst = name.replace(".", "_")
        return (f"{inst} {d} {g} {s} {b} {model} w={w:.4g} l={l:.4g} "
                f"delvto={delvto:.6g} mulu0={mu * bmm:.6g}")
