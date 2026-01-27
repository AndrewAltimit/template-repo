# PowerShell Launcher for Sleeper Detection Dashboard
# Provides comprehensive dashboard management on Windows

param(
    [Parameter(HelpMessage="Run mode: docker, local, or docker-compose")]
    [ValidateSet("docker", "local", "docker-compose")]
    [string]$Mode = "docker-compose",

    [Parameter(HelpMessage="Database initialization: mock, empty, existing, or path to db file")]
    [string]$Database = "mock",

    [Parameter(HelpMessage="Port for dashboard")]
    [int]$Port = 8501,

    [Parameter(HelpMessage="Open browser after launch")]
    [switch]$OpenBrowser,

    [Parameter(HelpMessage="Enable debug logging")]
    [switch]$Debug
)

$ErrorActionPreference = "Stop"
$script:DashboardPath = Join-Path $PSScriptRoot "..\..\..\packages\sleeper_agents\dashboard"

# Color functions
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Info { Write-Host $args -ForegroundColor Cyan }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }
function Write-Error { Write-Host $args -ForegroundColor Red }

Write-Success "=== Sleeper Detection Dashboard Launcher (Windows) ==="
Write-Host ""

# Change to dashboard directory
Push-Location $DashboardPath

try {
    # Initialize database
    Write-Info "Initializing database..."
    switch ($Database) {
        "mock" {
            Write-Info "Generating mock test data..."
            if (Test-Path "tests\fixtures.py") {
                python tests\fixtures.py
                if (Test-Path "tests\test_evaluation_results.db") {
                    Copy-Item "tests\test_evaluation_results.db" -Destination "evaluation_results.db" -Force
                    Write-Success "Mock data generated successfully!"
                } else {
                    throw "Failed to generate mock data"
                }
            } else {
                throw "fixtures.py not found in tests directory"
            }
        }

        "empty" {
            Write-Info "Creating empty database..."
            $pythonScript = @"
import sqlite3
conn = sqlite3.connect('evaluation_results.db')
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS evaluation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    test_type TEXT NOT NULL,
    accuracy REAL,
    precision REAL,
    recall REAL,
    f1_score REAL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    config TEXT,
    notes TEXT
)
''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS model_rankings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    overall_score REAL,
    vulnerability_score REAL,
    robustness_score REAL,
    eval_date DATETIME,
    rank INTEGER
)
''')
conn.commit()
conn.close()
print('Empty database created successfully!')
"@
            $pythonScript | python
        }

        "existing" {
            if (Test-Path "evaluation_results.db") {
                Write-Success "Using existing database"
            } else {
                Write-Warning "No existing database found, creating empty one..."
                & $PSCommandPath -Database "empty"
            }
        }

        default {
            # Assume it's a path to database file
            if (Test-Path $Database) {
                Copy-Item $Database -Destination "evaluation_results.db" -Force
                Write-Success "Database loaded from: $Database"
            } else {
                throw "Database file not found: $Database"
            }
        }
    }

    Write-Host ""
    Write-Info "Launching dashboard with mode: $Mode"

    # Launch dashboard based on mode
    switch ($Mode) {
        "docker-compose" {
            Write-Info "Building and launching with Docker Compose..."

            # Navigate to project root for docker-compose
            Push-Location (Join-Path $PSScriptRoot "..\..\..")

            # Build the dashboard image
            docker compose build sleeper-dashboard

            # Run the dashboard
            if ($Debug) {
                docker compose up sleeper-dashboard
            } else {
                docker compose up -d sleeper-dashboard
                Write-Success "Dashboard started in background on port $Port"
            }

            Pop-Location
        }

        "docker" {
            Write-Info "Building and launching with Docker..."

            # Build the image
            docker build -t sleeper-dashboard:local .

            # Load environment variables from .env if it exists
            $envPath = Join-Path $PSScriptRoot "..\..\..\.env"
            if (Test-Path $envPath) {
                Get-Content $envPath | ForEach-Object {
                    if ($_ -match "^([^#][^=]+)=(.+)$") {
                        [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
                    }
                }
            }

            # Prepare volume paths (convert to Docker-compatible format)
            $dbPath = (Get-Item "evaluation_results.db").FullName -replace '\\','/'
            $authPath = (Get-Item "auth" -ErrorAction SilentlyContinue).FullName -replace '\\','/'

            # Run the container
            $dockerArgs = @(
                "run", "--rm"
                "-p", "${Port}:8501"
                "-v", "${dbPath}:/home/dashboard/app/evaluation_results.db"
            )

            if ($authPath) {
                $dockerArgs += @("-v", "${authPath}:/home/dashboard/app/auth")
            }

            # Add environment variables
            $adminPassword = [Environment]::GetEnvironmentVariable("DASHBOARD_ADMIN_PASSWORD", "Process")
            if ($adminPassword) {
                $dockerArgs += @("-e", "DASHBOARD_ADMIN_PASSWORD=$adminPassword")
            }

            $dockerArgs += @(
                "-e", "DATABASE_PATH=/home/dashboard/app/evaluation_results.db"
                "sleeper-dashboard:local"
            )

            if ($Debug) {
                docker @dockerArgs
            } else {
                Start-Process -NoNewWindow docker -ArgumentList $dockerArgs
                Write-Success "Dashboard started on port $Port"
            }
        }

        "local" {
            Write-Info "Launching dashboard locally..."

            # Check Python installation
            try {
                python --version | Out-Null
            } catch {
                throw "Python is not installed or not in PATH"
            }

            # Check and install dependencies
            try {
                python -c "import streamlit" 2>$null
            } catch {
                Write-Warning "Installing dependencies..."
                pip install -r requirements.txt
            }

            # Load environment variables from .env if it exists
            $envPath = Join-Path $PSScriptRoot "..\..\..\.env"
            if (Test-Path $envPath) {
                Get-Content $envPath | ForEach-Object {
                    if ($_ -match "^([^#][^=]+)=(.+)$") {
                        [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
                    }
                }
            }

            # Set environment variables
            $env:DATABASE_PATH = (Get-Item "evaluation_results.db").FullName
            $env:DASHBOARD_ADMIN_PASSWORD = [Environment]::GetEnvironmentVariable("DASHBOARD_ADMIN_PASSWORD", "Process")

            # Launch Streamlit
            if ($Debug) {
                streamlit run app.py --server.port $Port --server.logLevel debug
            } else {
                Start-Process streamlit -ArgumentList "run", "app.py", "--server.port", $Port
                Write-Success "Dashboard started on port $Port"
            }
        }
    }

    # Open browser if requested
    if ($OpenBrowser) {
        Start-Sleep -Seconds 3  # Give dashboard time to start
        Start-Process "http://localhost:$Port"
        Write-Success "Opened dashboard in browser"
    }

    Write-Host ""
    Write-Success "Dashboard is running at: http://localhost:$Port"
    Write-Info "Press Ctrl+C to stop the dashboard"

} catch {
    Write-Error "Error: $_"
    exit 1
} finally {
    Pop-Location
}
