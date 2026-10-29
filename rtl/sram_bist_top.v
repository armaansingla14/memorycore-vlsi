// sram_bist_top.v
// SRAM macro model wrapped with a March C- BIST controller and a functional
// port. When bist_mode is high the controller owns the memory port.
`timescale 1ns/1ps
module sram_bist_top #(
    parameter AW  = 6,
    parameter DW  = 8,
    parameter NBG = 4
) (
    input  wire          clk,
    input  wire          rst_n,
    // functional port
    input  wire          f_cs,
    input  wire          f_we,
    input  wire [AW-1:0] f_addr,
    input  wire [DW-1:0] f_wdata,
    output wire [DW-1:0] f_rdata,
    // BIST control / status
    input  wire          bist_mode,
    input  wire          bist_start,
    output wire          bist_busy,
    output wire          bist_done,
    output wire          bist_fail,
    output wire [15:0]   bist_err_count,
    output wire [AW-1:0] bist_fail_addr,
    output wire [DW-1:0] bist_fail_syndrome,
    output wire [2:0]    bist_fail_elem
);
    wire          b_cs, b_we;
    wire [AW-1:0] b_addr;
    wire [DW-1:0] b_wdata;

    wire          m_cs    = bist_mode ? b_cs    : f_cs;
    wire          m_we    = bist_mode ? b_we    : f_we;
    wire [AW-1:0] m_addr  = bist_mode ? b_addr  : f_addr;
    wire [DW-1:0] m_wdata = bist_mode ? b_wdata : f_wdata;
    wire [DW-1:0] m_rdata;

    assign f_rdata = m_rdata;

    sram_model #(.AW(AW), .DW(DW)) mem (
        .clk(clk), .cs(m_cs), .we(m_we), .addr(m_addr), .wdata(m_wdata), .rdata(m_rdata)
    );

    mbist_march #(.AW(AW), .DW(DW), .NBG(NBG)) bist (
        .clk(clk), .rst_n(rst_n), .start(bist_start & bist_mode),
        .busy(bist_busy), .done(bist_done), .fail(bist_fail), .err_count(bist_err_count),
        .first_fail_addr(bist_fail_addr), .first_fail_syndrome(bist_fail_syndrome),
        .first_fail_elem(bist_fail_elem),
        .mem_cs(b_cs), .mem_we(b_we), .mem_addr(b_addr), .mem_wdata(b_wdata), .mem_rdata(m_rdata)
    );
endmodule
