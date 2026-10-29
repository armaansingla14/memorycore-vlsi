import re

from memcore.atpg.bench import Circuit
from memcore.atpg.flow import run_atpg
from memcore.atpg.gen import acc_ctr
from memcore.atpg.scan import export_patterns, insert_scan, scan_testbench


def test_scan_insertion_structure():
    c = Circuit.parse(acc_ctr(4), "acc_ctr4")
    v = insert_scan(c)
    assert len(re.findall(r"\bsdff\b", v)) == 8
    assert "assign scan_out = cnt3;" in v
    assert ".si(scan_in)" in v


def test_pattern_export_widths():
    c = Circuit.parse(acc_ctr(4), "acc_ctr4")
    rep = run_atpg(c, seed=1)
    text, layout = export_patterns(c, rep.patterns)
    lines = text.split()
    assert len(lines) == layout["n_patterns"] == len(rep.patterns)
    assert all(len(line) == layout["width"] == 8 + 5 + 3 + 8 for line in lines)
    tb = scan_testbench(c, layout)
    assert "SCAN_RESULT" in tb and "FAULT_NET" in tb
