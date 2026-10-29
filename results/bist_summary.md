# March C- BIST results (iverilog)

64 x 8 SRAM model, March C- (10N operations per background). `nbg=1` uses the solid background only; `nbg=4` repeats the march with 00/55/33/0F backgrounds.

verilator lint of mbist_march: clean

## Directed fault scenarios

| scenario | nbg | fail | errors | first_addr | syndrome | elem | cycles |
|---|---|---|---|---|---|---|---|
| fault_free | 1 | pass | 0 | - | - | - | 644 |
| fault_free | 4 | pass | 0 | - | - | - | 2564 |
| saf0_a10_b3 | 1 | FAIL | 2 | 10 | 08 | 2 | 644 |
| saf0_a10_b3 | 4 | FAIL | 10 | 10 | 08 | 2 | 2564 |
| saf1_a63_b7 | 1 | FAIL | 3 | 63 | 80 | 1 | 644 |
| saf1_a63_b7 | 4 | FAIL | 9 | 63 | 80 | 1 | 2564 |
| tf_rise_a5_b0 | 1 | FAIL | 2 | 5 | 01 | 2 | 644 |
| tf_rise_a5_b0 | 4 | FAIL | 8 | 5 | 01 | 2 | 2564 |
| tf_fall_a40_b6 | 1 | FAIL | 2 | 40 | 40 | 3 | 644 |
| tf_fall_a40_b6 | 4 | FAIL | 10 | 40 | 40 | 1 | 2564 |
| cfin_a12_v30 | 1 | FAIL | 4 | 30 | 02 | 1 | 644 |
| cfin_a12_v30 | 4 | FAIL | 16 | 30 | 02 | 1 | 2564 |
| cfid_a50_v7 | 1 | FAIL | 1 | 7 | 10 | 2 | 644 |
| cfid_a50_v7 | 4 | FAIL | 4 | 7 | 10 | 2 | 2564 |
| cfid_intraword_a20 | 1 | pass | 0 | - | - | - | 644 |
| cfid_intraword_a20 | 4 | FAIL | 2 | 20 | 02 | 2 | 2564 |
| adf_3_to_33 | 1 | FAIL | 2 | 33 | ff | 1 | 644 |
| adf_3_to_33 | 4 | FAIL | 8 | 33 | ff | 1 | 2564 |

## Random single-fault campaigns (100 faults each, seeded)

| fault class | n | detected (1 background) | detected (4 backgrounds) |
|---|---|---|---|
| saf | 100 | 100 (100 %) | 100 (100 %) |
| tf | 100 | 100 (100 %) | 100 (100 %) |
| cfin_interword | 100 | 100 (100 %) | 100 (100 %) |
| cfid_interword | 100 | 100 (100 %) | 100 (100 %) |
| cfin_intraword | 100 | 100 (100 %) | 100 (100 %) |
| cfid_intraword | 100 | 45 (45 %) | 100 (100 %) |
| adf | 100 | 100 (100 %) | 100 (100 %) |
