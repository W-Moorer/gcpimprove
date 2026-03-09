#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本 - 仅运行一次构建模型
"""

import subprocess
import sys
import os

def run_build():
    """
    运行构建模型脚本
    """
    abaqus_path = r"C:\SIMULIA\Commands\abaqus.bat"
    
    env = os.environ.copy()
    env["ABAQUS_CASE_JSON"] = r"cases\sphere_plane_axisym\case.json"
    env["ABAQUS_RUN_DIR"] = r"runs\sphere_plane_axisym\p0000"
    
    cmd = [abaqus_path, "cae", "noGUI=scripts/build_model.py"]
    
    subprocess.check_call(cmd, cwd=r"E:\workspace\geometric-contact-potential-main\project")
    print("Build model completed!")

if __name__ == "__main__":
    run_build()
