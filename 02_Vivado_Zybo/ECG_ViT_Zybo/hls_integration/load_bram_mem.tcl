# Firmware initialization through BMG CONFIG.MEM_FILE is not supported for
# this AXI BRAM Controller design: Vivado resets that setting to NONE.
# Keep this guard so old instructions fail with a clear explanation.
error "Do not use load_bram_mem.tcl: Vivado clears BMG MEM_FILE in this design. Run synthesis/implementation with empty BRAM, then use the AMD UpdateMEM flow described in hls_integration/README.md."
