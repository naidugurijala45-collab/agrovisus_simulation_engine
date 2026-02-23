@echo off
echo Installing dependencies... > setup.log
venv\Scripts\python.exe -m pip install -r requirements.txt >> setup.log 2>&1
venv\Scripts\python.exe -m pip install pytest >> setup.log 2>&1
echo Dependencies installed. >> setup.log
echo Running diagnostics... >> setup.log
call run_diagnostics_v2.bat
echo Done. >> setup.log
