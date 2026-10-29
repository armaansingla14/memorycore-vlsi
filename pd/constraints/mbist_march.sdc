# Timing constraints for the BIST controller (not run here)
set clk_period 10.0
create_clock -name clk -period $clk_period [get_ports clk]
set_clock_uncertainty 0.25 [get_clocks clk]
set_clock_transition 0.15 [get_clocks clk]

set inputs  [remove_from_collection [all_inputs] [get_ports {clk rst_n}]]
set_input_delay  [expr 0.3 * $clk_period] -clock clk $inputs
set_output_delay [expr 0.3 * $clk_period] -clock clk [all_outputs]
# memory read data arrives from the SRAM macro late in the cycle
set_input_delay  [expr 0.6 * $clk_period] -clock clk [get_ports mem_rdata*]

set_false_path -from [get_ports rst_n]
set_load 0.02 [all_outputs]
set_driving_cell -lib_cell sky130_fd_sc_hd__buf_2 $inputs
