# memorycore-vlsi

Memory design and test flow on a small scale: a 6T SRAM bitcell
characterized in ngspice, a 64x8 SRAM RTL model with a March C- memory BIST
controller verified in iverilog with injected faults, a scan-insertion
example, and a stuck-at fault simulator with PODEM ATPG that measures fault
coverage. Physical-design scripts for OpenROAD/SKY130 and Synopsys/Cadence
templates are included but **were not executed** (no PDK or tools in the
build environment).

> **Models are approximate.** The bitcell uses `models/cmos180_approx.lib`, a
> hand-written BSIM3v3 card loosely shaped after public 180 nm-class values,
> with corners emulated by threshold/mobility shifts and Pelgrom mismatch
> (`memcore/process.py`). The numbers below are simulation results with these
> models, not silicon or foundry data.

## Features

**Bitcell (ngspice, `memcore/bitcell.py`)**
- Read and hold static noise margin from butterfly curves (both half-cells
  swept with the same source; Seevinck largest-square method, with a
  closed-loop fixed-point test so monostable cells report SNM = 0).
- Write-trip voltage (bitline swept down until the cell flips), read current,
  read disturb bump, hold leakage split into supply and bitline components.
- Transients: time to develop 100 mV on a 100 fF bitline and write time.
- PVT grid, cell-ratio and pull-up sweeps, 500-sample Monte Carlo, and
  data-retention voltage (lowest VDD at which the cell stays bistable).

**Memory BIST (Verilog, `rtl/`)**
- `sram_model.v`: synchronous SRAM with a fault table: stuck-at, transition,
  inversion and idempotent coupling (inter- and intra-word), address-decoder faults.
- `mbist_march.v`: March C- controller {up(w0); up(r0,w1); up(r1,w0);
  down(r0,w1); down(r1,w0); up(r0)} with pipelined compare, error count,
  first-failure address/syndrome/element, and optional extra data
  backgrounds (00, 55, 33, 0F) for intra-word coupling faults.
- `tb/tb_mbist.v`: directed scenarios and seeded random fault campaigns.

**DFT and ATPG (Python, `memcore/atpg/`)**
- ISCAS `.bench` parser, levelization and Verilog export; generated
  benchmarks (adder, array multipliers, comparators, a sequential
  accumulator/counter) plus the public c17 and s27.
- Bit-parallel single stuck-at fault simulation with stem/branch faults and
  equivalence collapsing; random-pattern phase, PODEM top-up with redundancy
  identification, reverse-order compaction.
- Scan insertion (mux-D scan flops stitched into one chain), pattern export,
  and a generated self-checking scan testbench run in iverilog, including
  fault injection by `force` to cross-check the Python fault simulator.

**Physical design (`pd/`, not run)**: Yosys synthesis for `sky130_fd_sc_hd`, SDC,
OpenROAD floorplan/PDN/placement/CTS/routing/extraction/STA flow, Magic DRC +
Netgen LVS script, OpenLane 2 style config, and ICC2 / Innovus / PrimeTime templates.

## Layout

```
models/            approximate BSIM3v3 model card
memcore/spice.py   ngspice batch runner (native or docker)
memcore/process.py corners and Pelgrom mismatch
memcore/bitcell.py bitcell benches and metric extraction
memcore/atpg/      bench parser, fault simulator, PODEM, ATPG flow, scan insertion, generators
rtl/               SRAM model, March C- BIST, top wrapper, testbench; rtl/scan/ generated scan design + TB
atpg/netlists/     benchmark netlists (.bench) written by run_atpg.py
pd/                synthesis / P&R / signoff scripts (not executed)
scripts/           run_bitcell.py, run_bist.py, run_atpg.py
results/           CSV + markdown summaries and plots produced by the scripts
tests/             pytest (SNM extraction, ATPG, scan export, iverilog/ngspice integration)
```

## How to run

ngspice, iverilog and verilator are used natively if on `PATH`, otherwise via the
`devtools:latest` docker image.

```bash
pip install numpy matplotlib pytest
python -m pytest -q                                   # 19 tests (3 call iverilog/ngspice)
python scripts/run_bitcell.py --mc 500 --drv-mc 100   # ~5 min
python scripts/run_bist.py                            # ~30 s (iverilog) + verilator lint
python scripts/run_atpg.py                            # ~40 s (ATPG + 23 iverilog scan runs)
```

## Results

### Bitcell (`scripts/run_bitcell.py --mc 500 --drv-mc 100`)

Cell PD/AX/PU = 0.40/0.24/0.24 um, L = 0.18 um (cell ratio 1.67). TT, 27 C, 1.8 V:

| Hold SNM | Read SNM | Write-trip V(BL) | Read current | Leakage (total / VDD / BL) | Read 100 mV on 100 fF | Write time |
|---|---|---|---|---|---|---|
| 635 mV | 321 mV | 747 mV | 93.2 uA | 0.33 / 0.23 / 0.09 pA | 116 ps | 29 ps |

- **PVT** (5 corners x -40/27/125 C x 1.62/1.8/1.98 V): read SNM 236-394 mV
  (worst fs, 125 C, 1.98 V); write-trip 553-953 mV (worst sf, -40 C, 1.62 V);
  leakage 0.05-112 pA (worst ff, 125 C, 1.98 V). TT leakage at 1.8 V:
  0.05 pA at -40 C, 0.33 pA at 27 C, 33.9 pA at 125 C.
- **Monte Carlo** (500 samples, local mismatch): read SNM 308.6 +/- 12.6 mV
  (min 263.8 mV, mean - 3 sigma 270.9 mV), hold SNM 626.3 +/- 10.3 mV,
  write-trip 747.8 +/- 24.8 mV; 0/500 read or write failures.
- **Cell ratio sweep**: raising W_PD/W_AX from 1 to 3 raises read SNM from
  227 to 407 mV and lowers the write-trip voltage from 803 to 690 mV; widening
  the pull-up from 0.18 to 0.48 um raises read SNM 308 to 357 mV but drops
  write-trip from 799 to 567 mV.
- **Data retention**: the nominal cell stays bistable down to 0.06 V (10 mV
  grid); over 100 mismatch samples the DRV averages 0.088 V, worst 0.13 V.

ngspice's default `gmin` (1e-12 S across every junction) added about 9 pA per
cell at 1.8 V and masked the sub-threshold leakage, so the decks set
`gmin=1e-18`.

### March C- BIST (`scripts/run_bist.py`)

64 x 8 SRAM. One background: 644 cycles (10N + pipeline); four backgrounds: 2564 cycles.

| Scenario | 1 background | 4 backgrounds |
|---|---|---|
| fault-free | pass | pass |
| SAF0 / SAF1 | FAIL (addr 10 / 63) | FAIL |
| transition up / down | FAIL | FAIL |
| inversion coupling (inter-word) | FAIL (victim addr 30) | FAIL |
| idempotent coupling (inter-word) | FAIL | FAIL |
| idempotent coupling inside one word | **pass (missed)** | FAIL |
| address decoder (3 also writes 33) | FAIL | FAIL |

Random campaigns (100 single faults per class, seeded): SAF, TF, inter-word
CFin/CFid, intra-word CFin and ADF are all detected 100/100 with either
setting; intra-word CFid is detected 45/100 with the solid background and
100/100 with four backgrounds. `verilator --lint-only -Wall` on the controller is clean.

### ATPG and scan (`scripts/run_atpg.py`)

| Circuit | Gates | Collapsed faults | Random / PODEM detected | Redundant | Patterns | Coverage | Test efficiency |
|---|---|---|---|---|---|---|---|
| c17 | 6 | 22 | 22 / 0 | 0 | 6 | 100 % | 100 % |
| s27 (full scan) | 10 | 30 | 30 / 0 | 0 | 10 | 100 % | 100 % |
| rca8 | 49 | 194 | 194 / 0 | 0 | 12 | 100 % | 100 % |
| mult4x4 | 72 | 280 | 279 / 0 | 1 | 15 | 99.64 % | 100 % |
| cmp8 | 47 | 140 | 139 / 1 | 0 | 20 | 100 % | 100 % |
| cmp16 | 95 | 284 | 156 / 128 | 0 | 44 | 100 % | 100 % |
| mult8x8 | 336 | 1328 | 1327 / 0 | 1 | 27 | 99.92 % | 100 % |
| redundant (consensus term) | 5 | 17 | 16 / 0 | 1 | 4 | 94.12 % | 100 % |
| acc_ctr4 (full scan) | 47 | 188 | 184 / 0 | 4 | 16 | 97.87 % | 100 % |

Every fault PODEM classified as redundant was confirmed undetectable by
exhaustive simulation (all circuits with redundancies have at most 16 pseudo
inputs). The 16-bit comparator shows random-pattern resistance: random
patterns stall at 156/284 faults and PODEM covers the rest.

Scan example: `acc_ctr4` (8 flops) was scan-inserted into a single chain and its
16 compacted ATPG patterns were applied in iverilog through the chain: chain
integrity, primary-output and capture checks all passed fault-free. For 22
injected stem faults (20 random + the 2 stem faults the patterns leave
undetected), the Verilog scan test and the Python fault simulator agreed on
detection in 22/22 cases.

## Limitations

- Bitcell results use approximate 180 nm-class models; no layout,
  parasitics, or array-level peripheral circuits (sense amplifiers,
  decoders) are simulated. The bitline is a lumped 100 fF capacitor.
- The SRAM RTL is a behavioural model with an abstract fault table, not a
  transistor-level or layout-aware fault model.
- The ATPG targets single stuck-at faults only (no transition-delay or
  bridging faults) and the circuits are small.
- **Not executed**: everything in `pd/` (Yosys, OpenROAD, Magic, Netgen,
  ICC2, Innovus, PrimeTime). No area, timing, DRC or LVS results are claimed.

## License

MIT, see `LICENSE`.
