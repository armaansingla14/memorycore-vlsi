# OpenROAD place-and-route flow for mbist_march on SKY130 HD (not run here).
# Inputs : build/pd/mbist_march.syn.v (from pd/synth/synth.tcl)
# Env    : PDK_ROOT pointing at an installed sky130A PDK
# Usage  : openroad -exit pd/openroad/flow.tcl

set pdk  $::env(PDK_ROOT)/sky130A
set sc   $pdk/libs.ref/sky130_fd_sc_hd
set top  mbist_march
set out  build/pd/openroad
file mkdir $out

# ---------------------------------------------------------------- setup
read_lef $sc/techlef/sky130_fd_sc_hd__nom.tlef
read_lef $sc/lef/sky130_fd_sc_hd.lef
read_liberty $sc/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
read_verilog build/pd/${top}.syn.v
link_design $top
read_sdc pd/constraints/${top}.sdc
source $pdk/libs.tech/openlane/sky130_fd_sc_hd/setRC.tcl

# ---------------------------------------------------------------- floorplan
initialize_floorplan -site unithd -utilization 45 -aspect_ratio 1.0 -core_space 5
make_tracks
place_pins -hor_layers met3 -ver_layers met2 -random
tapcell -distance 14 -tapcell_master sky130_fd_sc_hd__tapvpwrvgnd_1 -endcap_master sky130_fd_sc_hd__decap_3

# ---------------------------------------------------------------- power grid
add_global_connection -net VPWR -pin_pattern {^VPWR$} -power
add_global_connection -net VGND -pin_pattern {^VGND$} -ground
add_global_connection -net VPWR -pin_pattern {^VPB$}
add_global_connection -net VGND -pin_pattern {^VNB$}
global_connect
set_voltage_domain -power VPWR -ground VGND
define_pdn_grid -name core
add_pdn_stripe -grid core -layer met1 -width 0.48 -followpins
add_pdn_stripe -grid core -layer met4 -width 1.6 -pitch 27.14 -offset 13.57
add_pdn_connect -grid core -layers {met1 met4}
pdngen

# ---------------------------------------------------------------- placement
global_placement -density 0.6 -timing_driven
estimate_parasitics -placement
repair_design
detailed_placement
check_placement -verbose
report_checks -path_delay max -format full_clock_expanded > $out/place_timing.rpt

# ---------------------------------------------------------------- CTS
clock_tree_synthesis -root_buf sky130_fd_sc_hd__clkbuf_16 -buf_list {sky130_fd_sc_hd__clkbuf_4 sky130_fd_sc_hd__clkbuf_8}
set_propagated_clock [all_clocks]
estimate_parasitics -placement
repair_timing -setup
repair_timing -hold -hold_margin 0.05
detailed_placement
report_clock_skew > $out/cts_skew.rpt

# ---------------------------------------------------------------- routing
set_routing_layers -signal met1-met5 -clock met3-met5
global_route -guide_file $out/route.guide -congestion_iterations 50
estimate_parasitics -global_routing
repair_timing -setup
filler_placement {sky130_fd_sc_hd__fill_1 sky130_fd_sc_hd__fill_2 sky130_fd_sc_hd__decap_4}
detailed_route -output_drc $out/droute_drc.rpt -bottom_routing_layer met1 -top_routing_layer met5

# ---------------------------------------------------------------- signoff-style reports
extract_parasitics -ext_model_file $pdk/libs.tech/openlane/rules.openrcx.sky130A.nom.calibre
write_spef $out/${top}.spef
report_checks -path_delay min_max -format full_clock_expanded > $out/final_timing.rpt
report_tns > $out/final_tns.rpt
report_wns > $out/final_wns.rpt
report_design_area > $out/area.rpt
report_power > $out/power.rpt
write_def $out/${top}.def
write_verilog $out/${top}.pnr.v
