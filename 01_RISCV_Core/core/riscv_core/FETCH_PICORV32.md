# Fetch official PicoRV32

The official PicoRV32 source is maintained by YosysHQ under an ISC-style license. This project intentionally does not ship an altered/reimplemented CPU. On an internet-connected Windows machine run:

`powershell -ExecutionPolicy Bypass -File fetch_picorv32.ps1`

On Linux:

`bash fetch_picorv32.sh`

The script downloads the upstream `picorv32.v` into this directory. Then add it to the Quartus project. Configure `ENABLE_COUNTERS=0`, `ENABLE_COUNTERS64=0`, `ENABLE_REGS_16_31=1`, `ENABLE_REGS_DUALPORT=0`, `COMPRESSED_ISA=0`, `ENABLE_MUL=0`, `ENABLE_DIV=0`, `ENABLE_IRQ=0` for a small RV32I configuration.
