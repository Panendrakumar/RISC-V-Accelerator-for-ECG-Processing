`timescale 1ns / 1ps

// v2 board top: interactive ECG beat classifier demo.
//   SW0-SW3  -> select a stored beat (read by firmware through AXI GPIO ch2)
//   BTN0     -> reset (and also readable by firmware)
//   BTN1-3   -> firmware commands (run / show true label / self-test)
//   LD2:LD0  -> class code from firmware (N=001 S=010 V=011 F=100 Q=101)
//   LD3      -> PicoRV32 trap (error)
//   LED6 RGB -> class colour from firmware, dimmed with PWM (full drive is very bright)
module zybo_vit_v2_top (
    input  wire       sysclk,
    input  wire [3:0] btn,
    input  wire [3:0] sw,
    output wire [3:0] led,
    output wire       led6_r,
    output wire       led6_g,
    output wire       led6_b
);
    wire [5:0] gpio_out;
    wire       cpu_trap;
    wire       clk_100;

    ecg_vit_system_wrapper system_i (
        .sysclk    (sysclk),
        .btn_reset (btn[0]),
        .gpio_in   ({btn, sw}),
        .gpio_out  (gpio_out),
        .trap      (cpu_trap),
        .clk_100   (clk_100)
    );

    assign led = {cpu_trap, gpio_out[2:0]};

    // ~6 % duty cycle at ~390 kHz: visible but not glaring.
    reg [7:0] pwm = 8'd0;
    always @(posedge clk_100) pwm <= pwm + 8'd1;
    wire dim_on = (pwm < 8'd16);

    assign led6_r = gpio_out[5] & dim_on;
    assign led6_g = gpio_out[4] & dim_on;
    assign led6_b = gpio_out[3] & dim_on;
endmodule
