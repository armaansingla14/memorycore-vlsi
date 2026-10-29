import numpy as np
import pytest

from memcore.bitcell import is_bistable, snm_from_vtc, write_trip


def inverter(x, vdd=1.0, vm=0.5, gain=20.0):
    return vdd / (1 + np.exp(gain * (x - vm)))


def test_symmetric_ideal_inverters_snm():
    x = np.linspace(0, 1, 2001)
    q = inverter(x)
    snm, l1, l2 = snm_from_vtc(x, q, q)
    assert l1 == pytest.approx(l2, rel=1e-3)
    # very steep inverters approach the VDD/2 limit
    x2 = np.linspace(0, 1, 4001)
    steep = inverter(x2, gain=400.0)
    assert snm_from_vtc(x2, steep, steep)[0] == pytest.approx(0.5, abs=0.02)
    assert 0.2 < snm < 0.5


def test_skewed_cell_has_smaller_lobe():
    x = np.linspace(0, 1, 2001)
    snm_sym = snm_from_vtc(x, inverter(x), inverter(x))[0]
    snm_skew, l1, l2 = snm_from_vtc(x, inverter(x, vm=0.4), inverter(x, vm=0.5))
    assert snm_skew < snm_sym
    assert abs(l1 - l2) > 0.05


def test_monostable_gives_zero():
    x = np.linspace(0, 1, 2001)
    weak = inverter(x, gain=1.5)          # loop gain < 1 everywhere
    assert not is_bistable(x, weak, weak)
    assert snm_from_vtc(x, weak, weak)[0] == 0.0
    # strongly skewed: one inverter flips far from the other -> single fixed point
    assert snm_from_vtc(x, inverter(x, vm=0.05, gain=8), inverter(x, vm=0.95, gain=8))[0] == 0.0


def test_write_trip_interpolation():
    vbl = np.linspace(1.8, 0, 901)
    q = np.where(vbl > 0.7, 1.8, 0.0)
    assert write_trip(vbl, q, 1.8) == pytest.approx(0.7, abs=0.003)
    assert write_trip(vbl, np.full_like(vbl, 1.8), 1.8) == 0.0
