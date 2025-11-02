@echo off
REM Dashboard Launcher Script for Windows
REM Launches the Sleeper Detection Dashboard with GPU support

REM Change to dashboard directory
SET SCRIPT_DIR=%~dp0
SET DASHBOARD_DIR=%SCRIPT_DIR%..\..\..\packages\sleeper_agents\dashboard
cd /d "%DASHBOARD_DIR%"

REM Load environment variables from .env file (if exists)
IF EXIST "..\..\..\.env" (
    echo Loading environment variables from .env...
    FOR /F "tokens=1,2 delims==" %%A IN ('python -c "import os; [print(f'{k}={v}') for k,v in [line.strip().split('=', 1) for line in open('../../../.env') if '=' in line and not line.strip().startswith('#')]]" 2^>nul') DO (
        SET "%%A=%%B"
    )
    echo Environment variables loaded
    echo.
)

echo ========================================
echo Sleeper Detection Dashboard Launcher
echo ========================================
echo.

REM Database initialization menu
echo How would you like to initialize the database?
echo 1) Seed with mock test data (recommended for demo)
echo 2) Initialize empty database
echo 3) Load from specific file
echo 4) Use existing database (if available)
echo 5) Reset authentication (recreate admin user)
echo 6) Load from imported experiments (models/backdoored/)
echo.
set /p DB_OPTION="Select option [1-6]: "

IF "%DB_OPTION%"=="1" GOTO option1_mock
IF "%DB_OPTION%"=="2" GOTO option2_empty
IF "%DB_OPTION%"=="3" GOTO option3_load
IF "%DB_OPTION%"=="4" GOTO option4_existing
IF "%DB_OPTION%"=="5" GOTO option5_reset
IF "%DB_OPTION%"=="6" GOTO option6_experiments
echo Invalid option. Exiting.
exit /b 1

:option1_mock
echo.
echo Generating mock test data...
IF EXIST initialize_mock_db.py (
    python initialize_mock_db.py
    IF EXIST evaluation_results_mock.db (
        copy /Y evaluation_results_mock.db evaluation_results.db >nul
        echo Mock data generated successfully!
        echo Using centralized mock data with 6 models including test-sleeper-v1
    ) ELSE (
        echo Failed to generate mock database
        exit /b 1
    )
) ELSE IF EXIST tests\fixtures.py (
    python tests\fixtures.py
    IF EXIST tests\test_evaluation_results.db (
        copy /Y tests\test_evaluation_results.db evaluation_results.db >nul
        echo Mock data generated successfully (legacy method)!
    ) ELSE (
        echo Failed to generate mock data
        exit /b 1
    )
) ELSE (
    echo Mock data generator not found!
    exit /b 1
)
GOTO launch_menu

:option2_empty
echo.
echo Creating empty database...
python -c "import sqlite3; conn = sqlite3.connect('evaluation_results.db'); cursor = conn.cursor(); cursor.execute('CREATE TABLE IF NOT EXISTS evaluation_results (id INTEGER PRIMARY KEY AUTOINCREMENT, model_name TEXT NOT NULL, test_type TEXT NOT NULL, accuracy REAL, precision REAL, recall REAL, f1_score REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, config TEXT, notes TEXT)'); conn.commit(); conn.close(); print('Empty database created successfully!')"
GOTO launch_menu

:option3_load
echo.
set /p DB_FILE="Enter path to database file: "
IF EXIST "%DB_FILE%" (
    copy /Y "%DB_FILE%" evaluation_results.db >nul
    echo Database loaded from: %DB_FILE%
) ELSE (
    echo Database file not found: %DB_FILE%
    exit /b 1
)
GOTO launch_menu

:option4_existing
IF EXIST evaluation_results.db (
    echo.
    echo Using existing database
) ELSE (
    echo.
    echo No existing database found. Creating empty database...
    python -c "import sqlite3; conn = sqlite3.connect('evaluation_results.db'); cursor = conn.cursor(); cursor.execute('CREATE TABLE IF NOT EXISTS evaluation_results (id INTEGER PRIMARY KEY AUTOINCREMENT, model_name TEXT NOT NULL, test_type TEXT NOT NULL, accuracy REAL, precision REAL, recall REAL, f1_score REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, config TEXT, notes TEXT)'); conn.commit(); conn.close()"
)
GOTO launch_menu

:option5_reset
echo.
echo Resetting authentication...
IF EXIST auth\users.db (
    del auth\users.db
    echo Removed existing auth database
)
IF EXIST evaluation_results.db (
    echo Using existing evaluation database
) ELSE (
    python -c "import sqlite3; conn = sqlite3.connect('evaluation_results.db'); cursor = conn.cursor(); cursor.execute('CREATE TABLE IF NOT EXISTS evaluation_results (id INTEGER PRIMARY KEY AUTOINCREMENT, model_name TEXT NOT NULL, test_type TEXT NOT NULL, accuracy REAL, precision REAL, recall REAL, f1_score REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, config TEXT, notes TEXT)'); conn.commit(); conn.close()"
)
GOTO launch_menu

:option6_experiments
echo.
echo Loading from imported experiments...

SET EXPERIMENTS_DIR=..\models\backdoored
IF NOT EXIST "%EXPERIMENTS_DIR%" (
    echo Experiments directory not found: %EXPERIMENTS_DIR%
    echo Import experiments first with: python ..\scripts\import_experiment.py
    exit /b 1
)

REM Count experiments
SET COUNT=0
FOR /D %%D IN ("%EXPERIMENTS_DIR%\*") DO SET /A COUNT+=1
echo Found %COUNT% experiments in %EXPERIMENTS_DIR%

IF "%COUNT%"=="0" (
    echo No experiments found
    echo Import experiments first with: python ..\scripts\import_experiment.py
    exit /b 1
)

REM Ask if overwrite existing
SET OVERWRITE_FLAG=
IF EXIST evaluation_results.db (
    set /p OVERWRITE="Database exists. Overwrite existing entries? (y/N): "
    IF /I "%OVERWRITE%"=="y" SET OVERWRITE_FLAG=--overwrite
)

REM Load experiments into database
echo Loading experiments into database...
python ..\scripts\load_experiments_to_dashboard.py --experiments-dir "%EXPERIMENTS_DIR%" --db-path evaluation_results.db %OVERWRITE_FLAG%
IF ERRORLEVEL 1 (
    echo Failed to load experiments
    exit /b 1
)
echo Experiments loaded successfully!
GOTO launch_menu

:launch_menu
echo.

REM Launch method selection
echo How would you like to run the dashboard?
echo 1) Docker with GPU support (recommended for Windows GPU machine)
echo 2) Local Python (requires dependencies installed)
echo.
set /p LAUNCH_METHOD="Select launch method [1-2]: "

IF "%LAUNCH_METHOD%"=="1" GOTO launch_docker
IF "%LAUNCH_METHOD%"=="2" GOTO launch_local
echo Invalid option. Exiting.
exit /b 1

:launch_docker
echo.
echo ========================================
echo Launching with Docker + GPU
echo ========================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
IF ERRORLEVEL 1 (
    echo Docker is not running. Please start Docker Desktop.
    exit /b 1
)

REM Check for nvidia-docker
docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi >nul 2>&1
IF ERRORLEVEL 1 (
    echo WARNING: GPU access not available. Dashboard will run in CPU mode.
    echo.
    echo To enable GPU support:
    echo 1. Install NVIDIA drivers
    echo 2. Install NVIDIA Container Toolkit
    echo 3. Restart Docker Desktop
    echo.
    pause
)

REM Stop existing container if running
docker stop sleeper-dashboard >nul 2>&1
docker rm sleeper-dashboard >nul 2>&1

REM Build and run container with GPU support
docker build -t sleeper-dashboard:latest .

REM Pass environment variables to container (if set)
SET DOCKER_ENV_FLAGS=
IF DEFINED DASHBOARD_ADMIN_PASSWORD (
    SET DOCKER_ENV_FLAGS=-e DASHBOARD_ADMIN_PASSWORD=%DASHBOARD_ADMIN_PASSWORD%
)

docker run -d --name sleeper-dashboard --gpus all -p 8501:8501 %DOCKER_ENV_FLAGS% -v "%CD%\evaluation_results.db:/app/evaluation_results.db" -v "%CD%\auth:/app/auth" sleeper-dashboard:latest

IF ERRORLEVEL 1 (
    echo.
    echo Failed to start Docker container
    echo.
    exit /b 1
)

echo.
echo ========================================
echo Dashboard started successfully!
echo ========================================
echo.
echo Access at: http://localhost:8501
echo View logs: docker logs -f sleeper-dashboard
echo Stop: docker stop sleeper-dashboard
echo.
echo The dashboard has GPU access for live model inference!
echo.
GOTO end

:launch_local
echo.
echo ========================================
echo Launching dashboard locally
echo ========================================
echo.

REM Check if Streamlit is installed
python -c "import streamlit" >nul 2>&1
IF ERRORLEVEL 1 (
    echo Streamlit not installed. Installing dependencies...
    pip install -r requirements.txt
)

echo Starting dashboard...
echo.
echo Access at: http://localhost:8501
echo Login: admin / admin123
echo.
echo Press Ctrl+C to stop
echo.

python -m streamlit run app.py --server.port 8501 --server.address localhost
GOTO end

:end
