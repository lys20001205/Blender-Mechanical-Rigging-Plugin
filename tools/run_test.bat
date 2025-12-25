@echo off
setlocal

:: ========================================================
:: MECHANICAL RIGGER - TEST LAUNCHER
:: ========================================================
:: This script launches Blender.
:: If a test script is provided as an argument, it runs it.
:: Otherwise, it loads the addon from source (test/load_addon.py)
:: and opens Blender for manual testing.
::
:: USAGE:
:: tools/run_test.bat [path/to/test_script.py]
:: ========================================================

:: --- CONFIGURATION (EDIT THIS) ---
:: Path to your Blender Executable (blender.exe)
set "BLENDER_EXE=E:\blender\blender-4.3.2-windows-x64\blender-4.3.2-windows-x64\blender.exe"

:: --- AUTOMATIC PATH SETUP ---
set "SCRIPT_DIR=%~dp0"
:: Get the repo root (parent of tools)
set "REPO_ROOT=%SCRIPT_DIR%..\"
:: Normalize path
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"

:: Check if user provided an argument
set "TEST_SCRIPT=%~1"

:: If no argument, use the default loader script to load the addon from src
if "%TEST_SCRIPT%"=="" (
    set "TEST_SCRIPT=%REPO_ROOT%test\load_addon.py"
)

:: --- CHECKS ---
if not exist "%BLENDER_EXE%" (
    echo [ERROR] Blender executable not found at:
    echo "%BLENDER_EXE%"
    echo Please edit 'tools/run_test.bat' and set the correct path.
    pause
    exit /b 1
)

:: --- LAUNCH ---
echo.
echo ========================================================
echo Launching Blender...

if exist "%TEST_SCRIPT%" (
    echo Running Script: "%TEST_SCRIPT%"
    echo ========================================================
    echo.
    "%BLENDER_EXE%" --python "%TEST_SCRIPT%"
) else (
    echo [ERROR] Script not found: "%TEST_SCRIPT%"
    echo Launching Blender in interactive mode (Addon might not be loaded)...
    echo ========================================================
    echo.
    "%BLENDER_EXE%"
)

endlocal
