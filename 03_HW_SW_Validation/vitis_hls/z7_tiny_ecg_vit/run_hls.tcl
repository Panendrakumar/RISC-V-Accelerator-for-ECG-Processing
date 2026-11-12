# Run from this directory with Vitis HLS 2023.2:
#   vitis_hls -f run_hls.tcl
open_project -reset ecg_vit_z7
set_top vit_inference
add_files vit_inference.cpp -cflags "-std=c++14 -I."
add_files -tb vit_inference_tb.cpp -cflags "-std=c++14 -I."
open_solution -reset solution1 -flow_target vivado
set_part {xc7z010clg400-1}
create_clock -period 10.0 -name default
config_compile -pipeline_loops 0
csim_design
csynth_design
export_design -format ip_catalog -rtl verilog
exit
