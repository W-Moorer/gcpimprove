#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
参数扫描脚本
Usage:
  python sweep.py base_case.json sweep_config.json [abaqus_config.json]
"""

import copy
import csv
import itertools
import json
import os
import subprocess
import sys
from pathlib import Path


def load_json(path):
    """
    加载JSON文件
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    """
    保存JSON文件
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def get_abaqus_cmd(config_path=None):
    """
    获取 Abaqus 命令路径
    """
    if config_path and os.path.isfile(config_path):
        cfg = load_json(config_path)
        abaqus_path = cfg.get("abaqus_path", "abaqus")
        if os.path.isfile(abaqus_path):
            return abaqus_path
    return "abaqus"


def param_product(grid):
    """
    生成参数组合的笛卡尔积
    """
    keys = list(grid.keys())
    vals = [grid[k] for k in keys]
    for combo in itertools.product(*vals):
        yield dict(zip(keys, combo))


def update_case(base_cfg, params, param_id):
    """
    根据参数更新配置
    """
    cfg = copy.deepcopy(base_cfg)
    cfg["param_id"] = param_id

    if "global_size" in params:
        cfg["mesh"]["global_size"] = params["global_size"]
    if "refine_size" in params:
        cfg["mesh"]["refine_size"] = params["refine_size"]
    if "refine_radius" in params:
        cfg["mesh"]["refine_radius"] = params["refine_radius"]
    if "family" in params:
        cfg["mesh"]["family"] = params["family"]
    if "max_inc" in params:
        cfg["loading"]["max_inc"] = params["max_inc"]
    if "contact_mode" in params:
        cfg["contact"]["mode"] = params["contact_mode"]

    return cfg


def run_abaqus_script(abaqus_cmd, script_path, env_vars, cwd=None):
    """
    执行 Abaqus 脚本，使用环境变量传递参数
    """
    cmd = [abaqus_cmd, "cae", f"noGUI={script_path}"]
    print("RUN:", " ".join(cmd))
    
    env = os.environ.copy()
    env.update(env_vars)
    
    subprocess.check_call(cmd, cwd=cwd, env=env)


def run_abaqus_job(abaqus_cmd, job_name, run_dir):
    """
    使用命令行运行 Abaqus 作业
    """
    cmd = [abaqus_cmd, f"job={job_name}", "interactive"]
    print("RUN:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=run_dir)


def main():
    """
    主函数：执行参数扫描
    """
    if len(sys.argv) < 3:
        print("Usage: python sweep.py base_case.json sweep_config.json [abaqus_config.json]")
        sys.exit(1)

    project_root = Path(__file__).parent.parent.resolve()
    os.chdir(project_root)

    base_case_path = Path(sys.argv[1]).resolve()
    sweep_cfg_path = Path(sys.argv[2]).resolve()

    abaqus_config_path = None
    if len(sys.argv) >= 4:
        abaqus_config_path = Path(sys.argv[3]).resolve()
    else:
        default_config = project_root / "abaqus_config.json"
        if default_config.exists():
            abaqus_config_path = default_config

    abaqus_cmd = get_abaqus_cmd(abaqus_config_path)
    print("Using Abaqus:", abaqus_cmd)
    print("Project Root:", project_root)

    base_cfg = load_json(base_case_path)
    sweep_cfg = load_json(sweep_cfg_path)

    case_id = base_cfg["case_id"]
    runs_root = project_root / "runs" / case_id
    runs_root.mkdir(parents=True, exist_ok=True)

    scripts_dir = project_root / "scripts"
    build_script = scripts_dir / "build_model.py"
    run_job_script = scripts_dir / "run_job.py"
    extract_script = scripts_dir / "extract_odb.py"

    summary_path = runs_root / "scan_summary.csv"
    with open(summary_path, "w", newline="", encoding="utf-8") as fsum:
        writer = csv.writer(fsum)
        writer.writerow([
            "case_id", "param_id",
            "global_size", "refine_size", "refine_radius", "family", "max_inc", "contact_mode",
            "run_dir"
        ])

        for i, params in enumerate(param_product(sweep_cfg["grid"])):
            param_id = f"p{i:04d}"
            run_dir = runs_root / param_id
            run_dir.mkdir(parents=True, exist_ok=True)

            case_cfg = update_case(base_cfg, params, param_id)
            case_cfg_path = run_dir / "case.json"
            save_json(case_cfg_path, case_cfg)

            print(f"\n{'='*60}")
            print(f"Processing: {param_id}")
            print(f"{'='*60}")

            run_abaqus_script(abaqus_cmd, build_script, {
                "ABAQUS_CASE_JSON": str(case_cfg_path),
                "ABAQUS_RUN_DIR": str(run_dir)
            })

            run_abaqus_script(abaqus_cmd, run_job_script, {
                "ABAQUS_RUN_DIR": str(run_dir),
                "ABAQUS_JOB_NAME": "Job-1"
            })

            run_abaqus_job(abaqus_cmd, "Job-1", str(run_dir))

            odb_path = run_dir / "Job-1.odb"
            run_abaqus_script(abaqus_cmd, extract_script, {
                "ABAQUS_ODB_PATH": str(odb_path),
                "ABAQUS_OUT_DIR": str(run_dir)
            })

            writer.writerow([
                case_id, param_id,
                params.get("global_size"),
                params.get("refine_size"),
                params.get("refine_radius"),
                params.get("family"),
                params.get("max_inc"),
                params.get("contact_mode"),
                str(run_dir)
            ])

    print("\n" + "="*60)
    print("Saved summary to", summary_path)
    print("="*60)


if __name__ == "__main__":
    main()
