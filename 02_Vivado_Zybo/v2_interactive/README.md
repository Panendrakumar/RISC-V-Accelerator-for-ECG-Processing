# v2 interactive ECG beat classifier (Zybo Z7-10)

A separate Vivado project built from scripts in this folder. The v1 project
(`../ECG_ViT_Zybo`) and its bitstreams are not modified. The working v1
demo is backed up in `../demo_bitstreams/`.

## What changed from v1

| Item | v1 | v2 |
|---|---|---|
| Inputs | BTN0 reset only | SW0-SW3 + BTN0-BTN3 readable by the RISC-V (AXI GPIO ch2) |
| Outputs | LD2:LD0 class, LD3 trap | same + RGB LED6 class colour |
| Laptop link | none | JTAG-to-AXI Master over the existing USB/JTAG cable (no extra hardware) |
| Timing | sysclk constrained twice (TIMING-6) | single clock definition from the Clocking Wizard |
| Latency | not measured | PicoRV32 `rdcycle` start-to-done count stored in BRAM (0x6014) |

Accelerator, model, Q6.10 weights and address map for CPU/accelerator are unchanged.

## Board controls

| Control | Action |
|---|---|
| SW3..SW0 | choose stored beat 0-15 (binary, SW0 = lowest bit, switch up = 1) |
| BTN1 | classify the selected beat on the FPGA |
| BTN2 (hold) | show the TRUE label of the selected beat (RGB off) |
| BTN3 | self-test: classify all 16 stored beats, compare with Q6.10 reference |
| BTN0 | reset |

LD2:LD0 code: N=001, S=010, V=011, F=100, Q=101. RGB: N green, S yellow,
V red, F magenta, Q blue. LD3 = CPU trap. Self-test ends with 111 + green when
every beat matches; blinking 110 + red means a mismatch.

## Stored beats (from `firmware/demo_beats.json`)

| SW (3..0) | test # | true | FP32 model | Q6.10 / expected FPGA | why it is included |
|---|---|---|---|---|---|
| 0000 | 0 | N | N | N | golden beat |
| 0001 | 1 | N | N | N | golden beat |
| 0010 | 7 | S | S | S | golden beat |
| 0011 | 41 | S | S | S | golden beat |
| 0100 | 4 | V | V | V | golden beat |
| 0101 | 32 | V | V | V | golden beat |
| 0110 | 201 | F | F | F | golden beat |
| 0111 | 483 | F | F | F | golden beat |
| 1000 | 1393 | Q | N | N | golden beat; model misses Q |
| 1001 | 353 | S | N | N | model mistake |
| 1010 | 57 | F | N | N | model mistake |
| 1011 | 714 | V | F | F | model mistake |
| 1100 | 59 | N | S | S | model mistake (false alarm) |
| 1101 | 576 | V | N | N | model mistake |
| 1110 | 2265 | Q | V | V | rare Q class |
| 1111 | 5482 | Q | V | V | rare Q class |

Beats 9-15 were picked on purpose to show where the model is wrong. They are
not a random sample and must not be used to estimate accuracy. On the board,
the BTN3 self-test matched the Q6.10 reference on all 16 beats.

## Measured results (full test split, 2026-11-10)

All 20,136 test beats were streamed from the laptop over JTAG-to-AXI and
classified by the accelerator on the board
(`03_HW_SW_Validation/hardware_outputs/fpga_stream/20261110_232934_0_20136/`).

| Measure | FPGA | Software reference |
|---|---:|---:|
| Accuracy | 98.6442% (19,863/20,136) | FP32 98.6343%, Q6.10 98.6393% |
| Macro-F1 | 0.7244 | FP32 0.724389, Q6.10 0.7243 |
| Same class as Q6.10 / FP32 | 99.995% / 99.970% | |
| Latency per beat | 3,128,915 cycles = 31.29 ms at 100 MHz | HLS estimate 3,102,112 cycles |

Implementation (`reports/`): 12,816 LUT (72.8%), 15,597 FF (44.3%), 38.5 BRAM
tiles (64.2%), 43 DSP (53.8%); timing met at 100 MHz (WNS +0.193 ns, WHS
+0.018 ns). The split is beat-level, not patient-independent; Q has 3 test beats
and F1 = 0. The JTAG transfer (about 82 ms per beat) is a test path and is not
part of the latency.

## Stream test beats from the laptop

Program `zybo_vit_v2_interactive.bit` together with
`ECG_ViT_Zybo_v2\ECG_ViT_Zybo_v2.runs\impl_1\zybo_vit_v2_top.ltx`, close
Hardware Manager, then run through the `V:` drive:

```powershell
V:\.venv\Scripts\python.exe V:\02_Vivado_Zybo\v2_interactive\host\stream_test_beats.py --start 0 --count 50
V:\.venv\Scripts\python.exe V:\02_Vivado_Zybo\v2_interactive\host\stream_test_beats.py --all
V:\.venv\Scripts\python.exe V:\02_Vivado_Zybo\v2_interactive\host\make_fpga_result_figure.py <run folder>
```

A partial run is a sample of the test split; only a completed `--all` run is the
FPGA test accuracy. The full run took about 27 minutes. `host\read_mailbox.tcl`
reads the last result from the mailbox at `0x6000`.

## Rebuild

`V:` is a `subst` mapping of the project root; it disappears after a restart.


```powershell
subst V: "<path-to-your-repo-folder>"
C:\Xilinx\Vivado\2023.2\bin\vivado.bat -mode batch -source V:/02_Vivado_Zybo/v2_interactive/build_v2_project.tcl
powershell -NoProfile -ExecutionPolicy Bypass -File V:\02_Vivado_Zybo\v2_interactive\firmware\build_interactive.ps1
```

Then merge the firmware (MMI is written to this folder by the build script):

```powershell
C:\Xilinx\Vivado\2023.2\bin\updatemem.bat -force --meminfo V:\02_Vivado_Zybo\v2_interactive\blk_mem_gen_0.mmi --data V:\02_Vivado_Zybo\v2_interactive\firmware\ecg_vit_interactive.elf --bit V:\02_Vivado_Zybo\v2_interactive\ECG_ViT_Zybo_v2\ECG_ViT_Zybo_v2.runs\impl_1\zybo_vit_v2_top.bit --proc dummy --out V:\02_Vivado_Zybo\v2_interactive\zybo_vit_v2_interactive.bit
```

Program `zybo_vit_v2_interactive.bit` from Hardware Manager.
