import itertools

import pytest

from memcore.atpg.bench import Circuit
from memcore.atpg.faultsim import Fault, FaultSimulator
from memcore.atpg.flow import coverage_of, run_atpg
from memcore.atpg.gen import C17, S27, all_benchmarks, redundant_example, ripple_adder
from memcore.atpg.podem import Podem


def test_parse_c17():
    c = Circuit.parse(C17, "c17")
    assert c.inputs == ["1", "2", "3", "6", "7"] and c.outputs == ["22", "23"]
    assert c.n_gates() == 6 and not c.flops


def test_s27_full_scan_view():
    c = Circuit.parse(S27, "s27")
    assert c.flops == ["G5", "G6", "G7"]
    assert c.pseudo_inputs[-3:] == ["G5", "G6", "G7"]
    assert c.pseudo_outputs[-3:] == ["G10", "G11", "G13"]


def test_adder_logic_simulation():
    c = Circuit.parse(ripple_adder(4), "rca4")
    fs = FaultSimulator(c)
    for a, b, cin in itertools.product(range(16), range(16), range(2)):
        pat = {f"a{i}": (a >> i) & 1 for i in range(4)}
        pat.update({f"b{i}": (b >> i) & 1 for i in range(4)})
        pat["cin"] = cin
        r = fs.responses(pat)
        s = sum(r[f"s{i}"] << i for i in range(4)) + (r["cout"] << 4)
        assert s == a + b + cin


def test_collapsing_reduces_faults():
    c = Circuit.parse(C17, "c17")
    fs = FaultSimulator(c)
    allf = fs.all_faults()
    col = fs.collapse(allf)
    assert len(allf) == 34 and len(col) == 22


def test_c17_full_coverage():
    rep = run_atpg(Circuit.parse(C17, "c17"), seed=1)
    assert rep.coverage_pct == 100.0 and rep.redundant == 0
    assert coverage_of(Circuit.parse(C17, "c17"), rep.patterns) == 100.0


def test_redundant_fault_identified_and_untestable():
    c = Circuit.parse(redundant_example(), "red")
    rep = run_atpg(c, seed=1)
    assert rep.redundant == 1 and rep.test_efficiency_pct == 100.0
    # the consensus term t3 = b.c stuck-at-0 cannot change f
    fs = FaultSimulator(c)
    pats = [dict(zip(fs.pis, bits)) for bits in itertools.product((0, 1), repeat=3)]
    det, _ = fs.run(pats, [Fault("t3", 0)])
    assert not det


def test_podem_pattern_detects_target():
    c = Circuit.parse(all_benchmarks()["cmp8"], "cmp8")
    fs = FaultSimulator(c)
    pg = Podem(c)
    faults = fs.collapse(fs.all_faults())
    for f in faults[::7]:
        status, pat = pg.generate(f)
        assert status == "detected"
        det, _ = fs.run([pat], [f])
        assert f in det


@pytest.mark.parametrize("name", ["rca8", "mult4x4", "acc_ctr4"])
def test_benchmarks_reach_full_test_efficiency(name):
    rep = run_atpg(Circuit.parse(all_benchmarks()[name], name), seed=3)
    assert rep.aborted == 0
    assert rep.test_efficiency_pct == 100.0
