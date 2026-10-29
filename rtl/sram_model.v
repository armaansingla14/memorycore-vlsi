// sram_model.v
// Synchronous single-port SRAM behavioural model with fault injection.
//
//   * registered read data (rdata valid the cycle after a read is issued)
//   * fault table driven by tasks callable from a testbench:
//       inject_saf (addr, bit, value)            stuck-at-0/1 cell
//       inject_tf  (addr, bit, rising)           transition fault (cell cannot
//                                                make a 0->1 (rising=1) or 1->0 transition)
//       inject_cfin(a_addr, a_bit, v_addr, v_bit) inversion coupling fault: any
//                                                transition of the aggressor
//                                                inverts the victim
//       inject_cfid(a_addr, a_bit, v_addr, v_bit, trans, val)
//                                                idempotent coupling fault: an
//                                                aggressor transition to `trans`
//                                                forces the victim to `val`
//       inject_adf (addr_a, addr_b)              address-decoder fault: an access
//                                                to addr_a also writes addr_b
//       clear_faults
//
// The fault model is intentionally simple (one table, bit-level) and is used
// to check that the March C- BIST controller detects each fault class.

`timescale 1ns/1ps
module sram_model #(
    parameter AW = 6,
    parameter DW = 8,
    parameter NF = 8          // fault table entries
) (
    input  wire          clk,
    input  wire          cs,
    input  wire          we,
    input  wire [AW-1:0] addr,
    input  wire [DW-1:0] wdata,
    output reg  [DW-1:0] rdata
);
    localparam DEPTH = 1 << AW;
    localparam F_NONE = 0, F_SAF = 1, F_TF = 2, F_CFIN = 3, F_CFID = 4, F_ADF = 5;

    reg [DW-1:0] mem [0:DEPTH-1];

    reg [2:0]    f_type  [0:NF-1];
    reg [AW-1:0] f_addr  [0:NF-1];
    reg [7:0]    f_bit   [0:NF-1];
    reg [AW-1:0] f_vaddr [0:NF-1];
    reg [7:0]    f_vbit  [0:NF-1];
    reg          f_val   [0:NF-1];
    reg          f_trans [0:NF-1];
    integer      n_faults;

    integer i;
    initial begin
        n_faults = 0;
        for (i = 0; i < NF; i = i + 1) f_type[i] = F_NONE;
        for (i = 0; i < DEPTH; i = i + 1) mem[i] = {DW{1'bx}};
        rdata = {DW{1'b0}};
    end

    task clear_faults;
        integer k;
        begin
            for (k = 0; k < NF; k = k + 1) f_type[k] = F_NONE;
            n_faults = 0;
        end
    endtask

    task add_fault(input [2:0] t, input [AW-1:0] a, input [7:0] b,
                   input [AW-1:0] va, input [7:0] vb, input v, input tr);
        begin
            if (n_faults < NF) begin
                f_type[n_faults]  = t;
                f_addr[n_faults]  = a;
                f_bit[n_faults]   = b;
                f_vaddr[n_faults] = va;
                f_vbit[n_faults]  = vb;
                f_val[n_faults]   = v;
                f_trans[n_faults] = tr;
                n_faults = n_faults + 1;
            end
        end
    endtask

    task inject_saf(input [AW-1:0] a, input [7:0] b, input v);
        begin add_fault(F_SAF, a, b, 0, 0, v, 0); mem[a][b] = v; end
    endtask
    task inject_tf(input [AW-1:0] a, input [7:0] b, input rising);
        add_fault(F_TF, a, b, 0, 0, 0, rising);
    endtask
    task inject_cfin(input [AW-1:0] a, input [7:0] b, input [AW-1:0] va, input [7:0] vb);
        add_fault(F_CFIN, a, b, va, vb, 0, 0);
    endtask
    task inject_cfid(input [AW-1:0] a, input [7:0] b, input [AW-1:0] va, input [7:0] vb,
                     input trans, input v);
        add_fault(F_CFID, a, b, va, vb, v, trans);
    endtask
    task inject_adf(input [AW-1:0] a, input [AW-1:0] b2);
        add_fault(F_ADF, a, 0, b2, 0, 0, 0);
    endtask

    // Apply a write to one word honouring SAF/TF/coupling faults.
    task do_write(input [AW-1:0] a, input [DW-1:0] d);
        reg [DW-1:0] old, nw;
        integer k;
        begin
            old = mem[a];
            nw  = d;
            for (k = 0; k < n_faults; k = k + 1) begin
                if (f_type[k] == F_TF && f_addr[k] == a) begin
                    if (f_trans[k] && old[f_bit[k]] === 1'b0 && d[f_bit[k]] === 1'b1)
                        nw[f_bit[k]] = 1'b0;           // cannot rise
                    if (!f_trans[k] && old[f_bit[k]] === 1'b1 && d[f_bit[k]] === 1'b0)
                        nw[f_bit[k]] = 1'b1;           // cannot fall
                end
                if (f_type[k] == F_SAF && f_addr[k] == a)
                    nw[f_bit[k]] = f_val[k];
            end
            mem[a] = nw;
            // coupling faults triggered by aggressor transitions in this word
            for (k = 0; k < n_faults; k = k + 1) begin
                if ((f_type[k] == F_CFIN || f_type[k] == F_CFID) && f_addr[k] == a &&
                    old[f_bit[k]] !== nw[f_bit[k]] && old[f_bit[k]] !== 1'bx) begin
                    if (f_type[k] == F_CFIN)
                        mem[f_vaddr[k]][f_vbit[k]] = ~mem[f_vaddr[k]][f_vbit[k]];
                    else if (nw[f_bit[k]] == f_trans[k])
                        mem[f_vaddr[k]][f_vbit[k]] = f_val[k];
                end
            end
            // re-apply stuck-at cells anywhere a coupling fault may have flipped them
            for (k = 0; k < n_faults; k = k + 1)
                if (f_type[k] == F_SAF) mem[f_addr[k]][f_bit[k]] = f_val[k];
        end
    endtask

    integer k2;
    always @(posedge clk) begin
        if (cs) begin
            if (we) begin
                do_write(addr, wdata);
                for (k2 = 0; k2 < n_faults; k2 = k2 + 1)
                    if (f_type[k2] == F_ADF && f_addr[k2] == addr)
                        do_write(f_vaddr[k2], wdata);
            end else begin
                rdata <= mem[addr];
            end
        end
    end
endmodule
