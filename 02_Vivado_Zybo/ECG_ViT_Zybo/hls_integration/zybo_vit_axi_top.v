`timescale 1ns / 1ps

module zybo_vit_axi_top (
    input  wire       sysclk,
    input  wire       btn_reset,
    output wire [3:0] led
);
    wire [2:0] class_led;
    wire       cpu_trap;

    ecg_vit_system_wrapper system_i (
        .sysclk    (sysclk),
        .btn_reset (btn_reset),
        .led_class (class_led),
        .trap      (cpu_trap)
    );

    // LED[2:0] encode N=001, S=010, V=011, F=100, Q=101.
    // LED[3] indicates a PicoRV32 trap.
    assign led = {cpu_trap, class_led};
endmodule
