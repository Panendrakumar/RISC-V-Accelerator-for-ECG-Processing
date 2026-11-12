# Run from this directory via a no-space drive mapping, for example R:.
open_project -reset ecg_vit_z7_fixed
set_top vit_inference_fixed
add_files vit_inference_fixed.cpp -cflags "-std=c++14 -I."
add_files -tb vit_inference_fixed_tb.cpp -cflags "-std=c++14 -I."
open_solution -reset solution1 -flow_target vivado
set_part {xc7z010clg400-1}
create_clock -period 10.0 -name default
config_compile -pipeline_loops 0
csim_design
csynth_design
export_design -format ip_catalog -rtl verilog
exit
