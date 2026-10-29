// Generated scan-test testbench for acc_ctr4_scan
`timescale 1ns/1ps
module tb_scan;
    reg clk = 0, scan_en = 0, scan_in = 0;
    wire scan_out;
    reg en;
    reg d0;
    reg d1;
    reg d2;
    reg d3;
    wire eq;
    wire par;
    wire ovf;
    reg [23:0] vectors [0:15];
    reg [23:0] vec;
    integer t, k, po_err, cap_err, chain_err;
    acc_ctr4_scan dut (.clk(clk), .scan_en(scan_en), .scan_in(scan_in), .scan_out(scan_out), .en(en), .d0(d0), .d1(d1), .d2(d2), .d3(d3), .eq(eq), .par(par), .ovf(ovf));

`ifdef FAULT_NET
    initial force dut.`FAULT_NET = `FAULT_VAL;
`endif

    task pulse; begin #5 clk = 1; #5 clk = 0; end endtask

    initial begin
        $readmemb("rtl/scan/scan_vectors.mem", vectors);
        po_err = 0; cap_err = 0; chain_err = 0;
        en = 0;
        d0 = 0;
        d1 = 0;
        d2 = 0;
        d3 = 0;
        // chain integrity: shift an alternating 0011 pattern through
        scan_en = 1;
        for (k = 0; k < 8 + 8; k = k + 1) begin
            scan_in = (k / 2) % 2;
            if (k >= 8 && scan_out !== ((k - 8) / 2) % 2) chain_err = chain_err + 1;
            pulse;
        end
        for (t = 0; t < 16; t = t + 1) begin
            vec = vectors[t];
            // load: shift F(N-1) first so that F0 receives the last bit
            scan_en = 1;
            for (k = 8 - 1; k >= 0; k = k - 1) begin
                scan_in = vec[23 - k];
                pulse;
            end
            // apply primary inputs and observe primary outputs
            scan_en = 0;
            en = vec[15];
            d0 = vec[14];
            d1 = vec[13];
            d2 = vec[12];
            d3 = vec[11];
            #2;
            if (eq !== vec[10]) begin po_err = po_err + 1; end
            if (par !== vec[9]) begin po_err = po_err + 1; end
            if (ovf !== vec[8]) begin po_err = po_err + 1; end
            pulse;            // capture
            // unload: scan_out presents F(N-1) first
            scan_en = 1;
            for (k = 8 - 1; k >= 0; k = k - 1) begin
                #1;
                if (scan_out !== vec[7 - k]) cap_err = cap_err + 1;
                pulse;
            end
        end
        $display("SCAN_RESULT patterns=%0d chain_err=%0d po_err=%0d capture_err=%0d", 16, chain_err, po_err, cap_err);
        $finish;
    end
endmodule
