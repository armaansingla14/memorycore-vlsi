"""6T SRAM bitcell characterization in ngspice: nominal, PVT, sizing sweeps,
Monte Carlo and data-retention voltage. Writes results/bitcell_* and plots."""
from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from memcore import bitcell as bc  # noqa: E402
from memcore.process import CORNERS, Process  # noqa: E402
from memcore.spice import NgSpice  # noqa: E402

RES = ROOT / "results"
PLOTS = RES / "plots"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
INK2, GRID = "#52514e", "#e4e3df"


def write_csv(name, rows):
    keys = list(rows[0])
    with open(RES / name, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.6g}" if isinstance(v, float) else v) for k, v in r.items()})


def md(rows, cols):
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(
            (f"{r[c]:.4g}" if isinstance(r[c], float) and not math.isnan(r[c]) else str(r[c])) for c in cols) + " |")
    return "\n".join(out)


def style(ax, xl, yl, title):
    ax.set_xlabel(xl, color=INK2)
    ax.set_ylabel(yl, color=INK2)
    ax.set_title(title, fontsize=10, loc="left")
    ax.grid(True, color=GRID, lw=0.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=INK2, labelsize=8)


def save(fig, name):
    PLOTS.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(PLOTS / name, dpi=90)
    plt.close(fig)


def stats(vals):
    a = np.asarray(vals, float)
    return {"n": int(a.size), "mean": float(a.mean()), "std": float(a.std(ddof=1)),
            "min": float(a.min()), "max": float(a.max()),
            "mean_minus_3sigma": float(a.mean() - 3 * a.std(ddof=1))}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc", type=int, default=500)
    ap.add_argument("--drv-mc", type=int, default=100)
    args = ap.parse_args(argv)
    RES.mkdir(exist_ok=True)
    sim = NgSpice(parallel=2)
    s0 = bc.CellSizing()

    # ---- nominal + butterfly plot ----
    nom = bc.characterize(sim, {"nom": (Process.at("tt"), s0, 1.8, 27.0)}, transient=True)["nom"]
    write_csv("bitcell_nominal.csv", [{**s0.as_dict(), **nom}])
    res = sim.run({"bf": bc.bench_butterfly("bf", Process.at("tt"), s0)})["bf"]
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 3.2), dpi=90)
    for ax, mode in zip(axes, ("hold", "read")):
        t = res.table(f"bf_{mode}.dat")
        x = t["v-sweep"]
        ax.plot(x, t["v(q)"], color=SERIES[0], lw=1.6, label="Q = f(QB)")
        ax.plot(t["v(qb)"], x, color=SERIES[1], lw=1.6, label="QB = f(Q), mirrored")
        snm = bc.snm_from_vtc(x, t["v(q)"], t["v(qb)"])[0]
        style(ax, "V(QB)", "V(Q)", f"{mode} butterfly, SNM = {snm * 1e3:.0f} mV")
        ax.set_aspect("equal")
    axes[0].legend(frameon=False, fontsize=7)
    save(fig, "bitcell_butterfly.png")

    # ---- PVT ----
    items = {}
    for c in CORNERS:
        for t in (-40.0, 27.0, 125.0):
            for v in (1.62, 1.8, 1.98):
                items[f"pvt_{c}_{int(t) + 40}_{int(v * 100)}"] = (Process.at(c), s0, v, t)
    pvt = bc.characterize(sim, items)
    pvt_rows = list(pvt.values())
    write_csv("bitcell_pvt.csv", pvt_rows)

    # ---- sizing sweeps ----
    sz_items = {}
    for w in (0.24e-6, 0.32e-6, 0.40e-6, 0.48e-6, 0.60e-6, 0.72e-6):
        sz_items[f"beta_{int(w * 1e9)}"] = (Process.at("tt"), replace(s0, w_pd=w), 1.8, 27.0)
    for w in (0.18e-6, 0.24e-6, 0.36e-6, 0.48e-6):
        sz_items[f"pu_{int(w * 1e9)}"] = (Process.at("tt"), replace(s0, w_pu=w), 1.8, 27.0)
    sz = bc.characterize(sim, sz_items)
    sz_rows = [{"sweep": k.split("_")[0], "w_pd_um": sz_items[k][1].w_pd * 1e6, "w_pu_um": sz_items[k][1].w_pu * 1e6,
                **v} for k, v in sz.items()]
    write_csv("bitcell_sizing.csv", sz_rows)
    fig, ax = plt.subplots(figsize=(5, 3.2), dpi=90)
    br = [r for r in sz_rows if r["sweep"] == "beta"]
    ax.plot([r["beta"] for r in br], [r["read_snm_mv"] for r in br], "-o", ms=4, color=SERIES[0], lw=1.6, label="read SNM")
    ax.plot([r["beta"] for r in br], [r["write_trip_mv"] for r in br], "-o", ms=4, color=SERIES[1], lw=1.6, label="write-trip voltage")
    ax.legend(frameon=False, fontsize=8)
    style(ax, "cell ratio W_PD / W_AX", "mV", "Read stability vs writability (TT, 1.8 V, 27 C)")
    save(fig, "bitcell_beta_sweep.png")

    # ---- Monte Carlo ----
    mc_items = {f"mc{k}": (Process.at("tt", seed=1000 + k), s0, 1.8, 27.0) for k in range(args.mc)}
    mc = bc.characterize(sim, mc_items)
    mc_rows = [{"seed": 1000 + k, **mc[f"mc{k}"]} for k in range(args.mc)]
    write_csv("bitcell_mc.csv", mc_rows)
    fig, ax = plt.subplots(figsize=(5, 3.2), dpi=90)
    ax.hist([r["read_snm_mv"] for r in mc_rows], bins=30, color=SERIES[0], edgecolor="white", lw=1, label="read SNM")
    ax.hist([r["hold_snm_mv"] for r in mc_rows], bins=30, color=SERIES[2], edgecolor="white", lw=1, label="hold SNM")
    ax.legend(frameon=False, fontsize=8)
    style(ax, "SNM (mV)", "count", f"Bitcell SNM under local mismatch (n={args.mc})")
    save(fig, "bitcell_mc_snm.png")

    # ---- data-retention voltage ----
    vdds = [round(v, 3) for v in np.arange(0.04, 0.401, 0.01)]
    d_nom = bc.drv(sim, {"nom": (Process.at("tt"), s0)}, vdds)["nom"]
    d_mc = bc.drv(sim, {f"d{k}": (Process.at("tt", seed=3000 + k), s0) for k in range(args.drv_mc)}, vdds)
    drv_vals = [d_mc[f"d{k}"]["drv_v"] for k in range(args.drv_mc)]
    write_csv("bitcell_drv.csv", [{"vdd": v, "hold_snm_mv_nominal": s * 1e3} for v, s in zip(vdds, d_nom["hold_snm"])])

    # ---- VDD sweep (nominal) ----
    vs_items = {f"vdd_{int(v * 100)}": (Process.at("tt"), s0, v, 27.0) for v in (0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 1.98)}
    vs = bc.characterize(sim, vs_items)
    vs_rows = list(vs.values())
    write_csv("bitcell_vdd_sweep.csv", vs_rows)

    # ---- summary ----
    def span(rows, key):
        vals = [r[key] for r in rows]
        return {"metric": key, "min": float(min(vals)), "max": float(max(vals))}

    pvt_summary = [span(pvt_rows, k) for k in ("hold_snm_mv", "read_snm_mv", "write_trip_mv", "read_current_ua",
                                                "leak_total_pa")]
    worst_read = min(pvt_rows, key=lambda r: r["read_snm_mv"])
    worst_write = min(pvt_rows, key=lambda r: r["write_trip_mv"])
    worst_leak = max(pvt_rows, key=lambda r: r["leak_total_pa"])
    mc_summary = [{"metric": k, **stats([r[k] for r in mc_rows])}
                  for k in ("hold_snm_mv", "read_snm_mv", "write_trip_mv", "read_current_ua", "leak_total_pa")]
    read_fail = sum(r["read_snm_mv"] <= 0 for r in mc_rows)
    write_fail = sum(r["write_trip_mv"] <= 0 for r in mc_rows)
    drv_ok = [d for d in drv_vals if not math.isnan(d)]
    leak27 = [r for r in pvt_rows if r["corner"] == "tt" and r["vdd"] == 1.8]
    nom_cols = ["hold_snm_mv", "read_snm_mv", "write_trip_mv", "read_current_ua", "read_bump_mv",
                "leak_total_pa", "leak_vdd_pa", "leak_bl_pa", "read_100mv_ps", "write_time_ps"]
    text = "\n".join([
        "# Bitcell results (ngspice, approximate 180 nm-class models)", "",
        f"Cell: PD {s0.w_pd * 1e6:.2f}/{s0.l * 1e6:.2f} um, AX {s0.w_ax * 1e6:.2f}/{s0.l * 1e6:.2f} um, "
        f"PU {s0.w_pu * 1e6:.2f}/{s0.l * 1e6:.2f} um (cell ratio {s0.beta:.2f}). Read access is the time to develop "
        "100 mV on a 100 fF bitline after WL rises.", "",
        "## Nominal (TT, 27 C, 1.8 V)", "", md([nom], nom_cols), "",
        "## PVT (5 corners x -40/27/125 C x 1.62/1.8/1.98 V)", "", md(pvt_summary, ["metric", "min", "max"]), "",
        f"Worst read SNM {worst_read['read_snm_mv']:.1f} mV at {worst_read['corner']}, {worst_read['temp_c']:.0f} C, "
        f"{worst_read['vdd']} V; worst write-trip {worst_write['write_trip_mv']:.1f} mV at {worst_write['corner']}, "
        f"{worst_write['temp_c']:.0f} C, {worst_write['vdd']} V; highest leakage {worst_leak['leak_total_pa']:.1f} pA "
        f"at {worst_leak['corner']}, {worst_leak['temp_c']:.0f} C, {worst_leak['vdd']} V.", "",
        "TT leakage vs temperature at 1.8 V: " + ", ".join(f"{r['temp_c']:.0f} C: {r['leak_total_pa']:.1f} pA" for r in leak27) + ".", "",
        "## Sizing sweeps (TT)", "",
        md(sz_rows, ["sweep", "w_pd_um", "w_pu_um", "beta", "read_snm_mv", "write_trip_mv", "read_current_ua"]), "",
        f"## Monte Carlo local mismatch (n = {args.mc}, TT, 27 C, 1.8 V)", "",
        md(mc_summary, ["metric", "n", "mean", "std", "min", "max", "mean_minus_3sigma"]), "",
        f"Read failures (read SNM <= 0): {read_fail}/{args.mc}; write failures (no flip with BL at 0 V): {write_fail}/{args.mc}.", "",
        "## Data-retention voltage (hold, bistability)", "",
        f"Nominal cell: hold SNM > 0 down to {d_nom['drv_v']:.3f} V on a 10 mV grid. "
        f"Monte Carlo (n = {args.drv_mc}): DRV mean {np.mean(drv_ok):.3f} V, max {np.max(drv_ok):.3f} V.", "",
        "## VDD sweep (TT, 27 C)", "",
        md(vs_rows, ["vdd", "hold_snm_mv", "read_snm_mv", "write_trip_mv", "read_current_ua", "leak_total_pa"]), "",
    ])
    (RES / "bitcell_summary.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
