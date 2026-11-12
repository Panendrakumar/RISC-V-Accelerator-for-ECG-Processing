# Build the v2 interactive ECG demo in a NEW Vivado project.
# The original ECG_ViT_Zybo project and its bitstreams are not modified.
#
# Run from PowerShell (V: must point at the project root, see README.md):
#   C:\Xilinx\Vivado\2023.2\bin\vivado.bat -mode batch -source V:/02_Vivado_Zybo/v2_interactive/build_v2_project.tcl
#
# Adds compared with v1:
#   - AXI GPIO channel 2 (inputs): SW0-SW3 and BTN0-BTN3
#   - AXI GPIO channel 1 widened to 6 outputs: LD0-LD2 class code + RGB LED6 (R,G,B)
#   - JTAG-to-AXI Master: the laptop can read/write BRAM over the existing USB/JTAG cable
#   - no duplicate sysclk create_clock (removes the v1 TIMING-6 critical warnings)

set v2_dir   [file dirname [file normalize [info script]]]
set root     [file normalize [file join $v2_dir .. ..]]
set proj_dir [file join $v2_dir ECG_ViT_Zybo_v2]
set hls_ip_repo [file join $root 03_HW_SW_Validation vitis_hls z7_tiny_ecg_vit ecg_vit_z7_fixed solution1 impl ip]
set picorv32_src [file join $root 10_RISC_V core riscv_core picorv32.v]
set cpu_wrapper  [file join $root 02_Vivado_Zybo ECG_ViT_Zybo hls_integration picorv32_axi_bd.v]
set top_src      [file join $v2_dir zybo_vit_v2_top.v]
set xdc_src      [file join $v2_dir zybo_z7_10_v2.xdc]

foreach required [list $hls_ip_repo $picorv32_src $cpu_wrapper $top_src $xdc_src] {
    if {![file exists $required]} { error "Required input not found: $required" }
}
if {[file exists $proj_dir]} {
    error "$proj_dir already exists. Rename or delete it before rebuilding from scratch."
}

create_project ECG_ViT_Zybo_v2 $proj_dir -part xc7z010clg400-1
if {[catch {set_property board_part digilentinc.com:zybo-z7-10:part0:1.1 [current_project]} msg]} {
    puts "NOTE: board part not set ($msg); the part number is still xc7z010clg400-1."
}
set_property target_language Verilog [current_project]
set_property IP_REPO_PATHS [list $hls_ip_repo] [current_project]
update_ip_catalog -rebuild

add_files -norecurse [list $picorv32_src $cpu_wrapper $top_src]
add_files -fileset constrs_1 -norecurse [list $xdc_src]
update_compile_order -fileset sources_1

# ---------------- Block design ----------------
create_bd_design ecg_vit_system
current_bd_design ecg_vit_system

set sysclk [create_bd_port -dir I -type clk -freq_hz 125000000 sysclk]
set reset_button [create_bd_port -dir I -type rst btn_reset]
set_property CONFIG.POLARITY ACTIVE_HIGH $reset_button
create_bd_port -dir O -from 5 -to 0 gpio_out
create_bd_port -dir I -from 7 -to 0 gpio_in
create_bd_port -dir O trap
create_bd_port -dir O -type clk clk_100

set clk_wiz [create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz:6.0 clk_wiz_0]
set_property -dict [list \
    CONFIG.PRIM_SOURCE {Single_ended_clock_capable_pin} \
    CONFIG.PRIM_IN_FREQ {125.000} \
    CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {100.000} \
    CONFIG.USE_RESET {true} \
    CONFIG.RESET_TYPE {ACTIVE_HIGH} \
    CONFIG.USE_LOCKED {true}] $clk_wiz

create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 proc_sys_reset_0
create_bd_cell -type module -reference picorv32_axi_bd picorv32_axi_bd_0
create_bd_cell -type ip -vlnv xilinx.com:hls:vit_inference_fixed:1.0 vit_inference_fixed_0

set jtag_vlnv [lindex [lsort [get_ipdefs -all xilinx.com:ip:jtag_axi:*]] end]
if {$jtag_vlnv eq ""} { error "JTAG-to-AXI Master IP not found in the IP catalog." }
create_bd_cell -type ip -vlnv $jtag_vlnv jtag_axi_0

set smart [create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:1.0 smartconnect_0]
set_property -dict [list CONFIG.NUM_SI {3} CONFIG.NUM_MI {3}] $smart

set bram_ctrl [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_bram_ctrl:4.1 axi_bram_ctrl_0]
set_property -dict [list CONFIG.DATA_WIDTH {32} CONFIG.SINGLE_PORT_BRAM {1} CONFIG.READ_LATENCY {1}] $bram_ctrl

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
    CONFIG.C_IS_DUAL {1} \
    CONFIG.C_GPIO_WIDTH {6} \
    CONFIG.C_ALL_OUTPUTS {1} \
    CONFIG.C_GPIO2_WIDTH {8} \
    CONFIG.C_ALL_INPUTS_2 {1}] $gpio

# Clocks and resets
connect_bd_net [get_bd_ports sysclk] [get_bd_pins clk_wiz_0/clk_in1]
connect_bd_net [get_bd_ports btn_reset] [get_bd_pins clk_wiz_0/reset] [get_bd_pins proc_sys_reset_0/ext_reset_in]
connect_bd_net [get_bd_pins clk_wiz_0/locked] [get_bd_pins proc_sys_reset_0/dcm_locked]
connect_bd_net [get_bd_pins clk_wiz_0/clk_out1] \
    [get_bd_ports clk_100] \
    [get_bd_pins proc_sys_reset_0/slowest_sync_clk] \
    [get_bd_pins picorv32_axi_bd_0/clk] \
    [get_bd_pins vit_inference_fixed_0/ap_clk] \
    [get_bd_pins jtag_axi_0/aclk] \
    [get_bd_pins smartconnect_0/aclk] \
    [get_bd_pins axi_bram_ctrl_0/s_axi_aclk] \
    [get_bd_pins axi_gpio_0/s_axi_aclk]
connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] \
    [get_bd_pins picorv32_axi_bd_0/resetn] \
    [get_bd_pins vit_inference_fixed_0/ap_rst_n] \
    [get_bd_pins jtag_axi_0/aresetn] \
    [get_bd_pins axi_bram_ctrl_0/s_axi_aresetn] \
    [get_bd_pins axi_gpio_0/s_axi_aresetn]
connect_bd_net [get_bd_pins proc_sys_reset_0/interconnect_aresetn] [get_bd_pins smartconnect_0/aresetn]

# AXI fabric: three masters (CPU, accelerator DMA, laptop JTAG) share BRAM/HLS/GPIO
connect_bd_intf_net [get_bd_intf_pins picorv32_axi_bd_0/M_AXI] [get_bd_intf_pins smartconnect_0/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins vit_inference_fixed_0/m_axi_gmem] [get_bd_intf_pins smartconnect_0/S01_AXI]
connect_bd_intf_net [get_bd_intf_pins jtag_axi_0/M_AXI] [get_bd_intf_pins smartconnect_0/S02_AXI]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M00_AXI] [get_bd_intf_pins axi_bram_ctrl_0/S_AXI]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M01_AXI] [get_bd_intf_pins vit_inference_fixed_0/s_axi_control]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M02_AXI] [get_bd_intf_pins axi_gpio_0/S_AXI]
connect_bd_intf_net [get_bd_intf_pins axi_bram_ctrl_0/BRAM_PORTA] [get_bd_intf_pins blk_mem_gen_0/BRAM_PORTA]

connect_bd_net [get_bd_pins axi_gpio_0/gpio_io_o] [get_bd_ports gpio_out]
connect_bd_net [get_bd_ports gpio_in] [get_bd_pins axi_gpio_0/gpio2_io_i]
connect_bd_net [get_bd_pins picorv32_axi_bd_0/trap] [get_bd_ports trap]

# Address map (same as v1 for CPU and accelerator)
set bram_seg [get_bd_addr_segs axi_bram_ctrl_0/S_AXI/Mem0]
set hls_seg  [get_bd_addr_segs vit_inference_fixed_0/s_axi_control/Reg]
set gpio_seg [get_bd_addr_segs axi_gpio_0/S_AXI/Reg]
set cpu_space  [get_bd_addr_spaces -of_objects [get_bd_cells picorv32_axi_bd_0]]
set hls_space  [get_bd_addr_spaces vit_inference_fixed_0/Data_m_axi_gmem]
set jtag_space [get_bd_addr_spaces -of_objects [get_bd_cells jtag_axi_0]]
puts "Address spaces: CPU=$cpu_space HLS=$hls_space JTAG=$jtag_space"

foreach space [list $cpu_space $jtag_space] {
    assign_bd_address -offset 0x00000000 -range 0x00008000 -target_address_space $space $bram_seg
    assign_bd_address -offset 0x40000000 -range 0x00010000 -target_address_space $space $hls_seg
    assign_bd_address -offset 0x40010000 -range 0x00010000 -target_address_space $space $gpio_seg
}
assign_bd_address -offset 0x00000000 -range 0x00008000 -target_address_space $hls_space $bram_seg
foreach seg [list $hls_seg $gpio_seg] {
    if {[catch {exclude_bd_addr_seg -target_address_space $hls_space $seg} msg]} {
        puts "NOTE: exclude for $seg: $msg"
    }
}

validate_bd_design
save_bd_design
set bd_file [get_files ecg_vit_system.bd]
generate_target all $bd_file
set wrapper [make_wrapper -files $bd_file -top]
add_files -norecurse [list $wrapper]
set_property top zybo_vit_v2_top [current_fileset]
update_compile_order -fileset sources_1

# ---------------- Synthesis, implementation, bitstream ----------------
launch_runs synth_1 -jobs 8
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} { error "Synthesis failed. See $proj_dir/ECG_ViT_Zybo_v2.runs/synth_1/runme.log" }
launch_runs impl_1 -to_step write_bitstream -jobs 8
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} { error "Implementation failed. See $proj_dir/ECG_ViT_Zybo_v2.runs/impl_1/runme.log" }

open_run impl_1
set rpt_dir [file join $v2_dir reports]
file mkdir $rpt_dir
report_utilization    -file [file join $rpt_dir utilization.rpt]
report_timing_summary -file [file join $rpt_dir timing_summary.rpt]
report_clocks         -file [file join $rpt_dir clocks.rpt]
report_methodology    -file [file join $rpt_dir methodology.rpt]

# MMI for firmware merging (AMD AR 63041 script already in the v1 folder)
cd $v2_dir
source [file join $root 02_Vivado_Zybo ECG_ViT_Zybo write_mmi.tcl]
write_mmi blk_mem_gen_0

set wns [get_property SLACK [get_timing_paths -delay_type max]]
set whs [get_property SLACK [get_timing_paths -delay_type min]]
puts "V2 BUILD DONE. WNS=$wns WHS=$whs"
puts "Bitstream: [file join $proj_dir ECG_ViT_Zybo_v2.runs impl_1 zybo_vit_v2_top.bit]"
puts "MMI:       [file join $v2_dir blk_mem_gen_0.mmi]"
