# Bitcell results (ngspice, approximate 180 nm-class models)

Cell: PD 0.40/0.18 um, AX 0.24/0.18 um, PU 0.24/0.18 um (cell ratio 1.67). Read access is the time to develop 100 mV on a 100 fF bitline after WL rises.

## Nominal (TT, 27 C, 1.8 V)

| hold_snm_mv | read_snm_mv | write_trip_mv | read_current_ua | read_bump_mv | leak_total_pa | leak_vdd_pa | leak_bl_pa | read_100mv_ps | write_time_ps |
|---|---|---|---|---|---|---|---|---|---|
| 635.3 | 320.8 | 747.3 | 93.15 | 222.6 | 0.3253 | 0.2317 | 0.09367 | 116.4 | 28.99 |

## PVT (5 corners x -40/27/125 C x 1.62/1.8/1.98 V)

| metric | min | max |
|---|---|---|
| hold_snm_mv | 544.3 | 715.6 |
| read_snm_mv | 235.9 | 393.9 |
| write_trip_mv | 553.3 | 953.4 |
| read_current_ua | 52.43 | 139.2 |
| leak_total_pa | 0.05015 | 112 |

Worst read SNM 235.9 mV at fs, 125 C, 1.98 V; worst write-trip 553.3 mV at sf, -40 C, 1.62 V; highest leakage 112.0 pA at ff, 125 C, 1.98 V.

TT leakage vs temperature at 1.8 V: -40 C: 0.1 pA, 27 C: 0.3 pA, 125 C: 33.9 pA.

## Sizing sweeps (TT)

| sweep | w_pd_um | w_pu_um | beta | read_snm_mv | write_trip_mv | read_current_ua |
|---|---|---|---|---|---|---|
| beta | 0.24 | 0.24 | 1 | 226.8 | 803.2 | 75.78 |
| beta | 0.32 | 0.24 | 1.333 | 280.9 | 771.3 | 86.22 |
| beta | 0.4 | 0.24 | 1.667 | 320.8 | 747.3 | 93.15 |
| beta | 0.48 | 0.24 | 2 | 350.7 | 727.4 | 98 |
| beta | 0.6 | 0.24 | 2.5 | 383.3 | 705.5 | 103 |
| beta | 0.72 | 0.24 | 3 | 406.5 | 689.6 | 106.5 |
| pu | 0.4 | 0.18 | 1.667 | 307.7 | 799.4 | 93.15 |
| pu | 0.4 | 0.24 | 1.667 | 320.8 | 747.3 | 93.15 |
| pu | 0.4 | 0.36 | 1.667 | 340.8 | 653.4 | 93.15 |
| pu | 0.4 | 0.48 | 1.667 | 356.5 | 567.4 | 93.15 |

## Monte Carlo local mismatch (n = 500, TT, 27 C, 1.8 V)

| metric | n | mean | std | min | max | mean_minus_3sigma |
|---|---|---|---|---|---|---|
| hold_snm_mv | 500 | 626.3 | 10.31 | 590 | 655 | 595.4 |
| read_snm_mv | 500 | 308.6 | 12.56 | 263.8 | 343.5 | 270.9 |
| write_trip_mv | 500 | 747.8 | 24.75 | 675.4 | 819.3 | 673.5 |
| read_current_ua | 500 | 93.04 | 2.873 | 84.89 | 102.1 | 84.42 |
| leak_total_pa | 500 | 0.3786 | 0.1228 | 0.1492 | 0.9821 | 0.01007 |

Read failures (read SNM <= 0): 0/500; write failures (no flip with BL at 0 V): 0/500.

## Data-retention voltage (hold, bistability)

Nominal cell: hold SNM > 0 down to 0.060 V on a 10 mV grid. Monte Carlo (n = 100): DRV mean 0.088 V, max 0.130 V.

## VDD sweep (TT, 27 C)

| vdd | hold_snm_mv | read_snm_mv | write_trip_mv | read_current_ua | leak_total_pa |
|---|---|---|---|---|---|
| 0.8 | 357.4 | 192.9 | 175.1 | 7.618 | 0.2425 |
| 1 | 445.5 | 244.6 | 285.2 | 20.56 | 0.2585 |
| 1.2 | 517.4 | 285.2 | 403.2 | 36.77 | 0.2746 |
| 1.4 | 567 | 307.1 | 519.3 | 54.84 | 0.2909 |
| 1.6 | 603.8 | 317.1 | 633.3 | 73.84 | 0.3076 |
| 1.8 | 635.3 | 320.8 | 747.3 | 93.15 | 0.3253 |
| 1.98 | 661.5 | 321 | 847.4 | 110.4 | 0.3442 |
