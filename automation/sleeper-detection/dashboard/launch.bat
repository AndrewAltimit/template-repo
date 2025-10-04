@echo off
REM Dashboard Launcher Script for Windows
REM Launches the Sleeper Detection Dashboard with GPU support

SETLOCAL EnableDelayedExpansion

REM Change to dashboard directory
SET SCRIPT_DIR=%~dp0
SET DASHBOARD_DIR=%SCRIPT_DIR%..\..\..\packages\sleeper_detection\dashboard
cd /d "%DASHBOARD_DIR%"

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

IF "%DB_OPTION%"=="1" (
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
)

IF "%DB_OPTION%"=="2" (
    echo.
    echo Creating empty database...
    python -c "import sqlite3; conn = sqlite3.connect('evaluation_results.db'); cursor = conn.cursor(); cursor.execute('CREATE TABLE IF NOT EXISTS evaluation_results (id INTEGER PRIMARY KEY AUTOINCREMENT, model_name TEXT NOT NULL, test_type TEXT NOT NULL, accuracy REAL, precision REAL, recall REAL, f1_score REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, config TEXT, notes TEXT)'); conn.commit(); conn.close(); print('Empty database created successfully!')"
)

IF "%DB_OPTION%"=="3" (
    echo.
    set /p DB_FILE="Enter path to database file: "
    IF EXIST "!DB_FILE!" (
        copy /Y "!DB_FILE!" evaluation_results.db >nul
        echo Database loaded from: !DB_FILE!
    ) ELSE (
        echo Database file not found: !DB_FILE!
        exit /b 1
    )
)

IF "%DB_OPTION%"=="4" (
    IF EXIST evaluation_results.db (
        echo.
        echo Using existing database
    ) ELSE (
        echo.
        echo No existing database found, creating empty one...
        python -c "import sqlite3; conn = sqlite3.connect('evaluation_results.db'); cursor = conn.cursor(); cursor.execute('CREATE TABLE IF NOT EXISTS evaluation_results (id INTEGER PRIMARY KEY AUTOINCREMENT, model_name TEXT NOT NULL, test_type TEXT NOT NULL, accuracy REAL, precision REAL, recall REAL, f1_score REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, config TEXT, notes TEXT)'); conn.commit(); conn.close()"
    )
)

IF "%DB_OPTION%"=="5" (
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
)

IF "%DB_OPTION%"=="6" (
    echo.
    echo Loading from imported experiments...

    SET "EXPERIMENTS_DIR=..\models\backdoored"
    IF NOT EXIST "!EXPERIMENTS_DIR!" (
        echo Experiments directory not found: !EXPERIMENTS_DIR!
        echo Import experiments first with: python ..\scripts\import_experiment.py
        exit /b 1
    )

    REM Count experiments
    SET COUNT=0
    FOR /D %%D IN ("!EXPERIMENTS_DIR!\*") DO SET /A COUNT+=1
    echo Found !COUNT! experiments in !EXPERIMENTS_DIR!

    REM Use safer, quoted comparison
    IF "!COUNT!"=="0" (
        echo No experiments found
        echo Import experiments first with: python ..\scripts\import_experiment.py
        exit /b 1
    )

    REM Ask if overwrite existing
    SET OVERWRITE_FLAG=
    IF EXIST evaluation_results.db (
        set /p OVERWRITE="Database exists. Overwrite existing entries? (y/N): "
        IF /I "!OVERWRITE!"=="y" SET OVERWRITE_FLAG=--overwrite
    )

    REM Load experiments into database
    echo Loading experiments into database...
    python ..\scripts\load_experiments_to_dashboard.py --experiments-dir "!EXPERIMENTS_DIR!" --db-path evaluation_results.db !OVERWRITE_FLAG!
    IF ERRORLEVEL 1 (
        echo Failed to load experiments
        exit /b 1
    )
    echo Experiments loaded successfully!
)

echo.

REM Launch method selection
echo How would you like to run the dashboard?
echo 1) Docker with GPU support (recommended for Windows GPU machine)
echo 2) Local Python (requires dependencies installed)
echo.
set /p LAUNCH_METHOD="Select launch method [1-2]: "

IF "%LAUNCH_METHOD%"=="1" (
    echo.
    echo ========================================
    echo Launching dashboard with Docker + GPU
    echo ========================================
    echo.

    REM Build the Docker image
    echo Building dashboard image...
    docker build -t sleeper-dashboard:latest .
    IF ERRORLEVEL 1 (
        echo Failed to build Docker image
        exit /b 1
    )

    REM Stop any existing container
    docker stop sleeper-dashboard 2>nul
    docker rm sleeper-dashboard 2>nul

    REM Load environment variables from .env if it exists
    SET ENV_FILE=%SCRIPT_DIR%..\..\..\..env
    IF EXIST "%ENV_FILE%" (
        FOR /F "usebackq tokens=1,* delims==" %%A IN ("%ENV_FILE%") DO (
            IF NOT "%%A"=="" IF NOT "%%B"=="" (
                REM Skip comments and empty lines
                SET LINE=%%A
                IF NOT "!LINE:~0,1!"=="#" (
                    SET %%A=%%B
                )
            )
        )
        echo Loaded environment from .env
    ) ELSE (
        echo Warning: .env file not found at %ENV_FILE%
    )

    REM Get absolute path to database
    SET ABS_DASHBOARD_DIR=%CD%

    REM Run the dashboard container with GPU support
    echo Starting dashboard container with NVIDIA GPU...
    echo Access at: http://localhost:8501
    echo.

    docker run -d ^
        --name sleeper-dashboard ^
        --gpus all ^
        -p 8501:8501 ^
        -v "%ABS_DASHBOARD_DIR%\evaluation_results.db:/home/dashboard/app/evaluation_results.db:ro" ^
        -v "%ABS_DASHBOARD_DIR%\components:/home/dashboard/app/components:ro" ^
        -v "%ABS_DASHBOARD_DIR%\utils:/home/dashboard/app/utils:ro" ^
        -v "%ABS_DASHBOARD_DIR%\config:/home/dashboard/app/config:ro" ^
        -e DATABASE_PATH=/home/dashboard/app/evaluation_results.db ^
        -e DASHBOARD_ADMIN_PASSWORD=%DASHBOARD_ADMIN_PASSWORD% ^
        -e PYTHONUNBUFFERED=1 ^
        sleeper-dashboard:latest

    IF ERRORLEVEL 1 (
        echo.
        echo Failed to start dashboard container
        echo.
        echo Troubleshooting:
        echo   - Ensure Docker Desktop is running
        echo   - Ensure nvidia-docker2 is installed
        echo   - Check: docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu22.04 nvidia-smi
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

) ELSE IF "%LAUNCH_METHOD%"=="2" (
    echo.
    echo ========================================
    echo Launching dashboard locally
    echo ========================================
    echo.

    REM Check if dependencies are installed
    python -c "import streamlit" 2>nul
    IF ERRORLEVEL 1 (
        echo Installing dependencies...
        pip install -r requirements.txt
        IF ERRORLEVEL 1 (
            echo Failed to install dependencies
            exit /b 1
        )
    )

    REM Load environment variables from .env if it exists
    SET ENV_FILE=%SCRIPT_DIR%..\..\..\..env
    IF EXIST "%ENV_FILE%" (
        FOR /F "usebackq tokens=1,* delims==" %%A IN ("%ENV_FILE%") DO (
            IF NOT "%%A"=="" IF NOT "%%B"=="" (
                REM Skip comments and empty lines
                SET LINE=%%A
                IF NOT "!LINE:~0,1!"=="#" (
                    SET %%A=%%B
                )
            )
        )
        echo Loaded environment from .env
    ) ELSE (
        echo Warning: .env file not found at %ENV_FILE%
    )

    REM Set environment variables
    SET DATABASE_PATH=%CD%\evaluation_results.db

    echo.
    echo Launching Streamlit dashboard...
    echo Access at: http://localhost:8501
    echo.

    streamlit run app.py --server.port 8501

) ELSE (
    echo.
    echo Invalid launch method
    exit /b 1
)

ENDLOCAL
