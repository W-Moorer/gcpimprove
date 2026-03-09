# -*- coding: utf-8 -*-
# 运行 build_model.py 脚本
# Usage: .\run_build.ps1 -CaseJson case.json -RunDir run_dir [-AbaqusPath abaqus_path]

param(
    [Parameter(Mandatory=$true)]
    [string]$CaseJson,
    
    [Parameter(Mandatory=$true)]
    [string]$RunDir,
    
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
Write-Host "Case: $CaseJson"
Write-Host "Run Dir: $RunDir"

$scriptsPath = Join-Path $ProjectRoot "scripts\build_model.py"
$scriptsPath = $scriptsPath.Replace('\', '/')

$env:PATH = "C:\SIMULIA\Commands;" + $env:PATH

Push-Location $ProjectRoot
try {
    & $AbaqusPath cae "noGUI=$scriptsPath" -- $CaseJson $RunDir
} finally {
    Pop-Location
}
