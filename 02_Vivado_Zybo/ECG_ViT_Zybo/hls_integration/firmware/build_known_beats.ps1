$ErrorActionPreference = 'Stop'
$FirmwareDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $FirmwareDir '..\..\..\..')).Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$CompilerDir = 'C:\RISC-V\xpack-riscv-none-elf-gcc-15.2.0-1\bin'
$Gcc = Join-Path $CompilerDir 'riscv-none-elf-gcc.exe'

if (!(Test-Path -LiteralPath $Gcc)) {
    throw "RISC-V xPack GCC not found under $CompilerDir"
}
if (!(Test-Path -LiteralPath $Python)) {
    throw "Project Python not found at $Python"
}

Push-Location $FirmwareDir
try {
    & $Python .\generate_known_beats_header.py
    if ($LASTEXITCODE -ne 0) { throw 'Known-beat header generation failed.' }
    $CompilerFlags = @(
        '-march=rv32i', '-mabi=ilp32', '-mno-relax', '-msmall-data-limit=0', '-Os',
        '-ffreestanding', '-fno-builtin', '-nostdlib',
        '-Wl,--no-relax', '-Wl,-T,linker.ld', '-Wl,-e,_start', '-Wl,-Map,ecg_vit_known_beats.map',
        '.\startup.S', '.\ecg_vit_known_beats.c', '-o', '.\ecg_vit_known_beats.elf'
    )
    & $Gcc @CompilerFlags
    if ($LASTEXITCODE -ne 0) { throw 'RISC-V firmware compile/link failed.' }
    $Size = (Get-Item .\ecg_vit_known_beats.elf).Length
    Write-Host "Built ecg_vit_known_beats.elf ($Size bytes). The existing ecg_vit_smoke.elf was not touched."
}
finally {
    Pop-Location
}
