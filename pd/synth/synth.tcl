# Yosys (Tcl mode) synthesis of the BIST controller for SKY130 HD (not run here)
# Usage: PDK_ROOT=/path/to/pdks yosys -c pd/synth/synth.tcl
set lib $::env(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
file mkdir build/pd
yosys read_verilog -sv rtl/mbist_march.v
yosys hierarchy -check -top mbist_march
yosys synth -top mbist_march -flatten
yosys dfflibmap -liberty $lib
yosys abc -liberty $lib -D 10000
yosys opt_clean -purge
yosys hilomap -hicell sky130_fd_sc_hd__conb_1 HI -locell sky130_fd_sc_hd__conb_1 LO
yosys setundef -zero
yosys splitnets
yosys insbuf -buf sky130_fd_sc_hd__buf_2 A X
yosys tee -o build/pd/synth_stat.rpt stat -liberty $lib
yosys write_verilog -noattr build/pd/mbist_march.syn.v
