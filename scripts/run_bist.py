"""Compile and run the March C- BIST testbench with iverilog (native or docker),
lint the RTL with verilator, and write results/bist_*.csv|md."""
from __future__ import annotations

import csv
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
RTL = ["rtl/tb/tb_mbist.v", "rtl/sram_bist_top.v", "rtl/mbist_march.v", "rtl/sram_model.v"]


def sh(cmd: str) -> subprocess.CompletedProcess:
    if shutil.which("iverilog"):
        return subprocess.run(["bash", "-c", cmd], cwd=ROOT, capture_output=True, text=True)
    return subprocess.run(["docker", "run", "--rm", "--memory", "1g", "--user", f"{os.getuid()}:{os.getgid()}",
                           "-v", f"{ROOT}:/work", "-w", "/work", "devtools:latest", "bash", "-c", cmd],
                          capture_output=True, text=True)


def main():
    RES.mkdir(exist_ok=True)
    lint = sh("verilator --lint-only -Wall -Wno-DECLFILENAME -Wno-UNUSEDPARAM "
              "--top-module mbist_march rtl/mbist_march.v 2>&1; echo LINT_EXIT=$?")
    lint_ok = "LINT_EXIT=0" in lint.stdout
    p = sh("mkdir -p build && iverilog -g2005 -Wall -o build/tb_mbist.vvp " + " ".join(RTL) +
           " && vvp -n build/tb_mbist.vvp")
    if "TB_DONE" not in p.stdout:
        print(p.stdout[-3000:], p.stderr[-3000:])
        raise SystemExit("BIST testbench did not complete")
    rows, camp = [], []
    for line in p.stdout.splitlines():
        if line.startswith("RESULT"):
            kv = dict(re.findall(r"(\w+)=(\S+)", line))
            rows.append(kv)
        elif line.startswith("CAMPAIGN"):
            kv = dict(re.findall(r"(\w+)=(\S+)", line))
            camp.append(kv)
    with open(RES / "bist_directed.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(RES / "bist_campaign.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(camp[0]))
        w.writeheader()
        w.writerows(camp)

    lines = ["# March C- BIST results (iverilog)", "",
             "64 x 8 SRAM model, March C- (10N operations per background). `nbg=1` uses the solid "
             "background only; `nbg=4` repeats the march with 00/55/33/0F backgrounds.", "",
             f"verilator lint of mbist_march: {'clean' if lint_ok else 'warnings, see log'}", "",
             "## Directed fault scenarios", "",
             "| scenario | nbg | fail | errors | first_addr | syndrome | elem | cycles |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['scenario']} | {r['nbg']} | {'FAIL' if r['fail'] == '1' else 'pass'} | {r['errors']} | "
                     f"{r['first_addr'] if r['fail'] == '1' else '-'} | {r['syndrome'] if r['fail'] == '1' else '-'} | "
                     f"{r['elem'] if r['fail'] == '1' else '-'} | {r['cycles']} |")
    lines += ["", "## Random single-fault campaigns (100 faults each, seeded)", "",
              "| fault class | n | detected (1 background) | detected (4 backgrounds) |", "|---|---|---|---|"]
    for c in camp:
        n = int(c["n"])
        lines.append(f"| {c['fault']} | {n} | {c['detected_nbg1']} ({100 * int(c['detected_nbg1']) / n:.0f} %) | "
                     f"{c['detected_nbg4']} ({100 * int(c['detected_nbg4']) / n:.0f} %) |")
    (RES / "bist_summary.md").write_text("\n".join(lines) + "\n")
    (RES / "verilator_lint.txt").write_text(lint.stdout)
    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
