# Physical-design scripts (not executed here)

These scripts describe how the BIST controller (`rtl/mbist_march.v`) and the
scan-inserted test block (`rtl/scan/acc_ctr4_scan.v`) would be taken through
synthesis and place-and-route. **None of them were run in this repository**:
the build environment has no Yosys, OpenROAD, Magic, Netgen, SKY130 PDK, or
Synopsys/Cadence tools. They are written against the public tool interfaces
and are provided as templates; expect to adjust paths and options.

| Directory | Contents | Status |
|---|---|---|
| `synth/` | Yosys script mapping to `sky130_fd_sc_hd` | not run |
| `constraints/` | SDC (100 MHz clock, I/O delays, scan-mode case analysis) | not run |
| `openroad/` | OpenROAD Tcl flow: floorplan, IO placement, PDN, global/detailed placement, CTS, global/detailed routing, RC extraction, STA reports; Magic DRC and Netgen LVS wrapper; OpenLane 2 style config | not run |
| `commercial/` | Synopsys ICC2 and PrimeTime, and Cadence Innovus templates for the same steps | not run |

The SRAM array itself is treated as a hard macro (for SKY130 an OpenRAM-generated
macro such as `sky130_sram_1kbyte_1rw1r_32x256_8` would be used); the behavioural
`sram_model.v` exists for simulation only.
