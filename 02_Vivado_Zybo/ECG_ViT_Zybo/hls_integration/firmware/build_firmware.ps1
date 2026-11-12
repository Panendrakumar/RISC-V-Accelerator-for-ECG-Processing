$ErrorActionPreference = 'Stop'
$FirmwareDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $FirmwareDir '..\..\..\..')).Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$CompilerDir = 'C:\RISC-V\xpack-riscv-none-elf-gcc-15.2.0-1\bin'
$Gcc = Join-Path $CompilerDir 'riscv-none-elf-gcc.exe'
$Objcopy = Join-Path $CompilerDir 'riscv-none-elf-objcopy.exe'

if (!(Test-Path -LiteralPath $Gcc) -or !(Test-Path -LiteralPath $Objcopy)) {
    throw "RISC-V xPack GCC/objcopy not found under $CompilerDir"
}

Push-Location $FirmwareDir
try {
    & $Python .\generate_demo_header.py
    if ($LASTEXITCODE -ne 0) { throw 'Golden vector header generation failed.' }
    $CompilerFlags = @(
        '-march=rv32i', '-mabi=ilp32', '-mno-relax', '-msmall-data-limit=0', '-Os',
        '-ffreestanding', '-fno-builtin', '-nostdlib',
        '-Wl,--no-relax', '-Wl,-T,linker.ld', '-Wl,-e,_start', '-Wl,-Map,ecg_vit_smoke.map',
        '.\startup.S', '.\ecg_vit_smoke.c', '-o', '.\ecg_vit_smoke.elf'
    )
    & $Gcc @CompilerFlags
    if ($LASTEXITCODE -ne 0) { throw 'RISC-V firmware compile/link failed.' }
    & $Objcopy -O binary .\ecg_vit_smoke.elf .\ecg_vit_smoke.bin
    if ($LASTEXITCODE -ne 0) { throw 'ELF to binary conversion failed.' }
    & $Python .\bin_to_coe.py .\ecg_vit_smoke.bin .\riscv_vit_demo.coe
    if ($LASTEXITCODE -ne 0) { throw 'COE/MEM generation failed.' }
}
finally {
    Pop-Location
}
