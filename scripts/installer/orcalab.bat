@echo off
setlocal enabledelayedexpansion

set "ENV_NAME=orcalab"
set "MINICONDA_URL=https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
set "INSTALLER=%TEMP%\miniconda_installer.exe"
set "SETUP_ONLY_FLAG=%TEMP%\orcalab_setup_only"

call :resolve_launcher_language %*
if /i "%LAUNCHER_LANGUAGE%"=="zh_CN" chcp 65001 >nul
call :load_launcher_strings
goto :launcher_start

:resolve_launcher_language
set "LAUNCHER_LANGUAGE="
:resolve_launcher_language_next
if "%~1"=="" goto :resolve_launcher_system_language
set "LAUNCHER_ARG=%~1"
if /i "!LAUNCHER_ARG!"=="--lang" (
    set "LAUNCHER_LANGUAGE="
    if not "%~2"=="" call :normalize_launcher_language "%~2"
    shift
) else if /i "!LAUNCHER_ARG:~0,7!"=="--lang=" (
    set "LAUNCHER_LANGUAGE="
    call :normalize_launcher_language "!LAUNCHER_ARG:~7!"
)
shift
goto :resolve_launcher_language_next

:resolve_launcher_system_language
if defined LAUNCHER_LANGUAGE exit /b 0
set "WINDOWS_UI_LANGUAGE="
for /f "usebackq delims=" %%L in (`powershell.exe -NoProfile -NonInteractive -Command "[Globalization.CultureInfo]::CurrentUICulture.TwoLetterISOLanguageName" 2^>nul`) do set "WINDOWS_UI_LANGUAGE=%%L"
if /i "!WINDOWS_UI_LANGUAGE!"=="zh" (
    set "LAUNCHER_LANGUAGE=zh_CN"
) else (
    set "LAUNCHER_LANGUAGE=en_US"
)
exit /b 0

:normalize_launcher_language
if /i "%~1"=="zh" set "LAUNCHER_LANGUAGE=zh_CN"
if /i "%~1"=="zh_CN" set "LAUNCHER_LANGUAGE=zh_CN"
if /i "%~1"=="en" set "LAUNCHER_LANGUAGE=en_US"
if /i "%~1"=="en_US" set "LAUNCHER_LANGUAGE=en_US"
exit /b 0

:load_launcher_strings
if /i "%LAUNCHER_LANGUAGE%"=="zh_CN" (
    set "MSG_ENV_SETUP_TITLE=OrcaLab 环境配置"
    set "MSG_LAUNCHER_TITLE=OrcaLab 启动器"
    set "MSG_CHECK_CONDA=正在检查 conda 安装"
    set "MSG_FOUND_CONDA=已找到 conda"
    set "MSG_REMOVE_BROKEN_CONDA=正在删除损坏的 conda 目录"
    set "MSG_CONDA_NOT_FOUND=未找到 conda，正在下载 Miniconda3"
    set "MSG_DOWNLOAD_FAILED=下载 Miniconda 失败，请检查网络连接"
    set "MSG_INSTALLING_MINICONDA=正在安装 Miniconda3 到"
    set "MSG_MINICONDA_FAILED=Miniconda 安装失败"
    set "MSG_MINICONDA_INSTALLED=Miniconda3 安装完成"
    set "MSG_PREPARE_PYTHON=正在准备 Python 环境"
    set "MSG_CREATE_ENV=正在创建 conda 环境"
    set "MSG_FIRST_SETUP_TIME=首次配置可能需要几分钟"
    set "MSG_CREATE_ENV_FAILED=创建 conda 环境失败"
    set "MSG_ENV_CREATED=conda 环境创建完成"
    set "MSG_ENV_EXISTS=conda 环境已存在"
    set "MSG_INSTALL_DEPENDENCIES=正在安装 OrcaLab 依赖"
    set "MSG_INSTALL_PACKAGE=正在安装"
    set "MSG_SLOW_NETWORK=网络较慢时，此步骤可能需要一些时间"
    set "MSG_PIP_ATTEMPT=pip 安装尝试"
    set "MSG_PIP_ATTEMPT_FAILED=失败（可能是网络问题），正在重试"
    set "MSG_IMPORT_FAILED=已安装但导入失败（安装不完整），正在重试"
    set "MSG_PACKAGE_INSTALL_FAILED=多次尝试后仍无法安装 orca-lab"
    set "MSG_CHECK_NETWORK=排查建议：请检查网络连接"
    set "MSG_PACKAGE_INSTALLED=已安装"
    set "MSG_SETUP_COMPLETE=环境配置完成"
    set "MSG_CAN_LAUNCH=现在可以启动 OrcaLab"
    set "MSG_LAUNCHING=正在启动 OrcaLab"
    set "MSG_STARTING=OrcaLab 正在启动，请稍候"
    set "MSG_APP_ERROR=OrcaLab 异常退出"
    set "MSG_TROUBLESHOOTING=排查建议"
    set "MSG_RUN_TERMINAL=从终端运行"
    set "MSG_ENSURE_INTERNET=确保首次配置时网络连接正常"
    set "MSG_REINSTALL=如果问题仍然存在，请重新安装 OrcaLab"
) else (
    set "MSG_ENV_SETUP_TITLE=OrcaLab Environment Setup"
    set "MSG_LAUNCHER_TITLE=OrcaLab Launcher"
    set "MSG_CHECK_CONDA=Checking conda installation"
    set "MSG_FOUND_CONDA=Found conda"
    set "MSG_REMOVE_BROKEN_CONDA=Removing broken conda directory"
    set "MSG_CONDA_NOT_FOUND=Conda not found. Downloading Miniconda3"
    set "MSG_DOWNLOAD_FAILED=Failed to download Miniconda. Check your internet connection"
    set "MSG_INSTALLING_MINICONDA=Installing Miniconda3 to"
    set "MSG_MINICONDA_FAILED=Miniconda installation failed"
    set "MSG_MINICONDA_INSTALLED=Miniconda3 installed"
    set "MSG_PREPARE_PYTHON=Preparing Python environment"
    set "MSG_CREATE_ENV=Creating conda environment"
    set "MSG_FIRST_SETUP_TIME=First-time setup may take a few minutes"
    set "MSG_CREATE_ENV_FAILED=Failed to create conda environment"
    set "MSG_ENV_CREATED=Conda environment created"
    set "MSG_ENV_EXISTS=Conda environment exists"
    set "MSG_INSTALL_DEPENDENCIES=Installing OrcaLab dependencies"
    set "MSG_INSTALL_PACKAGE=Installing"
    set "MSG_SLOW_NETWORK=This step may take a while on slow networks"
    set "MSG_PIP_ATTEMPT=pip install attempt"
    set "MSG_PIP_ATTEMPT_FAILED=failed (possible network issue). Retrying"
    set "MSG_IMPORT_FAILED=installed but import failed (incomplete install). Retrying"
    set "MSG_PACKAGE_INSTALL_FAILED=Failed to install orca-lab after multiple attempts"
    set "MSG_CHECK_NETWORK=Troubleshooting: Check your internet connection"
    set "MSG_PACKAGE_INSTALLED=installed"
    set "MSG_SETUP_COMPLETE=Environment setup complete"
    set "MSG_CAN_LAUNCH=You can now launch OrcaLab"
    set "MSG_LAUNCHING=Launching OrcaLab"
    set "MSG_STARTING=Starting OrcaLab, please wait"
    set "MSG_APP_ERROR=OrcaLab exited with an error"
    set "MSG_TROUBLESHOOTING=Troubleshooting"
    set "MSG_RUN_TERMINAL=Run from terminal"
    set "MSG_ENSURE_INTERNET=Ensure internet connection for first-time setup"
    set "MSG_REINSTALL=Reinstall OrcaLab if the issue persists"
)
exit /b 0

:launcher_start

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
    echo     !MSG_ENV_SETUP_TITLE!
    echo   ==============================================
) else (
    echo   ==============================================
    echo     !MSG_LAUNCHER_TITLE! v__ORCALAB_VERSION__
    echo   ==============================================
)
echo.

REM -- Step 1: Locate/Install conda -------------------------
echo   [1/4] !MSG_CHECK_CONDA!...
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
    echo   [OK] !MSG_FOUND_CONDA!: %CONDA_ROOT%
    goto :check_env
)

REM -- Clean up broken Miniconda directory ------------------
if exist "%DEFAULT_CONDA%" (
    echo   [INFO] !MSG_REMOVE_BROKEN_CONDA!: %DEFAULT_CONDA%
    rmdir /s /q "%DEFAULT_CONDA%" 2>nul
)

REM -- Install Miniconda ------------------------------------
echo   [INFO] !MSG_CONDA_NOT_FOUND!...
echo   [INFO] URL: %MINICONDA_URL%

powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%MINICONDA_URL%' -OutFile '%INSTALLER%'}"
if %ERRORLEVEL% NEQ 0 (
    echo   [ERROR] !MSG_DOWNLOAD_FAILED!.
    echo   [ERROR] URL: %MINICONDA_URL%
    if "%SETUP_ONLY%"=="1" exit /b 1
    pause
    exit /b 1
)

echo   [INFO] !MSG_INSTALLING_MINICONDA! %DEFAULT_CONDA% ...
"%INSTALLER%" /InstallationType=JustMe /RegisterPython=0 /AddToPath=0 /S /D=%USERPROFILE%\miniconda3
del "%INSTALLER%" 2>nul

set "CONDA_ROOT=%USERPROFILE%\miniconda3"
if not exist "%CONDA_ROOT%\Scripts\conda.exe" (
    echo   [ERROR] !MSG_MINICONDA_FAILED!.
    if "%SETUP_ONLY%"=="1" exit /b 1
    pause
    exit /b 1
)
echo   [OK] !MSG_MINICONDA_INSTALLED!.

REM -- Step 2: Ensure conda environment ---------------------
:check_env
echo.
echo   [2/4] !MSG_PREPARE_PYTHON!...
echo   ----------------------------------------

set "CONDA_EXE=%CONDA_ROOT%\Scripts\conda.exe"
set "ENV_PREFIX=%USERPROFILE%\.conda\envs\%ENV_NAME%"

if not exist "%ENV_PREFIX%\python.exe" (
    echo   [INFO] !MSG_CREATE_ENV!: %ENV_NAME% Python 3.12...
    echo   [INFO] !MSG_FIRST_SETUP_TIME!.
    "%CONDA_EXE%" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main >nul 2>&1
    "%CONDA_EXE%" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r >nul 2>&1
    "%CONDA_EXE%" tos accept --override-channels --channel https://repo.anaconda.com/pkgs/msys2 >nul 2>&1
    "%CONDA_EXE%" create --prefix "%ENV_PREFIX%" python=3.12 -y
    if !ERRORLEVEL! NEQ 0 (
        echo   [ERROR] !MSG_CREATE_ENV_FAILED!.
        if "%SETUP_ONLY%"=="1" exit /b 1
        pause
        exit /b 1
    )
    echo   [OK] !MSG_ENV_CREATED!.
) else (
    echo   [OK] !MSG_ENV_EXISTS!: %ENV_PREFIX%
)

REM -- Step 3: Install orca-lab package ---------------------
echo.
echo   [3/4] !MSG_INSTALL_DEPENDENCIES!...
echo   ----------------------------------------
echo   [INFO] !MSG_INSTALL_PACKAGE! orca-lab==__ORCALAB_VERSION__ ...
echo   [INFO] !MSG_SLOW_NETWORK!.

set "PIP_OK=0"
for /L %%i in (1,1,3) do (
    if "!PIP_OK!"=="0" (
        echo   [INFO] !MSG_PIP_ATTEMPT! %%i/3 ...
        "%CONDA_EXE%" run --no-capture-output --prefix "%ENV_PREFIX%" pip install --quiet orca-lab==__ORCALAB_VERSION__ --retries 5 --timeout 60 -i __PIP_INDEX_URL__ __PIP_EXTRA_INDEX_URLS__
        if !ERRORLEVEL! NEQ 0 (
            echo   [WARN] !MSG_PIP_ATTEMPT! %%i !MSG_PIP_ATTEMPT_FAILED!...
        ) else (
            REM -- Verify the install is actually complete by importing it --
            "%CONDA_EXE%" run --no-capture-output --prefix "%ENV_PREFIX%" python -c "import orcalab" >nul 2>&1
            if !ERRORLEVEL! EQU 0 (
                set "PIP_OK=1"
            ) else (
                echo   [WARN] orca-lab !MSG_IMPORT_FAILED!...
            )
        )
    )
)
if "!PIP_OK!"=="0" (
    echo   [ERROR] !MSG_PACKAGE_INSTALL_FAILED!.
    echo   [INFO] !MSG_CHECK_NETWORK!.
    if "%SETUP_ONLY%"=="1" exit /b 1
    pause
    exit /b 1
)
echo   [OK] orca-lab __ORCALAB_VERSION__ !MSG_PACKAGE_INSTALLED!.

REM -- If setup-only, exit here -----------------------------
if "%SETUP_ONLY%"=="1" (
    echo.
    echo   ==============================================
    echo     !MSG_SETUP_COMPLETE!.
    echo     !MSG_CAN_LAUNCH!.
    echo   ==============================================
    exit /b 0
)

REM -- Step 4: Launch ---------------------------------------
setlocal DisableDelayedExpansion
echo.
echo   [4/4] %MSG_LAUNCHING%...
echo   ----------------------------------------
echo   [INFO] %MSG_STARTING%...
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
    echo     %MSG_APP_ERROR%.
    echo   ==============================================
    echo.
    echo   %MSG_TROUBLESHOOTING%:
    echo   1. %MSG_RUN_TERMINAL%: conda activate %ENV_NAME% ^&^& python -m orcalab
    echo   2. %MSG_ENSURE_INTERNET%.
    echo   3. %MSG_REINSTALL%.
    echo.
    pause
)
