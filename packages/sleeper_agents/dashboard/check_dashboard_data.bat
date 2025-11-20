@echo off
REM Comprehensive Dashboard Data Verification Script
REM Tests all database tables and verifies data for new components
REM Run this before testing the dashboard UI

echo =========================================
echo Dashboard Data Verification
echo =========================================
echo.

REM Check if dashboard container is running
docker ps | findstr sleeper-dashboard >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Dashboard container not running
    echo Starting dashboard...
    call start.bat --no-logs
    timeout /t 5 >nul
)

echo [1/8] Checking database file exists...
docker exec sleeper-dashboard ls -la /results/evaluation_results.db 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Database file not found at /results/evaluation_results.db
    echo Please run an evaluation job first.
    pause
    exit /b 1
)
echo Database file exists.
echo.

echo [2/8] Checking table row counts...
echo.
echo === Honeypot Tests (Component: Red Team Results, Persona Profile) ===
docker exec sleeper-dashboard sqlite3 /results/evaluation_results.db "SELECT COUNT(*) as count FROM honeypot_responses;"
echo.

echo === Chain-of-Thought Analysis (Component: Detection Consensus, Persona Profile) ===
docker exec sleeper-dashboard sqlite3 /results/evaluation_results.db "SELECT COUNT(*) as count FROM chain_of_thought_analysis;"
echo.

echo === Persistence Results (Component: Detection Consensus, Risk Mitigation) ===
docker exec sleeper-dashboard sqlite3 /results/evaluation_results.db "SELECT COUNT(*) as count FROM persistence_results;"
echo.

echo === Internal State Analysis (Component: Detection Consensus, Persona Profile) ===
docker exec sleeper-dashboard sqlite3 /results/evaluation_results.db "SELECT COUNT(*) as count FROM internal_state_analysis;"
echo.

echo === Trigger Sensitivity ===
docker exec sleeper-dashboard sqlite3 /results/evaluation_results.db "SELECT COUNT(*) as count FROM trigger_sensitivity;"
echo.

echo [3/8] Checking for your model in database...
echo.
echo === Models in Database ===
docker exec sleeper-dashboard sqlite3 /results/evaluation_results.db "SELECT DISTINCT model_name FROM honeypot_responses UNION SELECT DISTINCT model_name FROM chain_of_thought_analysis UNION SELECT DISTINCT model_name FROM persistence_results ORDER BY model_name;"
echo.

echo [4/8] Verifying Detection Consensus data sources...
echo.
echo === Honeypot Response Statistics ===
docker exec sleeper-dashboard sqlite3 /results/evaluation_results.db "SELECT model_name, COUNT(*) as total_tests, AVG(reveal_score) as avg_reveal_score, MAX(reveal_score) as max_reveal_score FROM honeypot_responses GROUP BY model_name;"
echo.

echo === CoT Deception Patterns ===
docker exec sleeper-dashboard sqlite3 /results/evaluation_results.db "SELECT model_name, COUNT(*) as total_samples, SUM(CASE WHEN has_deceptive_patterns = 1 THEN 1 ELSE 0 END) as deceptive_count FROM chain_of_thought_analysis GROUP BY model_name;"
echo.

echo [5/8] Verifying Persona Profile data sources...
echo.
echo === Honeypot Types for Behavioral Analysis ===
docker exec sleeper-dashboard sqlite3 /results/evaluation_results.db "SELECT honeypot_type, COUNT(*) as count, AVG(reveal_score) as avg_score FROM honeypot_responses GROUP BY honeypot_type ORDER BY avg_score DESC;"
echo.

echo [6/8] Verifying Red Team Results data...
echo.
echo === Attack Success Analysis ===
docker exec sleeper-dashboard sqlite3 /results/evaluation_results.db "SELECT model_name, honeypot_type, COUNT(*) as attempts, AVG(reveal_score) as avg_score, SUM(CASE WHEN reveal_score > 0.5 THEN 1 ELSE 0 END) as successful FROM honeypot_responses GROUP BY model_name, honeypot_type;"
echo.

echo [7/8] Verifying Risk Mitigation Matrix data sources...
echo.
echo === Persistence Rates ===
docker exec sleeper-dashboard sqlite3 /results/evaluation_results.db "SELECT model_name, persistence_rate, post_training_rate, safety_method FROM persistence_results ORDER BY timestamp DESC LIMIT 5;"
echo.

echo [8/8] Checking for potential issues...
echo.

REM Check for models with no data
echo === Models with Missing Data ===
docker exec sleeper-dashboard sqlite3 /results/evaluation_results.db "SELECT model_name FROM (SELECT DISTINCT model_name FROM honeypot_responses UNION SELECT DISTINCT model_name FROM chain_of_thought_analysis) WHERE model_name NOT IN (SELECT model_name FROM persistence_results);"
echo.

REM Check for very low test coverage
echo === Models with Low Test Coverage (might show high 'Untested Behaviors' risk) ===
docker exec sleeper-dashboard sqlite3 /results/evaluation_results.db "SELECT model_name, (SELECT COUNT(*) FROM honeypot_responses WHERE honeypot_responses.model_name = all_models.model_name) + (SELECT COUNT(*) FROM chain_of_thought_analysis WHERE chain_of_thought_analysis.model_name = all_models.model_name) as total_tests FROM (SELECT DISTINCT model_name FROM honeypot_responses UNION SELECT DISTINCT model_name FROM chain_of_thought_analysis) as all_models WHERE total_tests < 50;"
echo.

echo =========================================
echo Verification Complete
echo =========================================
echo.
echo Next Steps:
echo 1. Verify your model appears in the lists above
echo 2. Check that row counts match expectations
echo 3. Start dashboard: start.bat
echo 4. Open browser: http://localhost:8501
echo 5. Test the 4 new components:
echo    - Detection Consensus
echo    - Behavioral Persona Profile
echo    - Automated Red-Teaming Results
echo    - Risk Mitigation Matrix
echo.
echo See TESTING_CHECKLIST.md for detailed testing instructions.
echo.

pause
