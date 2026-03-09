@echo off
REM -*- coding: utf-8 -*-
REM 运行 extract_odb.py 脚本
REM Usage: run_extract.bat odb_path out_dir [abaqus_path]

setlocal enabledelayedexpansion

set ODB_PATH=%~1
set OUT_DIR=%~2
set ABAQUS_PATH=%~3

if "%ODB_PATH%"=="" (
    echo Usage: run_extract.bat odb_path out_dir [abaqus_path]
    echo Example: run_extract.bat runs\sphere_plane_axisym\p0001\Job-1.odb runs\sphere_plane_axisym\p0001
    exit /b 1
)

if "%OUT_DIR%"=="" (
    echo Usage: run_extract.bat odb_path out_dir [abaqus_path]
    exit /b 1
)

if "%ABAQUS_PATH%"=="" (
    set "ABAQUS_PATH=C:\SIMULIA\Commands\abaqus.bat"
    if not exist "!ABAQUS_PATH!" (
        set ABAQUS_PATH=abaqus
    )
)

echo Using Abaqus: %ABAQUS_PATH%
echo ODB Path: %ODB_PATH%
echo Output Dir: %OUT_DIR%

set "PATH=C:\SIMULIA\Commands;%PATH%"

%ABAQUS_PATH% cae noGUI=scripts/extract_odb.py -- "%ODB_PATH%" "%OUT_DIR%"

endlocal
