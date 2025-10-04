@echo off
echo Testing argument handling
echo.
echo Before shift:
echo %%1 = %1
echo %%2 = %2
echo %%3 = %3
echo %%4 = %4
echo.

IF /I "%1"=="simple" (
    echo Matched "simple"
    echo.
    echo After shift:
    shift
    echo %%1 = %1
    echo %%2 = %2
    echo %%3 = %3
    echo %%4 = %4
    echo.
    echo Full command would be:
    echo docker-compose ... %1 %2 %3 %4 %5 %6 %7 %8 %9
)
