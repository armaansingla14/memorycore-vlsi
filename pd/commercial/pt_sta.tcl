# Synopsys PrimeTime sign-off STA template (not run here).
set DESIGN mbist_march
set search_path [list . $::env(LIB_DIR)]
set link_path   [list * $::env(LIB_SS_DB)]
read_verilog build/pd/icc2/${DESIGN}.pg.v
current_design $DESIGN
link_design
read_parasitics -format SPEF build/pd/icc2/${DESIGN}.spef
source pd/constraints/${DESIGN}.sdc
set_propagated_clock [all_clocks]
update_timing -full
report_timing -delay_type max -max_paths 20 -nosplit > reports/pt_setup.rpt
report_timing -delay_type min -max_paths 20 -nosplit > reports/pt_hold.rpt
report_constraint -all_violators -nosplit > reports/pt_violators.rpt
report_qor > reports/pt_qor.rpt
# Scan shift mode: analyse with scan_en held high on the scan block
# set_case_analysis 1 [get_ports scan_en]
