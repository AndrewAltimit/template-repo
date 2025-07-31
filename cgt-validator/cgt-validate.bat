@echo off
REM CGT Validator CLI wrapper script for Windows
REM Sets up PYTHONPATH to ensure proper imports

REM Get the directory where this script is located
set SCRIPT_DIR=%~dp0

REM Set PYTHONPATH to include src directory
set PYTHONPATH=%SCRIPT_DIR%src;%PYTHONPATH%

REM Execute the cgt-validate command with all arguments
cgt-validate %*
