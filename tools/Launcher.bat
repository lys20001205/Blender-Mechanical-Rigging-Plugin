@echo off
setlocal

:: ========================================================
:: MECHANICAL RIGGER - TEST LAUNCHER
:: ========================================================
:: This script launches Blender and immediately runs the
:: 'test/test_rigging.py' script.
::
:: USAGE:
:: 1. Set BLENDER_EXE below.
:: 2. Create a "Shell Script" Run Configuration in Rider pointing to this file.
:: ========================================================

:: --- CONFIGURATION (EDIT THIS) ---
:: Path to your Blender Executable (blender.exe)
:: Example: C:\Program Files\Blender Foundation\Blender 4.3\blender.exe
set "BLENDER_EXE=E:\blender\blender-4.3.2-windows-x64\blender-4.3.2-windows-x64\blender.exe"

:: --- AUTOMATIC PATH SETUP ---
set "SCRIPT_DIR=%~dp0"
:: Get the repo root (parent of tools)
set "REPO_ROOT=%SCRIPT_DIR%..\"
:: Normalize path
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"

set "TEST_SCRIPT=%REPO_ROOT%test\test_rigging.py"

:: --- CHECKS ---
if not exist "%BLENDER_EXE%" (
echo [ERROR] Blender executable not found at:
echo "%BLENDER_EXE%"
echo Please edit 'tools/run_test.bat' and set the correct path.
pause
exit /b 1
)

if not exist "%TEST_SCRIPT%" (
echo [ERROR] Test script not found at:
echo "%TEST_SCRIPT%"
pause
exit /b 1
)

:: --- LAUNCH ---
echo.
echo ========================================================
echo Launching Blender...
echo Test Script: %TEST_SCRIPT%
echo ========================================================
echo.

:: --python executes the script after Blender loads
"%BLENDER_EXE%" --python "%TEST_SCRIPT%"

endlocal