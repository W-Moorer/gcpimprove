# -*- coding: utf-8 -*-
# 运行 run_job.py 脚本
# Usage: .\run_job.ps1 -RunDir run_dir [-JobName Job-1] [-AbaqusPath abaqus_path]

param(
    [Parameter(Mandatory=$true)]
    [string]$RunDir,
    
    [string]$JobName = "Job-1",
    
    [string]$AbaqusPath
)

$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot

if ([string]::IsNullOrEmpty($AbaqusPath)) {
    $configPath = Join-Path $ProjectRoot "abaqus_config.json"
    if (Test-Path $configPath) {
        $config = Get-Content $configPath | ConvertFrom-Json
        $AbaqusPath = $config.abaqus_path
        if (-not (Test-Path $AbaqusPath)) {
            $AbaqusPath = "abaqus"
        }
    } else {
        $AbaqusPath = "abaqus"
    }
}

Write-Host "Using Abaqus: $AbaqusPath"
Write-Host "Run Dir: $RunDir"
Write-Host "Job Name: $JobName"

$scriptsPath = Join-Path $ProjectRoot "scripts\run_job.py"
$scriptsPath = $scriptsPath.Replace('\', '/')

$env:PATH = "C:\SIMULIA\Commands;" + $env:PATH

Push-Location $ProjectRoot
try {
    & $AbaqusPath cae "noGUI=$scriptsPath" -- $RunDir $JobName
} finally {
    Pop-Location
}
