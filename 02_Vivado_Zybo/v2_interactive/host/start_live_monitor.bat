@echo off
rem Live laptop view of the ECG accelerator. Double-click with the Zybo Z7-10 connected and switched on.
rem It programs zybo_vit_v2_interactive.bit, then mirrors every board result on screen.
rem Close Vivado Hardware Manager first (only one program can use the JTAG cable).
pushd "%~dp0..\..\.."
set "PROJ=%CD%"
popd
if not exist V:\02_Vivado_Zybo subst V: "%PROJ%"
echo The window opens now. It connects to the board after about 20-30 s while Vivado starts.
V:\.venv\Scripts\python.exe V:\02_Vivado_Zybo\v2_interactive\host\live_monitor.py --program %*
if errorlevel 1 pause
