# Synopsys IC Compiler II template (not run here; no licence/PDK available).
# Replace the *_PATH variables with the target library paths.
set DESIGN mbist_march
set NDM_REF_LIBS  $::env(NDM_REF_LIBS)        ;# standard-cell NDM libraries
set TECH_TF       $::env(TECH_TF)
set TLUPLUS_MAX   $::env(TLUPLUS_MAX)
set TLUPLUS_MIN   $::env(TLUPLUS_MIN)
set LAYER_MAP     $::env(TLU_LAYER_MAP)

create_lib ${DESIGN}.nlib -technology $TECH_TF -ref_libs $NDM_REF_LIBS
read_verilog -top $DESIGN build/pd/${DESIGN}.syn.v
link_block
read_parasitic_tech -tlup $TLUPLUS_MAX -layermap $LAYER_MAP -name maxTLU
read_parasitic_tech -tlup $TLUPLUS_MIN -layermap $LAYER_MAP -name minTLU
create_mode func
create_corner ss_m40c ; create_corner ff_125c
create_scenario -mode func -corner ss_m40c -name func_ss
create_scenario -mode func -corner ff_125c -name func_ff
set_parasitic_parameters -corners ss_m40c -late_spec maxTLU -early_spec maxTLU
set_parasitic_parameters -corners ff_125c -late_spec minTLU -early_spec minTLU
foreach s {func_ss func_ff} { current_scenario $s ; source pd/constraints/${DESIGN}.sdc }
set_scenario_status func_ss -setup true -hold false
set_scenario_status func_ff -setup false -hold true

# floorplan + power
initialize_floorplan -core_utilization 0.45 -shape R -side_ratio {1 1} -core_offset {5}
place_pins -self
create_pg_mesh_pattern mesh -layers {{{vertical_layer: M6} {width: 1.6} {pitch: 30}} {{horizontal_layer: M7} {width: 1.6} {pitch: 30}}}
create_pg_std_cell_conn_pattern rails -layers {M1}
set_pg_strategy core_mesh -core -pattern {{name: mesh} {nets: {VDD VSS}}}
set_pg_strategy core_rails -core -pattern {{name: rails} {nets: {VDD VSS}}}
compile_pg -strategies {core_mesh core_rails}

# placement, CTS, routing
place_opt
clock_opt
route_auto -max_detail_route_iterations 40
route_opt

# reports and outputs
check_routes
report_timing -scenarios {func_ss func_ff} -delay_type max -max_paths 10 > reports/icc2_setup.rpt
report_timing -scenarios {func_ss func_ff} -delay_type min -max_paths 10 > reports/icc2_hold.rpt
report_qor > reports/icc2_qor.rpt
write_verilog -include {pg_netlist} build/pd/icc2/${DESIGN}.pg.v
write_def build/pd/icc2/${DESIGN}.def
write_gds -layer_map $::env(GDS_LAYER_MAP) build/pd/icc2/${DESIGN}.gds
# Physical verification would follow with IC Validator: signoff_check_drc / signoff_check_lvs
