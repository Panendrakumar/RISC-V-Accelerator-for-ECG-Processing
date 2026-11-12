# PicoRV32 + Q6.10 ViT Integration

This folder prepares a first end-to-end PL inference demo for the Zybo Z7-10.
It keeps the existing smoke-test top intact and adds a separate IP Integrator
design driven by the PicoRV32 AXI4-Lite wrapper.

## What the demo does

The RISC-V starts from a BRAM image, points the HLS accelerator at one saved
198-sample ECG beat and two Q6.10 RR features, starts inference, polls the HLS
`ap_done` bit, then displays the argmax class on LD2:LD0. The saved golden
vector is expected to classify as `N` (class index 0). LD3 indicates a CPU
trap. While inference runs, LD2:LD0 show `111`; after an `N` result, they show
`001`. The input is a fixed demonstration beat, not a live ECG stream.

## Build the RISC-V BRAM image

From the project root in PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\02_Vivado_Zybo\ECG_ViT_Zybo\hls_integration\firmware\build_firmware.ps1"
```

This uses the installed xPack GCC under `C:\RISC-V`, quantizes the first
preserved golden vector into signed Q6.10, and links a bare-metal RV32I ELF
image into the 32 KiB BRAM address range. The `.coe` and `.mem` outputs are
retained for standalone memory initialization workflows. This custom PicoRV32
IP Integrator design uses the ELF with UpdateMEM after implementation.
It does not train or change the model.

## Create the Vivado block design

Open the existing `02_Vivado_Zybo\ECG_ViT_Zybo\ECG_ViT_Zybo.xpr` project in
Vivado 2023.2. In the Tcl Console, source this script (use braces because the
path has spaces):

```tcl
source {V:/02_Vivado_Zybo/ECG_ViT_Zybo/hls_integration/create_ecg_vit_bd.tcl}
```

The script adds the HLS IP repository, PicoRV32 AXI wrapper, shared 32 KiB
BRAM, AXI GPIO, 100 MHz clock and synchronized reset, then creates
`ecg_vit_system.bd`. It sets `zybo_vit_axi_top` as the new project top and
retains the previous smoke-test RTL files. The map is:

| Address | Function |
|---|---|
| `0x00000000-0x00007FFF` | Shared 32 KiB BRAM for CPU code/data and HLS input/output |
| `0x40000000` | HLS AXI-Lite control and pointer registers |
| `0x40010000` | Three-bit AXI GPIO output to LD2:LD0 |

The Block Memory Generator is intentionally left with `MEM_FILE=NONE`.
Vivado resets the initialization-file property when this BMG is used with the
AXI BRAM Controller, so do not source `load_bram_mem.tcl` or try to attach the
image through `CONFIG.MEM_FILE`. Generate the bitstream first, then merge the
firmware with UpdateMEM as described below.

The HLS pointer offsets are `ECG=0x10`, `RR=0x1C`, and `logits=0x28` (each
also has a high 32-bit register). The HLS control register is at offset `0x00`.

## Build and run

After the block design output products have been generated:

1. In Flow Navigator, click **Run Synthesis** and accept the default settings.
2. If synthesis completes, click **Run Implementation**; then choose **Generate Bitstream**.
3. Open **Open Implemented Design**. Download AMD's `write_mmi.tcl` attachment from [Answer Record 63041](https://adaptivesupport.amd.com/s/article/63041?language=en_US), save it in the Vivado project folder, and source it in the Tcl Console:

   ```tcl
   source -quiet {V:/02_Vivado_Zybo/ECG_ViT_Zybo/write_mmi.tcl}
   write_mmi blk_mem_gen_0
   ```

   Use `blk_mem_gen_0` because the implemented BRAM primitives in this design
   are instantiated beneath that BMG cell (the AXI BRAM Controller itself has
   no BRAM primitives). The command should report the generated `.mmi` file.
   This AMD workaround is
   best-effort, intended for block designs with a BRAM controller, and supports
   32-bit memory data.
4. In the Vivado Tcl Console, merge the ELF into the implemented bitstream.
   Replace `<mmi-file>` with the exact path printed above:

   ```tcl
   updatemem -force --meminfo {<mmi-file>} --data {V:/02_Vivado_Zybo/ECG_ViT_Zybo/hls_integration/firmware/ecg_vit_smoke.elf} --bit {V:/02_Vivado_Zybo/ECG_ViT_Zybo/ECG_ViT_Zybo.runs/impl_1/zybo_vit_axi_top.bit} --proc dummy --out {V:/02_Vivado_Zybo/ECG_ViT_Zybo/ECG_ViT_Zybo.runs/impl_1/zybo_vit_firmware.bit}
   ```

5. In **Hardware Manager**, program the FPGA with `zybo_vit_firmware.bit` (the
   Updatemem output), not the original bitstream. Release `BTN_RESET` if it is
   pressed. Expect LD2:LD0 to show `111` during inference and `001` when the
   demo beat is classified as `N`; LD3 indicates a CPU trap.

## Status (2026-11-11)

This design has been synthesized, implemented and programmed. With `ecg_vit_smoke.elf` the demo beat shows `001` (N). With `ecg_vit_known_beats.elf` (built by `firmware/build_known_beats.ps1`) the board classifies 9 golden beats in turn (LED sequence N, N, S, S, V, V, F, F, N, then `111` when all match; blinking `110` means a mismatch); all 9 matched. Implemented use: 9,571 LUT (54.4%), 36 BRAM tiles (60.0%), 43 DSP.

The working bitstreams and ELFs are backed up in `../../demo_bitstreams/`. The interactive build and the full test-split FPGA measurement (98.6442% accuracy on 20,136 beats, 31.29 ms per beat) are in `../../v2_interactive/`.

`V:` in the commands above is a `subst` mapping of the project root (Vivado fails on the spaces in the real path). Run `subst V: "<project root>"` again after a restart.
