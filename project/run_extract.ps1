# -*- coding: utf-8 -*-
# 运行 extract_odb.py 脚本
# Usage: .\run_extract.ps1 -OdbPath odb_path -OutDir out_dir [-AbaqusPath abaqus_path]

param(
    [Parameter(Mandatory=$true)]
    [string]$OdbPath,
    
    [Parameter(Mandatory=$true)]
    [string]$OutDir,
    
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
Write-Host "ODB Path: $OdbPath"
Write-Host "Output Dir: $OutDir"

$scriptsPath = Join-Path $ProjectRoot "scripts\extract_odb.py"
$scriptsPath = $scriptsPath.Replace('\', '/')

$env:PATH = "C:\SIMULIA\Commands;" + $env:PATH

Push-Location $ProjectRoot
try {
    & $AbaqusPath cae "noGUI=$scriptsPath" -- $OdbPath $OutDir
} finally {
    Pop-Location
}
