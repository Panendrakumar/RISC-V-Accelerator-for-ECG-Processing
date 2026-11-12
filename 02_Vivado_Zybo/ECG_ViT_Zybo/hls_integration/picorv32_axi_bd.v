// AXI4-Lite master wrapper used as the RISC-V controller in IP Integrator.
module picorv32_axi_bd (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk CLK",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME clk, ASSOCIATED_BUSIF M_AXI, ASSOCIATED_RESET resetn, FREQ_HZ 100000000" *)
    input  wire        clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 resetn RST",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME resetn, POLARITY ACTIVE_LOW" *)
    input  wire        resetn,
    output wire        trap,

    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI AWVALID" *) output wire        M_AXI_AWVALID,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI AWREADY" *) input  wire        M_AXI_AWREADY,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI AWADDR",
       X_INTERFACE_PARAMETER = "XIL_INTERFACENAME M_AXI, PROTOCOL AXI4LITE, DATA_WIDTH 32, ADDR_WIDTH 32, FREQ_HZ 100000000, ID_WIDTH 0, HAS_BURST 0, HAS_LOCK 0, HAS_CACHE 0, HAS_QOS 0, HAS_REGION 0, HAS_PROT 1, HAS_WSTRB 1, SUPPORTS_NARROW_BURST 0" *) output wire [31:0] M_AXI_AWADDR,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI AWPROT"  *) output wire [ 2:0] M_AXI_AWPROT,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI WVALID"  *) output wire        M_AXI_WVALID,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI WREADY"  *) input  wire        M_AXI_WREADY,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI WDATA"   *) output wire [31:0] M_AXI_WDATA,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI WSTRB"   *) output wire [ 3:0] M_AXI_WSTRB,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI BVALID"  *) input  wire        M_AXI_BVALID,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI BREADY"  *) output wire        M_AXI_BREADY,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI ARVALID" *) output wire        M_AXI_ARVALID,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI ARREADY" *) input  wire        M_AXI_ARREADY,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI ARADDR"  *) output wire [31:0] M_AXI_ARADDR,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI ARPROT"  *) output wire [ 2:0] M_AXI_ARPROT,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI RVALID"  *) input  wire        M_AXI_RVALID,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI RREADY"  *) output wire        M_AXI_RREADY,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 M_AXI RDATA"   *) input  wire [31:0] M_AXI_RDATA
);

    wire        unused_pcpi_valid;
    wire [31:0] unused_pcpi_insn;
    wire [31:0] unused_pcpi_rs1;
    wire [31:0] unused_pcpi_rs2;
    wire [31:0] unused_eoi;
    wire        unused_trace_valid;
    wire [35:0] unused_trace_data;

    picorv32_axi #(
        .ENABLE_IRQ     (0),
        .ENABLE_PCPI    (0),
        .ENABLE_MUL     (0),
        .ENABLE_FAST_MUL(0),
        .ENABLE_DIV     (0),
        .PROGADDR_RESET (32'h0000_0000),
        .STACKADDR      (32'h0000_7FF0)
    ) cpu (
        .clk             (clk),
        .resetn          (resetn),
        .trap            (trap),
        .mem_axi_awvalid (M_AXI_AWVALID),
        .mem_axi_awready (M_AXI_AWREADY),
        .mem_axi_awaddr  (M_AXI_AWADDR),
        .mem_axi_awprot  (M_AXI_AWPROT),
        .mem_axi_wvalid  (M_AXI_WVALID),
        .mem_axi_wready  (M_AXI_WREADY),
        .mem_axi_wdata   (M_AXI_WDATA),
        .mem_axi_wstrb   (M_AXI_WSTRB),
        .mem_axi_bvalid  (M_AXI_BVALID),
        .mem_axi_bready  (M_AXI_BREADY),
        .mem_axi_arvalid (M_AXI_ARVALID),
        .mem_axi_arready (M_AXI_ARREADY),
        .mem_axi_araddr  (M_AXI_ARADDR),
        .mem_axi_arprot  (M_AXI_ARPROT),
        .mem_axi_rvalid  (M_AXI_RVALID),
        .mem_axi_rready  (M_AXI_RREADY),
        .mem_axi_rdata   (M_AXI_RDATA),
        .pcpi_valid      (unused_pcpi_valid),
        .pcpi_insn       (unused_pcpi_insn),
        .pcpi_rs1        (unused_pcpi_rs1),
        .pcpi_rs2        (unused_pcpi_rs2),
        .pcpi_wr         (1'b0),
        .pcpi_rd         (32'b0),
        .pcpi_wait       (1'b0),
        .pcpi_ready      (1'b0),
        .irq             (32'b0),
        .eoi             (unused_eoi),
        .trace_valid     (unused_trace_valid),
        .trace_data      (unused_trace_data)
    );
endmodule
