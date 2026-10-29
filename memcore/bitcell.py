"""6T SRAM bitcell characterization benches (ngspice) and metric extraction.

Cell::

            BL                      BLB
             |                       |
     WL --[MAX1]-- Q ------ QB --[MAX2]-- WL
                   |  \\  /  |
               MPU1/MPD1  MPU2/MPD2  (cross-coupled inverters)

Benches
-------
* butterfly : both inverter halves are broken out and swept with the same
              input source (hold: WL = 0; read: WL = BL = BLB = VDD). The
              static noise margin is the side of the largest square that
              fits in the smaller lobe (Seevinck method).
* write     : cell holds Q = 1, WL = BLB = VDD and BL is swept from VDD to
              0; the write-trip voltage is V(BL) where Q collapses.
* read_i    : read current from the precharged bitline into the cell
              storing 0 (DC, BL held at VDD).
* leakage   : hold state, all supply/bitline currents.
* transient : bitline discharge (read access) and write time.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from .process import Process
from .spice import NgSpice, wrap


@dataclass(frozen=True)
class CellSizing:
    w_pd: float = 0.40e-6
    w_ax: float = 0.24e-6
    w_pu: float = 0.24e-6
    l: float = 0.18e-6

    @property
    def beta(self) -> float:
        return self.w_pd / self.w_ax

    def as_dict(self):
        return asdict(self)


def half(p: Process, s: CellSizing, side: int, inp: str, out: str, bl: str, wl: str, tag: str) -> str:
    """One inverter + access transistor. ``side`` 1 drives Q, 2 drives QB."""
    return "\n".join([
        p.mos(f"MPU{side}.{tag}", out, inp, "vdd", "vdd", "p", s.w_pu, s.l),
        p.mos(f"MPD{side}.{tag}", out, inp, "0", "0", "n", s.w_pd, s.l),
        p.mos(f"MAX{side}.{tag}", bl, wl, out, "0", "n", s.w_ax, s.l),
    ]) + "\n"


def full_cell(p: Process, s: CellSizing, tag: str = "c") -> str:
    return half(p, s, 1, "qb", "q", "bl", "wl", tag) + half(p, s, 2, "q", "qb", "blb", "wl", tag)


# ---------------------------------------------------------------------------
# Benches
# ---------------------------------------------------------------------------

def bench_butterfly(name: str, p: Process, s: CellSizing, vdd: float = 1.8, temp: float = 27.0,
                    modes=("hold", "read"), step: float = 0.005) -> str:
    """One deck, one DC sweep per mode (WL/BL set per mode)."""
    body = (half(p, s, 1, "x", "q", "bl", "wl", "a") + half(p, s, 2, "x", "qb", "blb", "wl", "b")
            + f".temp {temp}\nVDD vdd 0 dc {vdd}\nVX x 0 dc 0\nVWL wl 0 dc 0\n"
            f"VBL bl 0 dc {vdd}\nVBLB blb 0 dc {vdd}\n")
    ctrl = []
    for mode in modes:
        wl = vdd if mode == "read" else 0.0
        ctrl += [f"alter VWL dc = {wl}", f"dc VX 0 {vdd} {step}", f"wrdata {name}_{mode}.dat v(q) v(qb)"]
    return wrap(name, body, "\n".join(ctrl))


def bench_drv(name: str, p: Process, s: CellSizing, vdds, temp: float = 27.0) -> str:
    """Hold butterflies at several supply voltages (data-retention analysis)."""
    body = (half(p, s, 1, "x", "q", "bl", "wl", "a") + half(p, s, 2, "x", "qb", "blb", "wl", "b")
            + f".temp {temp}\nVDD vdd 0 dc 1.8\nVX x 0 dc 0\nVWL wl 0 dc 0\nVBL bl 0 dc 1.8\nVBLB blb 0 dc 1.8\n")
    ctrl = []
    for i, v in enumerate(vdds):
        stp = max(v / 300, 1e-3)
        ctrl += [f"alter VDD dc = {v}", f"alter VBL dc = {v}", f"alter VBLB dc = {v}",
                 f"dc VX 0 {v} {stp:.5g}", f"wrdata {name}_v{i}.dat v(q) v(qb)"]
    return wrap(name, body, "\n".join(ctrl))


def bench_write(name: str, p: Process, s: CellSizing, vdd: float = 1.8, temp: float = 27.0,
                step: float = 0.002) -> str:
    body = full_cell(p, s) + (f".temp {temp}\nVDD vdd 0 dc {vdd}\nVWL wl 0 dc {vdd}\n"
                              f"VBL bl 0 dc {vdd}\nVBLB blb 0 dc {vdd}\n.nodeset v(q)={vdd} v(qb)=0\n")
    ctrl = f"dc VBL {vdd} 0 {-step}\nwrdata {name}_wr.dat v(q) v(qb)\n"
    return wrap(name, body, ctrl)


def bench_dc_currents(name: str, p: Process, s: CellSizing, vdd: float = 1.8, temp: float = 27.0) -> str:
    """Read current (WL on, Q = 0) and hold leakage (WL off) in one deck."""
    body = full_cell(p, s) + (f".temp {temp}\nVDD vdd 0 dc {vdd}\nVWL wl 0 dc {vdd}\n"
                              f"VBL bl 0 dc {vdd}\nVBLB blb 0 dc {vdd}\n.nodeset v(q)=0 v(qb)={vdd}\n")
    ctrl = f"""op
let iread = -i(VBL)
let vread_bump = v(q)
print iread vread_bump
alter VWL dc = 0
op
let ileak_vdd = -i(VDD)
let ileak_bl = -i(VBL) - i(VBLB)
let ileak_total = ileak_vdd + ileak_bl
print ileak_vdd ileak_bl ileak_total
"""
    return wrap(name, body, ctrl)


def bench_transient(name: str, p: Process, s: CellSizing, vdd: float = 1.8, temp: float = 27.0,
                    c_bl: float = 100e-15) -> str:
    """Read: BL precharged (cap) discharges through the cell storing 0.
    Write: second cell instance (storing 1) gets BL driven low."""
    rd = _rename_nodes(full_cell(p, s, "r"), {"bl": "blr", "blb": "blbr", "q": "qr", "qb": "qbr"})
    wr = _rename_nodes(full_cell(p, s, "w"), {"bl": "blw", "blb": "blbw", "q": "qw", "qb": "qbw"})
    body = (rd + wr +
            f""".temp {temp}
VDD vdd 0 dc {vdd}
VWL wl 0 pwl(0 0 1n 0 1.05n {vdd})
Cblr blr 0 {c_bl}
Cblbr blbr 0 {c_bl}
Vblw blw 0 pwl(0 {vdd} 0.9n {vdd} 0.95n 0)
Vblbw blbw 0 dc {vdd}
.ic v(blr)={vdd} v(blbr)={vdd} v(qr)=0 v(qbr)={vdd} v(qw)={vdd} v(qbw)=0
""")
    ctrl = f"""tran 1p 6n 0 2p uic
linearize v(blr) v(blbr) v(qw) v(qbw) v(wl)
wrdata {name}_tr.dat v(blr) v(blbr) v(qw) v(qbw) v(wl)
"""
    return wrap(name, body, ctrl)


def _rename_nodes(text: str, mapping: dict[str, str]) -> str:
    out = []
    for line in text.splitlines():
        toks = line.split()
        if toks and toks[0].upper().startswith("M"):
            toks = [toks[0]] + [mapping.get(t, t) for t in toks[1:5]] + toks[5:]
        out.append(" ".join(toks))
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Metric extraction
# ---------------------------------------------------------------------------

def snm_from_vtc(x: np.ndarray, q: np.ndarray, qb: np.ndarray, n: int = 2001) -> tuple[float, float, float]:
    """Static noise margin from the two half-cell transfer curves.

    ``q = f1(x)`` (Q vs QB) and ``qb = f2(x)`` (QB vs Q). In the butterfly
    plane (horizontal = QB, vertical = Q), curve 1 is (x, f1(x)) and curve 2
    is (f2(y), y). For every 45-degree line Q = QB + c, the horizontal
    distance between the two curves equals the side of the square whose
    diagonal lies on that line. Returns (snm, lobe1, lobe2).
    """
    x = np.asarray(x, float)
    # curve 1: c = f1(x) - x is monotonically decreasing in x
    c1 = q - x
    # curve 2: points (f2(y), y) -> c = y - f2(y) increasing in y
    c2 = x - qb
    cmin = max(c1.min(), c2.min())
    cmax = min(c1.max(), c2.max())
    cs = np.linspace(cmin, cmax, n)
    o1 = np.argsort(c1)
    x1 = np.interp(cs, c1[o1], x[o1])           # horizontal coordinate of curve 1
    o2 = np.argsort(c2)
    x2 = np.interp(cs, c2[o2], qb[o2])          # horizontal coordinate of curve 2 (= f2(y))
    d = x2 - x1
    if not is_bistable(x, q, qb):
        return 0.0, 0.0, 0.0
    # metastable intersection: the sign change of d nearest to c = 0 (values
    # below eps are treated as zero so numerical noise on a symmetric cell
    # does not create spurious crossings)
    eps = 1e-6 * max(1.0, float(np.abs(x).max()))
    nz = np.where(np.abs(d) > eps)[0]
    if len(nz) < 2:
        return 0.0, 0.0, 0.0
    sg = np.sign(d[nz])
    tr = np.where(sg[:-1] != sg[1:])[0]
    if len(tr) == 0:
        return 0.0, 0.0, 0.0
    cmid = 0.5 * (cs[nz[tr]] + cs[nz[tr + 1]])
    j = tr[int(np.argmin(np.abs(cmid)))]
    lobe1 = _run_max(d, nz[j], -1)
    lobe2 = _run_max(d, nz[j + 1], +1)
    return min(lobe1, lobe2), lobe1, lobe2


def _run_max(d: np.ndarray, start: int, step: int) -> float:
    s0 = np.sign(d[start])
    best = 0.0
    i = start
    while 0 <= i < len(d) and np.sign(d[i]) in (s0, 0):
        best = max(best, abs(d[i]))
        i += step
    return float(best)


def is_bistable(x: np.ndarray, q: np.ndarray, qb: np.ndarray) -> bool:
    """True if the closed loop Q -> QB -> Q has an unstable (regenerative) fixed point.

    g(Q) = f1(f2(Q)) - Q crosses zero upward only at a fixed point with loop
    gain > 1, which exists exactly when the latch has two stable states.
    """
    g = np.interp(qb, x, q) - x          # f2 gives QB(Q=x); f1 maps it back to Q
    s = np.sign(g[np.abs(g) > 1e-9])     # drop exact zeros (fixed point on a grid node)
    return bool(np.any((s[:-1] < 0) & (s[1:] > 0)))


def write_trip(vbl: np.ndarray, q: np.ndarray, vdd: float) -> float:
    """BL voltage at which Q falls through VDD/2 (sweep runs from VDD downward)."""
    below = np.where(q < vdd / 2)[0]
    if len(below) == 0:
        return 0.0  # never flipped: write failure
    i = below[0]
    if i == 0:
        return float(vbl[0])
    f = (q[i - 1] - vdd / 2) / (q[i - 1] - q[i])
    return float(vbl[i - 1] + f * (vbl[i] - vbl[i - 1]))


def cross_time(t: np.ndarray, v: np.ndarray, level: float, t_from: float = 0.0, falling=True) -> float:
    m = t >= t_from
    t, v = t[m], v[m]
    s = v - level
    idx = np.where((s[:-1] > 0) & (s[1:] <= 0))[0] if falling else np.where((s[:-1] < 0) & (s[1:] >= 0))[0]
    if len(idx) == 0:
        return float("nan")
    i = idx[0]
    return float(t[i] + (t[i + 1] - t[i]) * s[i] / (s[i] - s[i + 1]))


# ---------------------------------------------------------------------------
# High-level characterization
# ---------------------------------------------------------------------------

def characterize(sim: NgSpice, items: dict[str, tuple[Process, CellSizing, float, float]],
                 transient: bool = False) -> dict[str, dict]:
    """items: tag -> (process, sizing, vdd, temp). Runs butterfly, write, DC currents."""
    jobs = {}
    for tag, (p, s, vdd, temp) in items.items():
        jobs[f"{tag}_bf"] = bench_butterfly(f"{tag}_bf", p, s, vdd, temp)
        jobs[f"{tag}_wr"] = bench_write(f"{tag}_wr", p, s, vdd, temp)
        jobs[f"{tag}_dc"] = bench_dc_currents(f"{tag}_dc", p, s, vdd, temp)
        if transient:
            jobs[f"{tag}_tr"] = bench_transient(f"{tag}_tr", p, s, vdd, temp)
    res = sim.run(jobs)
    out = {}
    for tag, (p, s, vdd, temp) in items.items():
        m = {"vdd": vdd, "temp_c": temp, "corner": p.corner, "beta": s.beta}
        for mode in ("hold", "read"):
            t = res[f"{tag}_bf"].table(f"{tag}_bf_{mode}.dat")
            snm, l1, l2 = snm_from_vtc(t["v-sweep"], t["v(q)"], t["v(qb)"])
            m[f"{mode}_snm_mv"] = snm * 1e3
        w = res[f"{tag}_wr"].table(f"{tag}_wr_wr.dat")
        m["write_trip_mv"] = write_trip(w["v-sweep"], w["v(q)"], vdd) * 1e3
        sc = res[f"{tag}_dc"].scalars
        m["read_current_ua"] = sc["iread"] * 1e6
        m["read_bump_mv"] = sc["vread_bump"] * 1e3
        m["leak_total_pa"] = sc["ileak_total"] * 1e12
        m["leak_vdd_pa"] = sc["ileak_vdd"] * 1e12
        m["leak_bl_pa"] = sc["ileak_bl"] * 1e12
        if transient:
            tr = res[f"{tag}_tr"].table(f"{tag}_tr_tr.dat")
            tt = tr["time"]
            t_wl = cross_time(tt, tr["v(wl)"], vdd / 2, 0, falling=False)
            dv = tr["v(blbr)"] - tr["v(blr)"]
            t100 = cross_time(tt, -dv, -0.1, t_wl)  # dv rising through 100 mV
            t_wr = cross_time(tt, tr["v(qw)"], vdd / 2, t_wl)
            m["read_100mv_ps"] = (t100 - t_wl) * 1e12
            m["write_time_ps"] = (t_wr - t_wl) * 1e12
        out[tag] = m
    return out


def drv(sim: NgSpice, items: dict[str, tuple[Process, CellSizing]], vdds, temp: float = 27.0) -> dict:
    """Hold SNM vs VDD for each item; DRV = lowest VDD at which hold SNM > 0."""
    jobs = {tag: bench_drv(tag, p, s, vdds, temp) for tag, (p, s) in items.items()}
    res = sim.run(jobs)
    out = {}
    for tag in items:
        snms = []
        for i, _ in enumerate(vdds):
            t = res[tag].table(f"{tag}_v{i}.dat")
            snms.append(snm_from_vtc(t["v-sweep"], t["v(q)"], t["v(qb)"])[0])
        snms = np.array(snms)
        ok = [v for v, sn in zip(vdds, snms) if sn > 1e-3]
        # lowest VDD such that this and all higher grid points are bistable
        drv_v = float("nan")
        for v, sn in sorted(zip(vdds, snms), reverse=True):
            if sn > 1e-3:
                drv_v = v
            else:
                break
        out[tag] = {"vdd": np.asarray(vdds), "hold_snm": snms, "drv_v": drv_v, "n_ok": len(ok)}
    return out
