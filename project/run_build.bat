@echo off
REM -*- coding: utf-8 -*-
REM 运行 build_model.py 脚本
REM Usage: run_build.bat case.json run_dir [abaqus_path]

setlocal enabledelayedexpansion

set CASE_JSON=%~1
set RUN_DIR=%~2
set ABAQUS_PATH=%~3

if "%CASE_JSON%"=="" (
    echo Usage: run_build.bat case.json run_dir [abaqus_path]
    echo Example: run_build.bat cases\sphere_plane_axisym\case.json runs\sphere_plane_axisym\p0001
    exit /b 1
)

if "%RUN_DIR%"=="" (
    echo Usage: run_build.bat case.json run_dir [abaqus_path]
    exit /b 1
)

if "%ABAQUS_PATH%"=="" (
    set "ABAQUS_PATH=C:\SIMULIA\Commands\abaqus.bat"
    if not exist "!ABAQUS_PATH!" (
        set ABAQUS_PATH=abaqus
    )
)

echo Using Abaqus: %ABAQUS_PATH%
echo Case: %CASE_JSON%
echo Run Dir: %RUN_DIR%

set "PATH=C:\SIMULIA\Commands;%PATH%"

%ABAQUS_PATH% cae noGUI=scripts/build_model.py -- "%CASE_JSON%" "%RUN_DIR%"

endlocal
