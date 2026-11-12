$ErrorActionPreference = 'Stop'
$FirmwareDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $FirmwareDir '..\..\..')).Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$Startup = Join-Path $ProjectRoot '02_Vivado_Zybo\ECG_ViT_Zybo\hls_integration\firmware\startup.S'
$CompilerDir = 'C:\RISC-V\xpack-riscv-none-elf-gcc-15.2.0-1\bin'
$Gcc = Join-Path $CompilerDir 'riscv-none-elf-gcc.exe'
$Size = Join-Path $CompilerDir 'riscv-none-elf-size.exe'

foreach ($p in @($Gcc, $Python, $Startup)) {
    if (!(Test-Path -LiteralPath $p)) { throw "Not found: $p" }
}

Push-Location $FirmwareDir
try {
    if (!(Test-Path .\demo_beats_data.h) -or $args -contains '-Reselect') {
        & $Python .\select_demo_beats.py
        if ($LASTEXITCODE -ne 0) { throw 'Demo beat selection failed.' }
    }
    $Flags = @(
        '-march=rv32i_zicsr', '-mabi=ilp32', '-mno-relax', '-msmall-data-limit=0', '-Os',
        '-ffreestanding', '-fno-builtin', '-nostdlib',
        '-Wl,--no-relax', '-Wl,-T,linker_v2.ld', '-Wl,-e,_start', '-Wl,-Map,ecg_vit_interactive.map',
        '-Wl,--no-warn-rwx-segments',
        $Startup, '.\ecg_vit_interactive.c', '-o', '.\ecg_vit_interactive.elf'
    )
    & $Gcc @Flags
    if ($LASTEXITCODE -ne 0) { throw 'RISC-V firmware compile/link failed.' }
    if (Test-Path -LiteralPath $Size) { & $Size .\ecg_vit_interactive.elf }
    Write-Host 'Built ecg_vit_interactive.elf'
}
finally {
    Pop-Location
}
