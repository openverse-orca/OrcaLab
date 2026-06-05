@echo off
setlocal enabledelayedexpansion

set "ENV_NAME=orcalab"
set "MINICONDA_URL=https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
set "INSTALLER=%TEMP%\miniconda_installer.exe"
set "SETUP_ONLY_FLAG=%TEMP%\orcalab_setup_only"

REM -- Check setup-only mode --------------------------------
set "SETUP_ONLY=0"
if exist "%SETUP_ONLY_FLAG%" (
    set "SETUP_ONLY=1"
    del "%SETUP_ONLY_FLAG%" 2>nul
)

if "%SETUP_ONLY%"=="1" (
    echo ========================================
    echo   OrcaLab Environment Setup
    echo ========================================
    echo.
) else (
    echo ========================================
    echo   OrcaLab Launcher
    echo ========================================
    echo.
)

REM -- Locate conda ------------------------------------------
set "CONDA_ROOT="
for %%d in (
    "%USERPROFILE%\miniconda3"
    "%USERPROFILE%\anaconda3"
    "%USERPROFILE%\AppData\Local\miniconda3"
    "%PROGRAMDATA%\miniconda3"
    "C:\ProgramData\miniconda3"
) do (
    if exist "%%~d\Scripts\conda.exe" set "CONDA_ROOT=%%~d"
)

if not "%CONDA_ROOT%"=="" (
    echo [OK] Found conda: %CONDA_ROOT%
    goto :check_env
)

REM -- Install Miniconda ------------------------------------
echo [INFO] Conda not found. Installing Miniconda3...

powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%MINICONDA_URL%' -OutFile '%INSTALLER%'}" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to download Miniconda.
    exit /b 1
)

"%INSTALLER%" /InstallationType=JustMe /RegisterPython=0 /AddToPath=0 /S /D=%USERPROFILE%\miniconda3
del "%INSTALLER%" 2>nul

set "CONDA_ROOT=%USERPROFILE%\miniconda3"
if not exist "%CONDA_ROOT%\Scripts\conda.exe" (
    echo [ERROR] Miniconda installation failed.
    exit /b 1
)
echo [OK] Miniconda installed.

REM -- Ensure orcalab conda environment ---------------------
:check_env
set "CONDA_EXE=%CONDA_ROOT%\Scripts\conda.exe"
set "ENV_PREFIX=%USERPROFILE%\.conda\envs\%ENV_NAME%"

if not exist "%ENV_PREFIX%\python.exe" (
    echo [INFO] Creating conda environment: %ENV_NAME%
    "%CONDA_EXE%" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main >nul 2>&1
    "%CONDA_EXE%" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r >nul 2>&1
    "%CONDA_EXE%" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/msys2 >nul 2>&1
    "%CONDA_EXE%" create --prefix "%ENV_PREFIX%" python=3.12 -y
    if !ERRORLEVEL! NEQ 0 (
        echo [ERROR] Failed to create conda environment.
        exit /b 1
    )
    echo [OK] Environment created.
)

REM -- Ensure orca-lab is installed -------------------------
echo [INFO] Ensuring orca-lab==__ORCALAB_VERSION__ ...
"%CONDA_EXE%" run --no-capture-output --prefix "%ENV_PREFIX%" pip install orca-lab==__ORCALAB_VERSION__ -i https://pypi.tuna.tsinghua.edu.cn/simple __PIP_EXTRA_INDEX_URLS__
if !ERRORLEVEL! NEQ 0 (
    echo [ERROR] Failed to install orca-lab.
    exit /b 1
)
echo [OK] orca-lab ready.

REM -- If setup-only, exit here -----------------------------
if "%SETUP_ONLY%"=="1" exit /b 0

REM -- Launch -----------------------------------------------
echo.
echo Starting OrcaLab...
"%CONDA_EXE%" run --no-capture-output --prefix "%ENV_PREFIX%" python -m orcalab %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [INFO] OrcaLab exited with an error. Troubleshooting:
    echo        1. Open terminal: conda activate %ENV_NAME% ^&^& python -m orcalab
    echo        2. Check internet connection for first-time setup
)
