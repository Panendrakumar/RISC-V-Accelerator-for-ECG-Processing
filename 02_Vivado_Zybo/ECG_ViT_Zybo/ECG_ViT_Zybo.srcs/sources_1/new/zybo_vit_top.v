`timescale 1ns / 1ps

module zybo_vit_top (
    input  wire       sysclk,
    input  wire       btn_reset,
    output wire [3:0] led
);

    // Zybo buttons are high when pressed. Synchronize the button,
    // then provide the active-low reset expected by PicoRV32.
    reg [1:0] reset_sync = 2'b00;

    always @(posedge sysclk) begin
        reset_sync <= {reset_sync[0], ~btn_reset};
    end

    wire cpu_resetn = reset_sync[1];

    // PicoRV32 native memory interface
    wire        cpu_mem_valid;
    wire        cpu_mem_instr;
    wire        cpu_mem_ready;
    wire [31:0] cpu_mem_addr;
    wire [31:0] cpu_mem_wdata;
    wire [ 3:0] cpu_mem_wstrb;
    wire [31:0] cpu_mem_rdata;
    wire        cpu_trap;

    // One-cycle response for the synchronous BRAM.
    reg ram_wait = 1'b0;

    always @(posedge sysclk) begin
        if (!cpu_resetn)
            ram_wait <= 1'b0;
        else if (cpu_mem_valid && !ram_wait)
            ram_wait <= 1'b1;
        else if (ram_wait)
            ram_wait <= 1'b0;
    end

    assign cpu_mem_ready = ram_wait;

    // Map the 32 KiB BRAM at byte addresses 0x0000 through 0x7FFF.
    wire ram_selected = (cpu_mem_addr[31:15] == 17'b0);
    wire bram_en = cpu_resetn && cpu_mem_valid &&
                   !ram_wait && ram_selected;

    wire [12:0] bram_addr = cpu_mem_addr[14:2];
    wire [ 3:0] bram_we   = bram_en ? cpu_mem_wstrb : 4'b0000;
    wire [31:0] bram_dout;

    assign cpu_mem_rdata = ram_selected ? bram_dout : 32'b0;

    riscv_bram u_riscv_bram (
        .clka  (sysclk),
        .ena   (bram_en),
        .wea   (bram_we),
        .addra (bram_addr),
        .dina  (cpu_mem_wdata),
        .douta (bram_dout)
    );

    picorv32 #(
        .ENABLE_IRQ    (0),
        .PROGADDR_RESET(32'h0000_0000),
        .STACKADDR     (32'h0000_7FFC)
    ) u_picorv32 (
        .clk       (sysclk),
        .resetn    (cpu_resetn),
        .trap      (cpu_trap),

        .mem_valid (cpu_mem_valid),
        .mem_instr (cpu_mem_instr),
        .mem_ready (cpu_mem_ready),
        .mem_addr  (cpu_mem_addr),
        .mem_wdata (cpu_mem_wdata),
        .mem_wstrb (cpu_mem_wstrb),
        .mem_rdata (cpu_mem_rdata),

        .pcpi_wr    (1'b0),
        .pcpi_rd    (32'b0),
        .pcpi_wait  (1'b0),
        .pcpi_ready (1'b0),
        .irq        (32'b0)
    );

    // Simple bring-up indicators: trap, clock heartbeat, memory request, store.
    reg [25:0] heartbeat = 26'b0;

    always @(posedge sysclk) begin
        if (!cpu_resetn)
            heartbeat <= 26'b0;
        else
            heartbeat <= heartbeat + 1'b1;
    end

    assign led = {
        cpu_mem_valid && (|cpu_mem_wstrb),
        cpu_mem_valid,
        heartbeat[25],
        cpu_trap
    };

endmodule