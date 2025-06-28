@echo off
REM Batch file to run the War Manager GUI

echo Starting War Manager...

REM Change to the directory where the script is located
cd /d %~dp0

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo No virtual environment found. Running with system Python...
)

REM Run the war manager script
python manage_war.py

REM Keep the window open if there's an error
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred. Press any key to close...
    pause >nul
)
