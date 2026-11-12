# Create the first PicoRV32 + fixed-point ViT integration design.
# Firmware is inserted after implementation with UpdateMEM; Vivado clears
# BMG MEM_FILE when this RAM is attached to AXI BRAM Controller.

if {[llength [get_projects -quiet]] == 0} {
    error "Open ECG_ViT_Zybo.xpr before sourcing this script."
}

set script_dir [file dirname [file normalize [info script]]]
set project_root [file normalize [file join $script_dir .. .. ..]]
set hls_ip_repo [file join $project_root 03_HW_SW_Validation vitis_hls z7_tiny_ecg_vit ecg_vit_z7_fixed solution1 impl ip]
set cpu_wrapper [file normalize [file join $script_dir picorv32_axi_bd.v]]
set board_top [file normalize [file join $script_dir zybo_vit_axi_top.v]]

foreach required [list $hls_ip_repo $cpu_wrapper $board_top] {
    if {![file exists $required]} {
        error "Required integration input not found: $required"
    }
}
set existing_bd [get_files -quiet -all *ecg_vit_system.bd]
if {[llength $existing_bd] != 0} {
    # Recover when Vivado wrote the BD file but its Windows helper process failed
    # before the first block could be added. Never append a second copy of the
    # design to a BD that already contains cells or ports.
    open_bd_design [lindex $existing_bd 0]
    current_bd_design ecg_vit_system
    set existing_cells [get_bd_cells -quiet]
    set existing_ports [get_bd_ports -quiet]
    if {[llength $existing_cells] != 0 || [llength $existing_ports] != 0} {
        error "ecg_vit_system already contains design objects; inspect it before re-running this integration script."
    }
    puts "Resuming the existing empty ecg_vit_system block design."
} else {
    create_bd_design ecg_vit_system
    current_bd_design ecg_vit_system
}

set current_repos [get_property IP_REPO_PATHS [current_project]]
if {[lsearch -exact $current_repos $hls_ip_repo] < 0} {
    lappend current_repos $hls_ip_repo
    set_property IP_REPO_PATHS $current_repos [current_project]
}
update_ip_catalog -rebuild

# Vivado's add_files consumes a Tcl list; [list] keeps paths with spaces as one item.
# Avoid adding duplicates when resuming after a transient Windows spawn failure.
proc add_source_once {path} {
    set wanted [file normalize $path]
    foreach existing [get_files -quiet -all] {
        if {![catch {file normalize $existing} normalized] && $normalized eq $wanted} {
            return
        }
    }
    add_files -norecurse [list $wanted]
}
add_source_once $cpu_wrapper
add_source_once $board_top
if {[catch {update_compile_order -fileset sources_1} compile_order_error]} {
    puts "WARNING: Vivado could not refresh compile order ($compile_order_error); continuing with BD creation."
}

# Existing board constraints use these exact top-level signal names.
set sysclk [create_bd_port -dir I -type clk -freq_hz 125000000 sysclk]
set reset_button [create_bd_port -dir I -type rst btn_reset]
set_property CONFIG.POLARITY ACTIVE_HIGH $reset_button
create_bd_port -dir O -from 2 -to 0 led_class
create_bd_port -dir O trap

set clk_wiz [create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz:6.0 clk_wiz_0]
set_property -dict [list \
    CONFIG.PRIM_SOURCE {Single_ended_clock_capable_pin} \
    CONFIG.PRIM_IN_FREQ {125.000} \
    CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {100.000} \
    CONFIG.USE_RESET {true} \
    CONFIG.RESET_TYPE {ACTIVE_HIGH} \
    CONFIG.USE_LOCKED {true}] $clk_wiz

set reset_ctrl [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 proc_sys_reset_0]

set cpu [create_bd_cell -type module -reference picorv32_axi_bd picorv32_axi_bd_0]
set vit [create_bd_cell -type ip -vlnv xilinx.com:hls:vit_inference_fixed:1.0 vit_inference_fixed_0]
set smart [create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:1.0 smartconnect_0]
set_property -dict [list CONFIG.NUM_SI {2} CONFIG.NUM_MI {3}] $smart

set bram_ctrl [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_bram_ctrl:4.1 axi_bram_ctrl_0]
set_property -dict [list \
    CONFIG.DATA_WIDTH {32} \
    CONFIG.SINGLE_PORT_BRAM {1} \
    CONFIG.READ_LATENCY {1}] $bram_ctrl

set bram [create_bd_cell -type ip -vlnv xilinx.com:ip:blk_mem_gen:8.4 blk_mem_gen_0]
set_property -dict [list \
    CONFIG.Interface_Type {Native} \
    CONFIG.Memory_Type {Single_Port_RAM} \
    CONFIG.Write_Width_A {32} \
    CONFIG.Read_Width_A {32} \
    CONFIG.Write_Depth_A {8192} \
    CONFIG.Use_Byte_Write_Enable {true} \
    CONFIG.Byte_Size {8}] $bram
set gpio [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:2.0 axi_gpio_0]
set_property -dict [list \
    CONFIG.C_IS_DUAL {0} \
    CONFIG.C_GPIO_WIDTH {3} \
    CONFIG.C_ALL_OUTPUTS {1}] $gpio

# Clock generation and synchronized board reset.
connect_bd_net [get_bd_ports sysclk] [get_bd_pins clk_wiz_0/clk_in1]
connect_bd_net [get_bd_ports btn_reset] [get_bd_pins clk_wiz_0/reset] [get_bd_pins proc_sys_reset_0/ext_reset_in]
connect_bd_net [get_bd_pins clk_wiz_0/locked] [get_bd_pins proc_sys_reset_0/dcm_locked]
connect_bd_net [get_bd_pins clk_wiz_0/clk_out1] \
    [get_bd_pins proc_sys_reset_0/slowest_sync_clk] \
    [get_bd_pins picorv32_axi_bd_0/clk] \
    [get_bd_pins vit_inference_fixed_0/ap_clk] \
    [get_bd_pins smartconnect_0/aclk] \
    [get_bd_pins axi_bram_ctrl_0/s_axi_aclk] \
    [get_bd_pins axi_gpio_0/s_axi_aclk]

connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] \
    [get_bd_pins picorv32_axi_bd_0/resetn] \
    [get_bd_pins vit_inference_fixed_0/ap_rst_n] \
    [get_bd_pins axi_bram_ctrl_0/s_axi_aresetn] \
    [get_bd_pins axi_gpio_0/s_axi_aresetn]
connect_bd_net [get_bd_pins proc_sys_reset_0/interconnect_aresetn] [get_bd_pins smartconnect_0/aresetn]

# CPU and HLS DMA share one AXI BRAM controller and one 32 KiB BRAM.
connect_bd_intf_net [get_bd_intf_pins picorv32_axi_bd_0/M_AXI] [get_bd_intf_pins smartconnect_0/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins vit_inference_fixed_0/m_axi_gmem] [get_bd_intf_pins smartconnect_0/S01_AXI]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M00_AXI] [get_bd_intf_pins axi_bram_ctrl_0/S_AXI]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M01_AXI] [get_bd_intf_pins vit_inference_fixed_0/s_axi_control]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M02_AXI] [get_bd_intf_pins axi_gpio_0/S_AXI]
connect_bd_intf_net [get_bd_intf_pins axi_bram_ctrl_0/BRAM_PORTA] [get_bd_intf_pins blk_mem_gen_0/BRAM_PORTA]
connect_bd_net [get_bd_pins axi_gpio_0/gpio_io_o] [get_bd_ports led_class]
connect_bd_net [get_bd_pins picorv32_axi_bd_0/trap] [get_bd_ports trap]

# At 100 MHz the fixed-point HLS core uses the same clock target as its synthesis run.
assign_bd_address -offset 0x00000000 -range 0x00008000 -target_address_space [get_bd_addr_spaces picorv32_axi_bd_0/M_AXI] [get_bd_addr_segs axi_bram_ctrl_0/S_AXI/Mem0]
assign_bd_address -offset 0x40000000 -range 0x00010000 -target_address_space [get_bd_addr_spaces picorv32_axi_bd_0/M_AXI] [get_bd_addr_segs vit_inference_fixed_0/s_axi_control/Reg]
assign_bd_address -offset 0x40010000 -range 0x00010000 -target_address_space [get_bd_addr_spaces picorv32_axi_bd_0/M_AXI] [get_bd_addr_segs axi_gpio_0/S_AXI/Reg]
assign_bd_address -offset 0x00000000 -range 0x00008000 -target_address_space [get_bd_addr_spaces vit_inference_fixed_0/m_axi_gmem] [get_bd_addr_segs axi_bram_ctrl_0/S_AXI/Mem0]
# The accelerator's data master only reads/writes the shared BRAM; it must not
# access the CPU-only control and LED registers on the same SmartConnect.
exclude_bd_addr_seg -target_address_space [get_bd_addr_spaces vit_inference_fixed_0/Data_m_axi_gmem] [get_bd_addr_segs vit_inference_fixed_0/s_axi_control/Reg]
exclude_bd_addr_seg -target_address_space [get_bd_addr_spaces vit_inference_fixed_0/Data_m_axi_gmem] [get_bd_addr_segs axi_gpio_0/S_AXI/Reg]

# Validate and generate the design with empty BRAM. For this custom PicoRV32
# BD, firmware is merged into the implemented bitstream using UpdateMEM.
validate_bd_design
save_bd_design
set bd_file [get_files -quiet */ecg_vit_system.bd]
generate_target all $bd_file
set bd_wrapper [make_wrapper -files $bd_file -top]
add_files -norecurse [list $bd_wrapper]
set_property top zybo_vit_axi_top [current_fileset]

puts "Created ecg_vit_system.bd and set zybo_vit_axi_top as project top."
puts "Address map: BRAM 0x00000000-0x00007FFF; HLS 0x40000000; AXI GPIO 0x40010000."
puts "BRAM is intentionally uninitialized here; merge firmware after implementation with UpdateMEM."
puts "Next: Run Synthesis, resolve any reported issue, then Implementation and Bitstream."
