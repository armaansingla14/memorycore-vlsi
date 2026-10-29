"""Stuck-at ATPG on the benchmark netlists, plus scan insertion and an
iverilog run of the generated scan test (fault-free and with injected faults).

Writes atpg/netlists/*.bench, rtl/scan/*.v, results/atpg_*.csv|md, plots.
"""
from __future__ import annotations

import csv
import itertools
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from memcore.atpg.bench import Circuit, _vname  # noqa: E402
from memcore.atpg.faultsim import FaultSimulator  # noqa: E402
from memcore.atpg.flow import run_atpg  # noqa: E402
from memcore.atpg.gen import all_benchmarks  # noqa: E402
from memcore.atpg.scan import CELLS_V, export_patterns, insert_scan, scan_testbench  # noqa: E402

RES = ROOT / "results"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#52514e"]


def verilog_runner():
    if shutil.which("iverilog"):
        return lambda cmd, cwd: subprocess.run(["bash", "-c", cmd], cwd=cwd, capture_output=True, text=True)

    def run(cmd, cwd):
        return subprocess.run(["docker", "run", "--rm", "--memory", "1g", "--user", f"{os.getuid()}:{os.getgid()}",
                               "-v", f"{cwd}:/work", "-w", "/work", "devtools:latest", "bash", "-c", cmd],
                              capture_output=True, text=True)
    return run


def exhaustive_check(c: Circuit, faults) -> bool:
    """True if none of ``faults`` is detected by the exhaustive pattern set."""
    fs = FaultSimulator(c)
    pis = fs.pis
    pats = [dict(zip(pis, bits)) for bits in itertools.product((0, 1), repeat=len(pis))]
    det, _ = fs.run(pats, list(faults))
    return len(det) == 0


def main():
    RES.mkdir(exist_ok=True)
    netdir = ROOT / "atpg" / "netlists"
    netdir.mkdir(parents=True, exist_ok=True)
    rows, curves = [], {}
    circuits = {}
    for name, text in all_benchmarks().items():
        (netdir / f"{name}.bench").write_text(text)
        c = Circuit.parse(text, name)
        circuits[name] = c
        rep = run_atpg(c, n_random=512, batch=32, seed=7)
        row = rep.row()
        # independent check of redundancy claims for small circuits
        if rep.redundant and len(c.pseudo_inputs) <= 16:
            fs = FaultSimulator(c)
            faults = fs.collapse(fs.all_faults())
            det, _ = fs.run(rep.patterns, faults)
            undet = [f for f in faults if f not in det]
            row["redundant_verified_exhaustive"] = exhaustive_check(c, undet)
        else:
            row["redundant_verified_exhaustive"] = ""
        rows.append(row)
        curves[name] = rep.random_curve
        print(f"{name}: {row['faults_collapsed']} faults, coverage {row['coverage_pct']:.2f}%, "
              f"eff {row['test_efficiency_pct']:.2f}%, patterns {row['patterns_final']}", flush=True)
        if name == "acc_ctr4":
            scan_patterns = rep.patterns

    keys = list(rows[0].keys())
    with open(RES / "atpg_summary.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.4g}" if isinstance(v, float) else v) for k, v in r.items()})

    fig, ax = plt.subplots(figsize=(5, 3.2), dpi=90)
    for i, (name, cv) in enumerate(curves.items()):
        if cv:
            ax.plot([p for p, _ in cv], [c for _, c in cv], color=SERIES[i % len(SERIES)], lw=1.4, label=name)
    ax.set_xscale("log")
    ax.legend(frameon=False, fontsize=7)
    ax.set_xlabel("random patterns applied", color="#52514e")
    ax.set_ylabel("stuck-at coverage (%)", color="#52514e")
    ax.set_title("Random-pattern fault coverage (before PODEM top-up)", fontsize=10, loc="left")
    ax.grid(True, color="#e4e3df", lw=0.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    (RES / "plots").mkdir(exist_ok=True)
    fig.tight_layout()
    fig.savefig(RES / "plots" / "atpg_random_coverage.png", dpi=90)
    plt.close(fig)

    # ---------------- scan insertion + Verilog scan test ----------------
    c = circuits["acc_ctr4"]
    scan_dir = ROOT / "rtl" / "scan"
    scan_dir.mkdir(parents=True, exist_ok=True)
    (scan_dir / "cells.v").write_text(CELLS_V)
    (scan_dir / "acc_ctr4.v").write_text("// Generated from atpg/netlists/acc_ctr4.bench (no scan)\n" + c.to_verilog("acc_ctr4"))
    (scan_dir / "acc_ctr4_scan.v").write_text(insert_scan(c, "acc_ctr4_scan"))
    vec_text, layout = export_patterns(c, scan_patterns)
    (scan_dir / "scan_vectors.mem").write_text(vec_text)
    (scan_dir / "tb_scan.v").write_text(scan_testbench(c, layout, "acc_ctr4_scan", "rtl/scan/scan_vectors.mem"))

    run = verilog_runner()
    build = "mkdir -p build && "
    src = "rtl/scan/tb_scan.v rtl/scan/acc_ctr4_scan.v rtl/scan/cells.v"

    def scan_sim(defines: str = "", tag: str = "ff"):
        cmd = (build + f"iverilog -g2005 {defines} -o build/tb_scan_{tag}.vvp {src} && "
               f"vvp -n build/tb_scan_{tag}.vvp")
        p = run(cmd, ROOT)
        m = re.search(r"SCAN_RESULT patterns=(\d+) chain_err=(\d+) po_err=(\d+) capture_err=(\d+)", p.stdout)
        if not m:
            raise RuntimeError(p.stdout + p.stderr)
        return tuple(int(x) for x in m.groups())

    scan_rows = []
    n, chain_err, po_err, cap_err = scan_sim()
    scan_rows.append({"run": "fault_free", "fault": "", "python_detects": False, "patterns": n,
                      "chain_err": chain_err, "po_err": po_err, "capture_err": cap_err,
                      "tb_detects": (chain_err + po_err + cap_err) > 0})
    # injected stem faults on internal nets: compare TB outcome with the Python fault simulator
    fs = FaultSimulator(c)
    stem_faults = [f for f in fs.all_faults() if f.gate is None and f.net not in c.inputs]
    rng = np.random.default_rng(3)
    picks = list(rng.choice(len(stem_faults), size=min(20, len(stem_faults)), replace=False))
    # add every stem fault the ATPG patterns leave undetected (the redundant ones)
    det_all, _ = fs.run(scan_patterns, stem_faults)
    picks += [i for i, f in enumerate(stem_faults) if f not in det_all and i not in picks]
    det_set, _ = fs.run(scan_patterns, [stem_faults[i] for i in picks])
    for i in picks:
        f = stem_faults[int(i)]
        py_det = f in det_set
        defs = f"-DFAULT_NET={_vname(f.net)} -DFAULT_VAL={f.stuck}"
        n, ce, pe, ke = scan_sim(defs, f"f{i}")
        scan_rows.append({"run": "injected", "fault": str(f), "python_detects": py_det, "patterns": n,
                          "chain_err": ce, "po_err": pe, "capture_err": ke,
                          "tb_detects": (ce + pe + ke) > 0})
        print(f"scan fault {f}: python={py_det} tb={(ce + pe + ke) > 0}", flush=True)
    with open(RES / "scan_test.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(scan_rows[0]))
        w.writeheader()
        w.writerows(scan_rows)
    agree = sum(r["python_detects"] == r["tb_detects"] for r in scan_rows[1:])

    cols = ["circuit", "n_pi", "n_po", "n_flops", "n_gates", "faults_total", "faults_collapsed",
            "detected_random", "detected_podem", "redundant", "aborted", "patterns_final",
            "coverage_pct", "test_efficiency_pct", "redundant_verified_exhaustive"]
    lines = ["# ATPG and scan results", "",
             "Single stuck-at faults, equivalence-collapsed. Sequential circuits are tested in the "
             "full-scan view (flops = pseudo PI/PO). Coverage = detected / collapsed faults; "
             "test efficiency also credits faults proven redundant by PODEM.", "",
             "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        lines.append("| " + " | ".join(f"{r[k]:.2f}" if isinstance(r[k], float) else str(r[k]) for k in cols) + " |")
    ff = scan_rows[0]
    lines += ["", "## Scan test of acc_ctr4 (8 scan flops, iverilog)", "",
              f"Fault-free: {ff['patterns']} patterns, chain errors {ff['chain_err']}, PO mismatches {ff['po_err']}, "
              f"capture mismatches {ff['capture_err']}.", "",
              f"Injected stem faults: {len(scan_rows) - 1}; the Verilog scan test and the Python fault simulator "
              f"agree on detection for {agree} of {len(scan_rows) - 1} "
              f"({sum(r['tb_detects'] for r in scan_rows[1:])} detected, "
              f"{sum(not r['tb_detects'] for r in scan_rows[1:])} undetected).", ""]
    (RES / "atpg_summary.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
