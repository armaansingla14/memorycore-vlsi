# Scan block constraints (not run here). Functional mode by default; scan shift
# mode analysed separately with scan_en = 1.
create_clock -name clk -period 10.0 [get_ports clk]
set_input_delay 2.0 -clock clk [remove_from_collection [all_inputs] [get_ports clk]]
set_output_delay 2.0 -clock clk [all_outputs]
set_case_analysis 0 [get_ports scan_en]
