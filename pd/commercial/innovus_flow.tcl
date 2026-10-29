# Cadence Innovus template (not run here; no licence/PDK available).
set DESIGN mbist_march
set init_verilog   build/pd/${DESIGN}.syn.v
set init_top_cell  $DESIGN
set init_lef_file  [list $::env(TECH_LEF) $::env(STDCELL_LEF)]
set init_mmmc_file pd/commercial/mmmc.tcl
set init_pwr_net   VDD
set init_gnd_net   VSS
init_design

floorPlan -r 1.0 0.45 5 5 5 5
editPin -side Top -layer M3 -spreadType center -pin [dbGet top.terms.name]
addRing -nets {VDD VSS} -type core_rings -layer {top M5 bottom M5 left M6 right M6} -width 1.6 -spacing 1.0
addStripe -nets {VDD VSS} -layer M6 -direction vertical -width 1.6 -spacing 1.0 -set_to_set_distance 30
sroute -nets {VDD VSS}

setPlaceMode -place_global_timing_effort high
place_opt_design
ccopt_design
optDesign -postCTS -hold
setNanoRouteMode -routeWithTimingDriven true -routeWithSiDriven true
routeDesign
optDesign -postRoute -setup -hold
addFiller -cell $::env(FILLER_CELLS) -prefix FILL

verify_drc -report reports/innovus_drc.rpt
verifyConnectivity -report reports/innovus_conn.rpt
timeDesign -postRoute -outDir reports/innovus_timing
report_power -outfile reports/innovus_power.rpt
saveNetlist build/pd/innovus/${DESIGN}.pnr.v
defOut -routing build/pd/innovus/${DESIGN}.def
streamOut build/pd/innovus/${DESIGN}.gds -mapFile $::env(GDS_MAP)
# LVS with Pegasus/PVS would compare the GDS against the saved netlist.
