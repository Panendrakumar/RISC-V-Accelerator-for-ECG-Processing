@echo off
rem Preview the live monitor window with fake data (no board needed).
pushd "%~dp0..\..\.."
set "PROJ=%CD%"
popd
if not exist V:\02_Vivado_Zybo subst V: "%PROJ%"
V:\.venv\Scripts\python.exe V:\02_Vivado_Zybo\v2_interactive\host\live_monitor.py --simulate %*
if errorlevel 1 pause
