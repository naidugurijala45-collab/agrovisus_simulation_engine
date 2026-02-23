@echo off
echo --- Running Debug Sim Service --- > diagnostics.log
venv\Scripts\python.exe debug_sim_service.py >> diagnostics.log 2>&1
echo. >> diagnostics.log
echo --- Running Pytest RL Env --- >> diagnostics.log
venv\Scripts\python.exe -m pytest tests/test_rl_env.py >> diagnostics.log 2>&1
echo. >> diagnostics.log
echo --- Running Pytest Simulation Service --- >> diagnostics.log
venv\Scripts\python.exe -m pytest tests/test_simulation_service.py >> diagnostics.log 2>&1
echo. >> diagnostics.log
echo --- Running Pytest Weather Service --- >> diagnostics.log
venv\Scripts\python.exe -m pytest tests/test_weather_service.py >> diagnostics.log 2>&1
echo. >> diagnostics.log
echo --- Done --- >> diagnostics.log
