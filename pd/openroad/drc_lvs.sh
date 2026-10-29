#!/usr/bin/env bash
# Magic DRC + GDS stream-out and Netgen LVS for the routed block (not run here).
set -euo pipefail
TOP=mbist_march
OUT=build/pd/openroad
: "${PDK_ROOT:?set PDK_ROOT to the directory containing sky130A}"
MAGICRC=$PDK_ROOT/sky130A/libs.tech/magic/sky130A.magicrc

magic -dnull -noconsole -rcfile "$MAGICRC" <<MAGIC
lef read $PDK_ROOT/sky130A/libs.ref/sky130_fd_sc_hd/techlef/sky130_fd_sc_hd__nom.tlef
lef read $PDK_ROOT/sky130A/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef
def read $OUT/$TOP.def
load $TOP
select top cell
drc style drc(full)
drc check
drc catchup
set count [drc count total]
puts "DRC_COUNT \$count"
gds write $OUT/$TOP.gds
extract all
ext2spice lvs
ext2spice -o $OUT/$TOP.extracted.spice
quit -noprompt
MAGIC

netgen -batch lvs "$OUT/$TOP.extracted.spice $TOP" "$OUT/$TOP.pnr.v $TOP" \
    "$PDK_ROOT/sky130A/libs.tech/netgen/sky130A_setup.tcl" "$OUT/lvs.rpt"
grep -E "Circuits match|Netlists do not match" "$OUT/lvs.rpt"
