@echo off
echo Arg1: [%1]
echo All: [%*]

IF "%1"=="" (
    echo Empty argument path
) ELSE (
    echo Non-empty argument path
)

IF /I "%1"=="simple" (
    echo MATCHED simple
) ELSE (
    echo DID NOT MATCH simple, got: [%1]
)

pause
