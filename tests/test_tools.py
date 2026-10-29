"""Integration tests that call ngspice / iverilog (skipped when unavailable)."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from memcore.spice import ngspice_available

ROOT = Path(__file__).resolve().parents[1]


def _docker_ok():
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "image", "inspect", "devtools:latest"], capture_output=True).returncode == 0


def _sh(cmd):
    if shutil.which("iverilog"):
        return subprocess.run(["bash", "-c", cmd], cwd=ROOT, capture_output=True, text=True)
    return subprocess.run(["docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{ROOT}:/work",
                           "-w", "/work", "devtools:latest", "bash", "-c", cmd], capture_output=True, text=True)


tools = pytest.mark.skipif(not (shutil.which("iverilog") or _docker_ok()), reason="iverilog not available")


@tools
def test_bist_testbench_passes_and_detects():
    p = _sh("mkdir -p build && iverilog -g2005 -o build/t_mbist.vvp rtl/tb/tb_mbist.v rtl/sram_bist_top.v "
            "rtl/mbist_march.v rtl/sram_model.v && vvp -n build/t_mbist.vvp")
    out = p.stdout
    assert "TB_DONE" in out
    assert "scenario=fault_free nbg=4 fail=0" in out
    assert "scenario=saf0_a10_b3 nbg=1 fail=1" in out
    assert "scenario=cfid_intraword_a20 nbg=1 fail=0" in out
    assert "scenario=cfid_intraword_a20 nbg=4 fail=1" in out


@tools
def test_scan_testbench_fault_free():
    p = _sh("mkdir -p build && iverilog -g2005 -o build/t_scan.vvp rtl/scan/tb_scan.v rtl/scan/acc_ctr4_scan.v "
            "rtl/scan/cells.v && vvp -n build/t_scan.vvp")
    assert "chain_err=0 po_err=0 capture_err=0" in p.stdout


@pytest.mark.skipif(not ngspice_available(), reason="ngspice not available")
def test_bitcell_nominal():
    from memcore import bitcell as bc
    from memcore.process import Process
    from memcore.spice import NgSpice
    m = bc.characterize(NgSpice(), {"t": (Process.at("tt"), bc.CellSizing(), 1.8, 27.0)})["t"]
    assert 400 < m["hold_snm_mv"] < 900
    assert 100 < m["read_snm_mv"] < m["hold_snm_mv"]
    assert m["write_trip_mv"] > 0
    assert m["leak_total_pa"] > 0 and m["read_current_ua"] > 1
