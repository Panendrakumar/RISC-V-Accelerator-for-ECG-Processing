# Read the v2 firmware mailbox (BRAM 0x6000-0x6037) through JTAG-to-AXI.
# Does NOT reprogram the FPGA. Run with:
#   vivado -mode batch -nojournal -nolog -source read_mailbox.tcl
set ltx [file normalize [file join [file dirname [info script]] .. ECG_ViT_Zybo_v2 ECG_ViT_Zybo_v2.runs impl_1 zybo_vit_v2_top.ltx]]
open_hw_manager
connect_hw_server -allow_non_jtag
open_hw_target
set dev [lindex [get_hw_devices xc7z010*] 0]
current_hw_device $dev
set_property PROBES.FILE $ltx $dev
set_property FULL_PROBES.FILE $ltx $dev
refresh_hw_device -update_hw_probes false $dev
set axi [lindex [get_hw_axis] 0]
if {$axi eq ""} { error "No JTAG-to-AXI master found. Is zybo_vit_v2_interactive.bit programmed?" }
reset_hw_axi $axi
create_hw_axi_txn -force mb_rd $axi -address 00006000 -len 14 -type read
run_hw_axi -quiet [get_hw_axi_txns mb_rd]
set data [get_property DATA [get_hw_axi_txns mb_rd]]
puts "RAW_DATA=$data"
