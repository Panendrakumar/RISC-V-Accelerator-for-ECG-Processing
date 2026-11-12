param()
$ErrorActionPreference="Stop"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/YosysHQ/picorv32/main/picorv32.v" -OutFile "$PSScriptRoot/picorv32.v"
Write-Host "Downloaded official PicoRV32 source."
