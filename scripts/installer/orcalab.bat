@echo off
setlocal enabledelayedexpansion

set "ENV_NAME=orcalab"
set "ORCALAB_LANG=__ORCALAB_LANG__"
set "MINICONDA_URL=https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
set "INSTALLER=%TEMP%\miniconda_installer.exe"
set "SETUP_ONLY_FLAG=%TEMP%\orcalab_setup_only"

REM -- Check setup-only mode --------------------------------
set "SETUP_ONLY=0"
if exist "%SETUP_ONLY_FLAG%" (
    set "SETUP_ONLY=1"
    del "%SETUP_ONLY_FLAG%" 2>nul
)

cls
echo.
if "%SETUP_ONLY%"=="1" (
    echo   ==============================================
    echo     OrcaLab Environment Setup
    echo   ==============================================
) else (
    echo   ==============================================
    echo     OrcaLab Launcher v__ORCALAB_VERSION__
    echo   ==============================================
)
echo.

REM -- Step 1: Locate/Install conda -------------------------
echo   [1/4] Checking conda installation...
echo   ----------------------------------------

set "CONDA_ROOT="
set "DEFAULT_CONDA=%USERPROFILE%\miniconda3"
for %%d in (
    "%DEFAULT_CONDA%"
    "%USERPROFILE%\anaconda3"
    "%USERPROFILE%\AppData\Local\miniconda3"
    "%PROGRAMDATA%\miniconda3"
    "C:\ProgramData\miniconda3"
) do (
    if not "!CONDA_ROOT!"=="" goto :conda_found_break
    if exist "%%~d\Scripts\conda.exe" set "CONDA_ROOT=%%~d"
    if exist "%%~d\_conda.exe" if "!CONDA_ROOT!"=="" set "CONDA_ROOT=%%~d"
)
:conda_found_break

if not "%CONDA_ROOT%"=="" (
    echo   [OK] Found conda: %CONDA_ROOT%
    goto :check_env
)

REM -- Clean up broken Miniconda directory ------------------
if exist "%DEFAULT_CONDA%" (
    echo   [INFO] Removing broken conda directory: %DEFAULT_CONDA%
    rmdir /s /q "%DEFAULT_CONDA%" 2>nul
)

REM -- Install Miniconda ------------------------------------
echo   [INFO] Conda not found. Downloading Miniconda3...
echo   [INFO] URL: %MINICONDA_URL%

powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%MINICONDA_URL%' -OutFile '%INSTALLER%'}"
if %ERRORLEVEL% NEQ 0 (
    echo   [ERROR] Failed to download Miniconda. Check your internet connection.
    echo   [ERROR] URL: %MINICONDA_URL%
    if "%SETUP_ONLY%"=="1" exit /b 1
    pause
    exit /b 1
)

echo   [INFO] Installing Miniconda3 to %DEFAULT_CONDA% ...
"%INSTALLER%" /InstallationType=JustMe /RegisterPython=0 /AddToPath=0 /S /D=%USERPROFILE%\miniconda3
del "%INSTALLER%" 2>nul

set "CONDA_ROOT=%USERPROFILE%\miniconda3"
if not exist "%CONDA_ROOT%\Scripts\conda.exe" (
    echo   [ERROR] Miniconda installation failed.
    if "%SETUP_ONLY%"=="1" exit /b 1
    pause
    exit /b 1
)
echo   [OK] Miniconda3 installed.

REM -- Step 2: Ensure conda environment ---------------------
:check_env
echo.
echo   [2/4] Preparing Python environment...
echo   ----------------------------------------

set "CONDA_EXE=%CONDA_ROOT%\Scripts\conda.exe"
set "ENV_PREFIX=%USERPROFILE%\.conda\envs\%ENV_NAME%"

if not exist "%ENV_PREFIX%\python.exe" (
    echo   [INFO] Creating conda environment: %ENV_NAME% Python 3.12...
    echo   [INFO] First-time setup may take a few minutes.
    "%CONDA_EXE%" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main >nul 2>&1
    "%CONDA_EXE%" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r >nul 2>&1
    "%CONDA_EXE%" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/msys2 >nul 2>&1
    "%CONDA_EXE%" create --prefix "%ENV_PREFIX%" python=3.12 -y
    if !ERRORLEVEL! NEQ 0 (
        echo   [ERROR] Failed to create conda environment.
        if "%SETUP_ONLY%"=="1" exit /b 1
        pause
        exit /b 1
    )
    echo   [OK] Conda environment created.
) else (
    echo   [OK] Conda environment exists: %ENV_PREFIX%
)

REM -- Step 3: Install orca-lab package ---------------------
echo.
echo   [3/4] Installing OrcaLab dependencies...
echo   ----------------------------------------
echo   [INFO] Installing orca-lab==__ORCALAB_VERSION__ ...
echo   [INFO] This step may take a while on slow networks.

set "PIP_OK=0"
for /L %%i in (1,1,3) do (
    if "!PIP_OK!"=="0" (
        echo   [INFO] pip install attempt %%i/3 ...
        "%CONDA_EXE%" run --no-capture-output --prefix "%ENV_PREFIX%" pip install --quiet orca-lab==__ORCALAB_VERSION__ --retries 5 --timeout 60 -i __PIP_INDEX_URL__ __PIP_EXTRA_INDEX_URLS__
        if !ERRORLEVEL! NEQ 0 (
            echo   [WARN] pip install attempt %%i failed (possible network issue^). Retrying...
        ) else (
            REM -- Verify the install is actually complete by importing it --
            "%CONDA_EXE%" run --no-capture-output --prefix "%ENV_PREFIX%" python -c "import orcalab" >nul 2>&1
            if !ERRORLEVEL! EQU 0 (
                set "PIP_OK=1"
            ) else (
                echo   [WARN] orca-lab installed but import failed (incomplete install^). Retrying...
            )
        )
    )
)
if "!PIP_OK!"=="0" (
    echo   [ERROR] Failed to install orca-lab after multiple attempts.
    echo   [INFO] Troubleshooting: Check your internet connection.
    if "%SETUP_ONLY%"=="1" exit /b 1
    pause
    exit /b 1
)
echo   [OK] orca-lab __ORCALAB_VERSION__ installed.

REM -- If setup-only, exit here -----------------------------
if "%SETUP_ONLY%"=="1" (
    echo.
    echo   ==============================================
    echo     Environment setup complete.
    echo     You can now launch OrcaLab.
    echo   ==============================================
    exit /b 0
)

REM -- Step 4: Launch ---------------------------------------
echo.
echo   [4/4] Launching OrcaLab...
echo   ----------------------------------------
echo   [INFO] Starting OrcaLab, please wait...
echo.

REM -- Launch detached with pythonw.exe so the launcher window can close --
set "PYW_EXE=%ENV_PREFIX%\pythonw.exe"
if exist "%PYW_EXE%" (
    start "" "%PYW_EXE%" -m orcalab %*
    exit /b 0
)

REM -- Fallback: pythonw.exe missing, run in foreground with error report --
"%CONDA_EXE%" run --no-capture-output --prefix "%ENV_PREFIX%" python -m orcalab %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo   ==============================================
    echo     OrcaLab exited with an error.
    echo   ==============================================
    echo.
    echo   Troubleshooting:
    echo   1. Run from terminal: conda activate %ENV_NAME% ^&^& python -m orcalab
    echo   2. Ensure internet connection for first-time setup.
    echo   3. Reinstall OrcaLab if the issue persists.
    echo.
    pause
)
