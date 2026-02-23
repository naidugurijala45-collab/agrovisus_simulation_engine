@echo off
venv\Scripts\python.exe tests/test_simulation_service.py > final_sim.log 2>&1
venv\Scripts\python.exe tests/test_weather_service.py > final_weather.log 2>&1
