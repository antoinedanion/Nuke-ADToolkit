@echo off
setlocal

:: ============================================================
:: ADToolkit — Release Builder
:: Usage: release.bat 1.0.0
:: ============================================================

set REPO_DIR=%~dp0
set ADTOOLKIT_DIR=%REPO_DIR%ADToolkit
set RELEASES_DIR=%REPO_DIR%releases

:: ------------------------------------------------------------
:: Get version
:: ------------------------------------------------------------
if "%~1"=="" (
    set /p VERSION="Version number (e.g. 1.0.0): "
) else (
    set VERSION=%~1
)

if "%VERSION%"=="" (
    echo ERROR: No version provided.
    exit /b 1
)

set RELEASE_NAME=ADToolkit_v%VERSION%
set ZIP_PATH=%RELEASES_DIR%\%RELEASE_NAME%.zip

echo.
echo Building release: %RELEASE_NAME%
echo.

:: ------------------------------------------------------------
:: Create releases folder if needed
:: ------------------------------------------------------------
if not exist "%RELEASES_DIR%" mkdir "%RELEASES_DIR%"

:: ------------------------------------------------------------
:: Check zip already exists
:: ------------------------------------------------------------
if exist "%ZIP_PATH%" (
    echo ERROR: %ZIP_PATH% already exists. Bump the version or delete the file.
    exit /b 1
)

:: ------------------------------------------------------------
:: Clean __pycache__
:: ------------------------------------------------------------
echo Cleaning __pycache__...
for /d /r "%ADTOOLKIT_DIR%" %%d in (__pycache__) do (
    if exist "%%d" (
        rd /s /q "%%d"
        echo   Removed: %%d
    )
)

:: ------------------------------------------------------------
:: Create zip (requires PowerShell 5+)
:: ------------------------------------------------------------
echo Creating %ZIP_PATH%...
powershell -NoProfile -Command ^
    "Compress-Archive -Path '%ADTOOLKIT_DIR%' -DestinationPath '%ZIP_PATH%' -CompressionLevel Optimal"

if errorlevel 1 (
    echo ERROR: Failed to create zip.
    exit /b 1
)

echo Done: %ZIP_PATH%