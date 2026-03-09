# -*- coding: utf-8 -*-
"""
Usage:
  abaqus cae noGUI=run_job.py -- run_dir job_name
  或通过环境变量:
  set ABAQUS_RUN_DIR=run_dir
  set ABAQUS_JOB_NAME=Job-1
  abaqus cae noGUI=run_job.py
"""

import os
import sys
import subprocess
from abaqus import openMdb, mdb


def load_args():
    """
    加载命令行参数，支持两种方式：
    1. 命令行参数: -- run_dir job_name
    2. 环境变量: ABAQUS_RUN_DIR 和 ABAQUS_JOB_NAME
    """
    run_dir = None
    job_name = None
    
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        if idx + 1 < len(sys.argv):
            run_dir = sys.argv[idx + 1]
        if idx + 2 < len(sys.argv):
            job_name = sys.argv[idx + 2]
    
    if run_dir is None:
        run_dir = os.environ.get("ABAQUS_RUN_DIR")
    if job_name is None:
        job_name = os.environ.get("ABAQUS_JOB_NAME", "Job-1")
    
    if run_dir is None:
        raise RuntimeError("Expected arguments: run_dir job_name (via -- or environment variables)")
    
    return run_dir, job_name


def main():
    """
    主函数：打开CAE文件，创建INP文件，使用命令行运行作业
    """
    run_dir, job_name = load_args()
    cae_path = os.path.abspath(os.path.join(run_dir, "model.cae"))
    if not os.path.isfile(cae_path):
        raise IOError("Missing CAE file: {}".format(cae_path))

    os.chdir(run_dir)
    openMdb(pathName=cae_path)
    
    if job_name not in mdb.jobs.keys():
        raise RuntimeError("Job '{}' not found in model. Available jobs: {}".format(
            job_name, list(mdb.jobs.keys())))
    
    job = mdb.jobs[job_name]
    
    inp_path = os.path.join(run_dir, job_name + ".inp")
    job.writeInput(consistencyChecking=OFF)
    
    mdb.save()
    print("Created INP file:", inp_path)
    print("Job '{}' is ready for submission.".format(job_name))
    print("Run 'abaqus job={} interactive' to execute the analysis.".format(job_name))


if __name__ == "__main__":
    main()
