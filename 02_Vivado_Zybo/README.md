# Zybo Z7-10 hardware implementation

Updated: 2026-11-11

## Board

Digilent Zybo Z7-10, Zynq-7000 part `xc7z010clg400-1`, Vivado 2023.2. The Zynq has an ARM Cortex-A9 processing system, but this design does not use it: a **PicoRV32 RISC-V softcore** is instantiated in the programmable logic and controls the ECG accelerator.

## Implemented system

```text
125 MHz sysclk → Clocking Wizard (100 MHz) → Processor System Reset
PicoRV32 (AXI master) ──┐
HLS IP m_axi_gmem ──────┼─ AXI SmartConnect ─┬─ AXI BRAM Controller + 32 KiB BRAM (firmware, beat, logits, mailbox)
JTAG-to-AXI (v2 only) ──┘                    ├─ AXI GPIO (LEDs; v2 also switches/buttons)
                                             └─ HLS IP s_axi_control (vit_inference_fixed, Q6.10)
```

Address map: BRAM `0x00000000–0x00007FFF`; HLS control `0x40000000` (ECG pointer `0x10`, RR `0x1C`, output `0x28`); AXI GPIO `0x40010000`. Firmware is merged into the bitstream with UpdateMEM using the MMI from AMD Answer Record 63041 (`write_mmi.tcl`).

## Folders

| Folder | Contents | Status |
|---|---|---|
| `ECG_ViT_Zybo/` | v1 project: block design (`hls_integration/create_ecg_vit_bd.tcl`), single-beat and known-beat firmware | Built, programmed. Single beat shows N; known-beat self-test 9/9 on the board. 9,571 LUT (54.4%), 36 BRAM tiles (60.0%), 43 DSP |
| `v2_interactive/` | v2 project built by script: switches/buttons, RGB LED, JTAG-to-AXI, cycle counter, result mailbox, host streaming scripts | Built, programmed. Self-test 16/16; full test split measured on the board (below) |
| `demo_bitstreams/` | Backup of the working v1 bitstreams, MMI and firmware ELFs | Ready to program |

## Measured on the board (v2 evaluation build)

| Measure | Result |
|---|---|
| Test beats streamed / completed | 20,136 / 20,136 |
| FPGA accuracy | 98.6442% (19,863 correct) |
| FPGA macro-F1 | 0.7244 |
| Same class as Q6.10 software / FP32 software | 99.995% / 99.970% |
| Latency per beat (PicoRV32 `rdcycle`) | 3,128,915 cycles = 31.29 ms at 100 MHz |
| Utilization | 12,816 LUT (72.8%), 15,597 FF (44.3%), 38.5 BRAM tiles (64.2%), 43 DSP (53.8%) |
| Timing at 100 MHz | WNS +0.193 ns, WHS +0.018 ns (met) |

Evidence: `../03_HW_SW_Validation/hardware_outputs/fpga_stream/20261110_232934_0_20136/` and `v2_interactive/reports/`. The test split is beat-level (not patient-independent) and Q has 3 test beats. Beats reach the board over JTAG from the laptop; there is no live ECG input.

## Path note

Vivado's command line fails on the spaces in the project path. Map the project to `V:` before running scripts:

```powershell
subst V: "<path-to-your-repo-folder>"
```

## Not done

Live ECG front end, automatic R-peak detection, power measurement, bit-exact comparison with the HLS C model.
