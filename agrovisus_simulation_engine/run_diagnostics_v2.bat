@echo off
echo --- Running Debug Sim Service --- > diagnostics.log
venv\Scripts\python.exe debug_sim_service.py >> diagnostics.log 2>&1
echo. >> diagnostics.log

echo --- Running Test RL Env (Direct) --- >> diagnostics.log
venv\Scripts\python.exe tests/test_rl_env.py >> diagnostics.log 2>&1
echo. >> diagnostics.log

echo --- Running Test Simulation Service (Direct) --- >> diagnostics.log
venv\Scripts\python.exe tests/test_simulation_service.py >> diagnostics.log 2>&1
echo. >> diagnostics.log

echo --- Running Test Weather Service (Direct) --- >> diagnostics.log
venv\Scripts\python.exe tests/test_weather_service.py >> diagnostics.log 2>&1
echo. >> diagnostics.log

echo --- Done --- >> diagnostics.log
