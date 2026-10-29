# ATPG and scan results

Single stuck-at faults, equivalence-collapsed. Sequential circuits are tested in the full-scan view (flops = pseudo PI/PO). Coverage = detected / collapsed faults; test efficiency also credits faults proven redundant by PODEM.

| circuit | n_pi | n_po | n_flops | n_gates | faults_total | faults_collapsed | detected_random | detected_podem | redundant | aborted | patterns_final | coverage_pct | test_efficiency_pct | redundant_verified_exhaustive |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| c17 | 5 | 2 | 0 | 6 | 34 | 22 | 22 | 0 | 0 | 0 | 6 | 100.00 | 100.00 |  |
| s27 | 4 | 1 | 3 | 10 | 50 | 30 | 30 | 0 | 0 | 0 | 10 | 100.00 | 100.00 |  |
| rca8 | 17 | 9 | 0 | 49 | 260 | 194 | 194 | 0 | 0 | 0 | 12 | 100.00 | 100.00 |  |
| mult4x4 | 8 | 8 | 0 | 72 | 384 | 280 | 279 | 0 | 1 | 0 | 15 | 99.64 | 100.00 | True |
| cmp8 | 16 | 2 | 0 | 47 | 218 | 140 | 139 | 1 | 0 | 0 | 20 | 100.00 | 100.00 |  |
| cmp16 | 32 | 2 | 0 | 95 | 442 | 284 | 156 | 128 | 0 | 0 | 44 | 100.00 | 100.00 |  |
| mult8x8 | 16 | 16 | 0 | 336 | 1792 | 1328 | 1327 | 0 | 1 | 0 | 27 | 99.92 | 100.00 | True |
| redundant | 3 | 1 | 0 | 5 | 28 | 17 | 16 | 0 | 1 | 0 | 4 | 94.12 | 100.00 | True |
| acc_ctr4 | 5 | 3 | 8 | 47 | 254 | 188 | 184 | 0 | 4 | 0 | 16 | 97.87 | 100.00 | True |

## Scan test of acc_ctr4 (8 scan flops, iverilog)

Fault-free: 16 patterns, chain errors 0, PO mismatches 0, capture mismatches 0.

Injected stem faults: 22; the Verilog scan test and the Python fault simulator agree on detection for 22 of 22 (20 detected, 2 undetected).
