// mbist_march.v
// Memory BIST controller implementing March C- with multiple data backgrounds.
//
//   M0: up   (w0)
//   M1: up   (r0, w1)
//   M2: up   (r1, w0)
//   M3: down (r0, w1)
//   M4: down (r1, w0)
//   M5: up   (r0)
//
// "0" and "1" denote the data background and its complement. With NBG > 1
// the whole march is repeated for the standard word-oriented backgrounds
// 00..0, 0101.., 0011.., 00001111.. so intra-word coupling faults are
// covered. Read data comes back one cycle after the read is issued
// (registered SRAM); comparisons are pipelined accordingly.
//
// Outputs: done, fail (sticky), err_count, first failing address and its
// XOR syndrome, and the element index in which the first failure occurred.

`timescale 1ns/1ps
module mbist_march #(
    parameter AW  = 6,
    parameter DW  = 8,
    parameter NBG = 4
) (
    input  wire          clk,
    input  wire          rst_n,
    input  wire          start,
    output reg           busy,
    output reg           done,
    output reg           fail,
    output reg  [15:0]   err_count,
    output reg  [AW-1:0] first_fail_addr,
    output reg  [DW-1:0] first_fail_syndrome,
    output reg  [2:0]    first_fail_elem,
    // memory port
    output reg           mem_cs,
    output reg           mem_we,
    output reg  [AW-1:0] mem_addr,
    output reg  [DW-1:0] mem_wdata,
    input  wire [DW-1:0] mem_rdata
);
    localparam LAST = (1 << AW) - 1;

    // element description
    function [1:0] n_ops(input [2:0] e);
        case (e) 3'd0, 3'd5: n_ops = 2'd1; default: n_ops = 2'd2; endcase
    endfunction
    function is_down(input [2:0] e);
        is_down = (e == 3'd3) || (e == 3'd4);
    endfunction
    // op k of element e: {is_read, polarity}
    function [1:0] op_of(input [2:0] e, input k);
        case (e)
            3'd0: op_of = 2'b00;                       // w0
            3'd1: op_of = k ? 2'b01 : 2'b10;           // r0, w1
            3'd2: op_of = k ? 2'b00 : 2'b11;           // r1, w0
            3'd3: op_of = k ? 2'b01 : 2'b10;           // r0, w1
            3'd4: op_of = k ? 2'b00 : 2'b11;           // r1, w0
            default: op_of = 2'b10;                    // r0
        endcase
    endfunction

    function [DW-1:0] background(input [2:0] idx);
        integer b;
        begin
            for (b = 0; b < DW; b = b + 1)
                case (idx)
                    3'd0: background[b] = 1'b0;
                    3'd1: background[b] = b[0];
                    3'd2: background[b] = b[1];
                    3'd3: background[b] = b[2];
                    default: background[b] = b[3];
                endcase
        end
    endfunction

    reg [2:0]    elem;
    reg          opk;
    reg [AW-1:0] addr;
    reg [2:0]    bg;
    reg          running;
    reg [1:0]    drain;

    // compare pipeline: p0 at issue, p1 one cycle later, compare at p1
    reg          p0_v, p1_v;
    reg [DW-1:0] p0_exp, p1_exp;
    reg [AW-1:0] p0_addr, p1_addr;
    reg [2:0]    p0_elem, p1_elem;

    wire [1:0]    cur_op  = op_of(elem, opk);
    wire [DW-1:0] bg_word = background(bg);
    wire [DW-1:0] cur_dat = cur_op[0] ? ~bg_word : bg_word;
    wire          last_op = (n_ops(elem) == 2'd1) ? 1'b1 : opk;
    wire          last_addr = is_down(elem) ? (addr == 0) : (addr == LAST[AW-1:0]);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy <= 1'b0; done <= 1'b0; fail <= 1'b0; err_count <= 16'd0;
            first_fail_addr <= {AW{1'b0}}; first_fail_syndrome <= {DW{1'b0}}; first_fail_elem <= 3'd0;
            mem_cs <= 1'b0; mem_we <= 1'b0; mem_addr <= {AW{1'b0}}; mem_wdata <= {DW{1'b0}};
            elem <= 3'd0; opk <= 1'b0; addr <= {AW{1'b0}}; bg <= 3'd0; running <= 1'b0; drain <= 2'd0;
            p0_v <= 1'b0; p1_v <= 1'b0; p0_exp <= 0; p1_exp <= 0; p0_addr <= 0; p1_addr <= 0;
            p0_elem <= 0; p1_elem <= 0;
        end else begin
            // ---------------- compare stage ----------------
            p1_v <= p0_v; p1_exp <= p0_exp; p1_addr <= p0_addr; p1_elem <= p0_elem;
            if (p1_v && (mem_rdata !== p1_exp)) begin
                if (!fail) begin
                    first_fail_addr     <= p1_addr;
                    first_fail_syndrome <= mem_rdata ^ p1_exp;
                    first_fail_elem     <= p1_elem;
                end
                fail <= 1'b1;
                if (err_count != 16'hFFFF) err_count <= err_count + 16'd1;
            end
            // ---------------- issue stage ----------------
            p0_v <= 1'b0;
            if (start && !busy) begin
                busy <= 1'b1; done <= 1'b0; fail <= 1'b0; err_count <= 16'd0;
                running <= 1'b1; elem <= 3'd0; opk <= 1'b0; addr <= {AW{1'b0}}; bg <= 3'd0;
                drain <= 2'd0;
                mem_cs <= 1'b0; mem_we <= 1'b0;
            end else if (running) begin
                mem_cs    <= 1'b1;
                mem_we    <= ~cur_op[1];
                mem_addr  <= addr;
                mem_wdata <= cur_dat;
                if (cur_op[1]) begin
                    p0_v <= 1'b1; p0_exp <= cur_dat; p0_addr <= addr; p0_elem <= elem;
                end
                // advance: op -> address -> element -> background
                if (!last_op) begin
                    opk <= 1'b1;
                end else begin
                    opk <= 1'b0;
                    if (!last_addr) begin
                        addr <= is_down(elem) ? addr - 1'b1 : addr + 1'b1;
                    end else if (elem != 3'd5) begin
                        elem <= elem + 3'd1;
                        addr <= is_down(elem + 3'd1) ? LAST[AW-1:0] : {AW{1'b0}};
                    end else if (bg != NBG - 1) begin
                        bg <= bg + 3'd1;
                        elem <= 3'd0;
                        addr <= {AW{1'b0}};
                    end else begin
                        running <= 1'b0;
                        drain <= 2'd3;
                    end
                end
            end else if (busy) begin
                mem_cs <= 1'b0; mem_we <= 1'b0;
                if (drain != 0) drain <= drain - 2'd1;
                else begin
                    busy <= 1'b0;
                    done <= 1'b1;
                end
            end
        end
    end
endmodule
