@echo off
REM run_claude.bat - Start Claude Code with Node.js 22.16.0

setlocal enabledelayedexpansion

echo Starting Claude Code with Node.js 22.16.0

REM Check if nvm-windows is installed
where nvm >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo NVM for Windows not found. Please install it first.
    echo Visit: https://github.com/coreybutler/nvm-windows
    exit /b 1
)

REM Switch to Node.js 22.16.0
echo Switching to Node.js 22.16.0...
call nvm use 22.16.0
if %ERRORLEVEL% neq 0 (
    echo Node.js 22.16.0 not installed. Installing...
    call nvm install 22.16.0
    call nvm use 22.16.0
)

REM Verify Node version
for /f "tokens=*" %%i in ('node --version') do set NODE_VERSION=%%i
echo Using Node.js: %NODE_VERSION%

REM Note: Security validation is handled by gh-validator binary
REM via PATH shadowing. No explicit hook initialization needed.

REM Ask about unattended mode
echo.
echo Claude Code Configuration
echo.
echo Would you like to run Claude Code in unattended mode?
echo This will allow Claude to execute commands without asking for approval.
echo.
choice /c YN /n /m "Use unattended mode? (Y/N): "
if %ERRORLEVEL% equ 1 (
    echo.
    echo Starting Claude Code in UNATTENDED mode --dangerously-skip-permissions...
    echo WARNING: Claude will execute commands without asking for approval!
    echo.
    claude --dangerously-skip-permissions
) else (
    echo.
    echo Starting Claude Code in NORMAL mode with approval prompts...
    echo.
    claude
)

endlocal
