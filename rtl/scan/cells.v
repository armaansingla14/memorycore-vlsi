// Scan cell library (behavioural)
`timescale 1ns/1ps
module dff (input wire clk, input wire d, output reg q);
    always @(posedge clk) q <= d;
endmodule

module sdff (input wire clk, input wire d, input wire si, input wire se, output reg q);
    always @(posedge clk) q <= se ? si : d;
endmodule
