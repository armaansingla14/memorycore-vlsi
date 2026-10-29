# Multi-mode multi-corner setup for Innovus (template, not run here)
create_library_set -name ss_lib -timing [list $::env(LIB_SS)]
create_library_set -name ff_lib -timing [list $::env(LIB_FF)]
create_rc_corner -name rc_max -qx_tech_file $::env(QRC_MAX)
create_rc_corner -name rc_min -qx_tech_file $::env(QRC_MIN)
create_delay_corner -name dc_ss -library_set ss_lib -rc_corner rc_max
create_delay_corner -name dc_ff -library_set ff_lib -rc_corner rc_min
create_constraint_mode -name func -sdc_files [list pd/constraints/mbist_march.sdc]
create_analysis_view -name setup_view -constraint_mode func -delay_corner dc_ss
create_analysis_view -name hold_view  -constraint_mode func -delay_corner dc_ff
set_analysis_view -setup {setup_view} -hold {hold_view}
