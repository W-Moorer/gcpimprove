@echo off
REM -*- coding: utf-8 -*-
REM 运行 run_job.py 脚本
REM Usage: run_job.bat run_dir job_name [abaqus_path]

setlocal enabledelayedexpansion

set RUN_DIR=%~1
set JOB_NAME=%~2
set ABAQUS_PATH=%~3

if "%RUN_DIR%"=="" (
    echo Usage: run_job.bat run_dir job_name [abaqus_path]
    echo Example: run_job.bat runs\sphere_plane_axisym\p0001 Job-1
    exit /b 1
)

if "%JOB_NAME%"=="" (
    set JOB_NAME=Job-1
)

if "%ABAQUS_PATH%"=="" (
    set "ABAQUS_PATH=C:\SIMULIA\Commands\abaqus.bat"
    if not exist "!ABAQUS_PATH!" (
        set ABAQUS_PATH=abaqus
    )
)

echo Using Abaqus: %ABAQUS_PATH%
echo Run Dir: %RUN_DIR%
echo Job Name: %JOB_NAME%

set "PATH=C:\SIMULIA\Commands;%PATH%"

%ABAQUS_PATH% cae noGUI=scripts/run_job.py -- "%RUN_DIR%" "%JOB_NAME%"

endlocal
