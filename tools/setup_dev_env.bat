@echo off
setlocal

:: ========================================================
:: MECHANICAL RIGGER - DEVELOPER SETUP
:: ========================================================
:: This script creates a symlink between your source code and Blender
:: and installs the necessary debugging tools.
::
:: INSTRUCTIONS:
:: 1. Right-click this file and choose "Edit".
:: 2. Set the paths below to match your system.
:: 3. Save and run the script.
:: ========================================================

:: --- CONFIGURATION (EDIT THESE PATHS) ---

:: 1. Path to Blender's Python Executable
:: Example: C:\Program Files\Blender Foundation\Blender 4.3\4.3\python\bin\python.exe
set BLENDER_PYTHON=""

:: 2. Path to Blender Addons Directory
:: Example: C:\Users\<YourUser>\AppData\Roaming\Blender Foundation\Blender\4.3\scripts\addons
set BLENDER_ADDONS=""

:: --- END OF CONFIGURATION ---

set ADDON_NAME=mechanical_rigger

:: Path to the source code (Assuming this script is in /tools/ and src is in /src/)
set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%..\"
set "SRC_PATH=%REPO_ROOT%src\%ADDON_NAME%"
:: Normalize path
for %%I in ("%SRC_PATH%") do set "SRC_PATH=%%~fI"

echo ========================================================
echo Mechanical Rigger Developer Setup
echo ========================================================

:: Check if paths are set
if %BLENDER_PYTHON% == "" (
    echo [ERROR] BLENDER_PYTHON path is not set.
    echo Please right-click this script, select Edit, and set your paths.
    echo.
    echo Expected: Path to python.exe inside Blender installation.
    pause
    exit /b 1
)
if %BLENDER_ADDONS% == "" (
    echo [ERROR] BLENDER_ADDONS path is not set.
    echo Please right-click this script, select Edit, and set your paths.
    echo.
    echo Expected: Path to 'scripts\addons' in your AppData folder.
    pause
    exit /b 1
)

echo.
echo 1. Checking Python Environment...

if not exist %BLENDER_PYTHON% (
    echo [ERROR] Blender Python not found at:
    echo %BLENDER_PYTHON%
    echo Please verify the path in the script.
    pause
    exit /b 1
)

echo Found Blender Python.

echo.
echo 2. Installing Dependencies (pip & pydevd-pycharm)...

:: Ensure pip is installed
%BLENDER_PYTHON% -m ensurepip --default-pip
if %errorlevel% neq 0 (
    echo [WARNING] ensurepip failed. Pip might already be installed. Continuing...
)

:: Install debugger
%BLENDER_PYTHON% -m pip install pydevd-pycharm
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install pydevd-pycharm.
    pause
    exit /b 1
)

echo Dependencies installed successfully.

echo.
echo 3. Creating Symlink (Junction)...

set "TARGET_DIR=%BLENDER_ADDONS%\%ADDON_NAME%"
set "TARGET_DIR=%TARGET_DIR:"=%"

:: Check if target already exists
if exist "%TARGET_DIR%" (
    echo [INFO] Target directory already exists: "%TARGET_DIR%"
    echo Please manually delete it if it is a regular folder/zip installation.
    echo If it is already a symlink, you are good to go.
) else (
    echo Linking:
    echo Source: "%SRC_PATH%"
    echo Dest:   "%TARGET_DIR%"

    mklink /J "%TARGET_DIR%" "%SRC_PATH%"

    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create symlink. You might need to run this script as Administrator.
        pause
        exit /b 1
    )
    echo Symlink created successfully!
)

echo.
echo ========================================================
echo Setup Complete!
echo 1. Open Rider and install "Python Community" plugin.
echo 2. Create "Python Debug Server" config (localhost:5678).
echo 3. Start Debugger in Rider.
echo 4. Start Blender.
echo ========================================================
pause
