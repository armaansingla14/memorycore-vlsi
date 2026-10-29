// tb_mbist.v
// Runs the March C- BIST on a 64x8 SRAM model for a set of directed fault
// scenarios and a seeded random fault campaign, with 1 and 4 data
// backgrounds. Prints one machine-readable RESULT line per run.
`timescale 1ns/1ps
module tb_mbist;
    localparam AW = 6, DW = 8;
    reg clk = 0, rst_n = 0;
    always #5 clk = ~clk;

    reg  start1 = 0, start4 = 0;
    wire busy1, done1, fail1, busy4, done4, fail4;
    wire [15:0] err1, err4;
    wire [AW-1:0] fa1, fa4;
    wire [DW-1:0] syn1, syn4, rd1, rd4;
    wire [2:0] el1, el4;

    sram_bist_top #(.AW(AW), .DW(DW), .NBG(1)) dut1 (
        .clk(clk), .rst_n(rst_n), .f_cs(1'b0), .f_we(1'b0), .f_addr({AW{1'b0}}), .f_wdata({DW{1'b0}}),
        .f_rdata(rd1), .bist_mode(1'b1), .bist_start(start1), .bist_busy(busy1), .bist_done(done1),
        .bist_fail(fail1), .bist_err_count(err1), .bist_fail_addr(fa1), .bist_fail_syndrome(syn1),
        .bist_fail_elem(el1));
    sram_bist_top #(.AW(AW), .DW(DW), .NBG(4)) dut4 (
        .clk(clk), .rst_n(rst_n), .f_cs(1'b0), .f_we(1'b0), .f_addr({AW{1'b0}}), .f_wdata({DW{1'b0}}),
        .f_rdata(rd4), .bist_mode(1'b1), .bist_start(start4), .bist_busy(busy4), .bist_done(done4),
        .bist_fail(fail4), .bist_err_count(err4), .bist_fail_addr(fa4), .bist_fail_syndrome(syn4),
        .bist_fail_elem(el4));

    integer cycles1, cycles4;
    integer det1, det4, total;
    integer seed;

    task run_both(input [8*24-1:0] name);
        begin
            cycles1 = 0; cycles4 = 0;
            @(negedge clk); start1 = 1; start4 = 1;
            @(negedge clk); start1 = 0; start4 = 0;
            while (!(done1 && done4)) begin
                @(negedge clk);
                if (!done1) cycles1 = cycles1 + 1;
                if (!done4) cycles4 = cycles4 + 1;
            end
            $display("RESULT scenario=%0s nbg=1 fail=%0d errors=%0d first_addr=%0d syndrome=%02h elem=%0d cycles=%0d",
                     name, fail1, err1, fa1, syn1, el1, cycles1 + 1);
            $display("RESULT scenario=%0s nbg=4 fail=%0d errors=%0d first_addr=%0d syndrome=%02h elem=%0d cycles=%0d",
                     name, fail4, err4, fa4, syn4, el4, cycles4 + 1);
        end
    endtask

    task clear;
        begin dut1.mem.clear_faults; dut4.mem.clear_faults; end
    endtask

    // random-fault campaign helpers
    task campaign(input integer ftype, input integer n, input [8*24-1:0] name);
        integer k, a, b, va, vb, v, w;
        begin
            det1 = 0; det4 = 0;
            for (k = 0; k < n; k = k + 1) begin
                clear;
                a  = {$random(seed)} % (1 << AW);
                b  = {$random(seed)} % DW;
                va = {$random(seed)} % (1 << AW);
                vb = {$random(seed)} % DW;
                v  = {$random(seed)} % 2;
                w  = {$random(seed)} % 2;
                if (ftype == 4 || ftype == 5) begin
                    // intra-word coupling: same address, different bit
                    va = a;
                    if (vb == b) vb = (b + 1) % DW;
                end else if ((ftype == 2 || ftype == 3 || ftype == 6) && va == a) begin
                    va = (a + 1) % (1 << AW);
                end
                case (ftype)
                    0: begin dut1.mem.inject_saf(a, b, v); dut4.mem.inject_saf(a, b, v); end
                    1: begin dut1.mem.inject_tf(a, b, v); dut4.mem.inject_tf(a, b, v); end
                    2: begin dut1.mem.inject_cfin(a, b, va, vb); dut4.mem.inject_cfin(a, b, va, vb); end
                    3: begin dut1.mem.inject_cfid(a, b, va, vb, v, w); dut4.mem.inject_cfid(a, b, va, vb, v, w); end
                    4: begin dut1.mem.inject_cfin(a, b, va, vb); dut4.mem.inject_cfin(a, b, va, vb); end
                    5: begin dut1.mem.inject_cfid(a, b, va, vb, v, w); dut4.mem.inject_cfid(a, b, va, vb, v, w); end
                    6: begin dut1.mem.inject_adf(a, va); dut4.mem.inject_adf(a, va); end
                endcase
                cycles1 = 0;
                @(negedge clk); start1 = 1; start4 = 1;
                @(negedge clk); start1 = 0; start4 = 0;
                while (!(done1 && done4)) @(negedge clk);
                det1 = det1 + fail1;
                det4 = det4 + fail4;
            end
            $display("CAMPAIGN fault=%0s n=%0d detected_nbg1=%0d detected_nbg4=%0d", name, n, det1, det4);
        end
    endtask

    initial begin
        seed = 20260;
        repeat (3) @(negedge clk);
        rst_n = 1;
        // ---- directed scenarios ----
        clear;                                   run_both("fault_free");
        clear; dut1.mem.inject_saf(10, 3, 0);  dut4.mem.inject_saf(10, 3, 0);  run_both("saf0_a10_b3");
        clear; dut1.mem.inject_saf(63, 7, 1);  dut4.mem.inject_saf(63, 7, 1);  run_both("saf1_a63_b7");
        clear; dut1.mem.inject_tf(5, 0, 1);    dut4.mem.inject_tf(5, 0, 1);    run_both("tf_rise_a5_b0");
        clear; dut1.mem.inject_tf(40, 6, 0);   dut4.mem.inject_tf(40, 6, 0);   run_both("tf_fall_a40_b6");
        clear; dut1.mem.inject_cfin(12, 1, 30, 1); dut4.mem.inject_cfin(12, 1, 30, 1); run_both("cfin_a12_v30");
        clear; dut1.mem.inject_cfid(50, 2, 7, 4, 1, 0); dut4.mem.inject_cfid(50, 2, 7, 4, 1, 0); run_both("cfid_a50_v7");
        clear; dut1.mem.inject_cfid(20, 0, 20, 1, 1, 1); dut4.mem.inject_cfid(20, 0, 20, 1, 1, 1); run_both("cfid_intraword_a20");
        clear; dut1.mem.inject_adf(3, 33);     dut4.mem.inject_adf(3, 33);     run_both("adf_3_to_33");
        // ---- random campaigns ----
        campaign(0, 100, "saf");
        campaign(1, 100, "tf");
        campaign(2, 100, "cfin_interword");
        campaign(3, 100, "cfid_interword");
        campaign(4, 100, "cfin_intraword");
        campaign(5, 100, "cfid_intraword");
        campaign(6, 100, "adf");
        $display("TB_DONE");
        $finish;
    end
endmodule
