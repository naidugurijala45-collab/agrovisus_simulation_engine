@echo off
echo Installing minimal dependencies... > setup_fast.log
venv\Scripts\python.exe -m pip install gymnasium pytest >> setup_fast.log 2>&1
echo Running diagnostics... >> setup_fast.log
call run_diagnostics_v2.bat
echo Done. >> setup_fast.log
