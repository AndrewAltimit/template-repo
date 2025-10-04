@echo off
REM Import all deception detection probe results to dashboard

echo ========================================
echo Importing Deception Detection Results
echo ========================================
echo.

REM Change to dashboard directory
SET SCRIPT_DIR=%~dp0
SET DASHBOARD_DIR=%SCRIPT_DIR%..\dashboard
cd /d "%DASHBOARD_DIR%"

REM Import Qwen 2.5 7B Instruct (best result)
echo Importing Qwen 2.5 7B Instruct...
python ..\scripts\import_probe_results.py ^
    --db-path evaluation_results.db ^
    --model "Qwen 2.5 7B Instruct" ^
    --layer 27 ^
    --auroc 0.932 ^
    --accuracy 0.872 ^
    --precision 0.903 ^
    --recall 0.833 ^
    --f1 0.867

REM Import Qwen 2.5 3B Instruct (layer 32)
echo Importing Qwen 2.5 3B Instruct (Layer 32)...
python ..\scripts\import_probe_results.py ^
    --db-path evaluation_results.db ^
    --model "Qwen 2.5 3B Instruct (Layer 32)" ^
    --layer 32 ^
    --auroc 0.876 ^
    --accuracy 0.82 ^
    --precision 0.85 ^
    --recall 0.78 ^
    --f1 0.81

REM Import Qwen 2.5 3B Instruct (layer 18)
echo Importing Qwen 2.5 3B Instruct (Layer 18)...
python ..\scripts\import_probe_results.py ^
    --db-path evaluation_results.db ^
    --model "Qwen 2.5 3B Instruct (Layer 18)" ^
    --layer 18 ^
    --auroc 0.848 ^
    --accuracy 0.79 ^
    --precision 0.82 ^
    --recall 0.75 ^
    --f1 0.78

REM Import Yi 1.5 9B Chat
echo Importing Yi 1.5 9B Chat...
python ..\scripts\import_probe_results.py ^
    --db-path evaluation_results.db ^
    --model "Yi 1.5 9B Chat" ^
    --layer 40 ^
    --auroc 0.908 ^
    --accuracy 0.85 ^
    --precision 0.88 ^
    --recall 0.81 ^
    --f1 0.84

echo.
echo ========================================
echo Import Complete!
echo ========================================
echo.
echo Dashboard now displays all deception detection results
echo Access at: http://localhost:8501
echo.

pause
