#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
结果汇总脚本
Usage:
  python aggregate.py runs_root output_dir
"""

import csv
import json
import os
import sys
from pathlib import Path


def load_json(path):
    """
    加载JSON文件
    """
    with open(path, "r") as f:
        return json.load(f)


def load_csv(path):
    """
    加载CSV文件
    """
    rows = []
    if os.path.isfile(path):
        with open(path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    return rows


def aggregate_case(runs_dir, output_dir):
    """
    汇总单个案例的所有运行结果
    """
    runs_path = Path(runs_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    all_history = []
    all_field = []
    summary_rows = []

    for param_dir in sorted(runs_path.iterdir()):
        if not param_dir.is_dir():
            continue

        param_id = param_dir.name
        meta_path = param_dir / "meta.json"
        history_path = param_dir / "history.csv"
        field_path = param_dir / "field_last.csv"

        if meta_path.exists():
            meta = load_json(meta_path)
        else:
            meta = {"case_id": "unknown", "param_id": param_id}

        if history_path.exists():
            history_rows = load_csv(history_path)
            all_history.extend(history_rows)

        if field_path.exists():
            field_rows = load_csv(field_path)
            all_field.extend(field_rows)

        summary_rows.append({
            "case_id": meta.get("case_id", "unknown"),
            "param_id": param_id,
            "run_dir": str(param_dir)
        })

    history_out = output_path / "history_all.csv"
    if all_history:
        with open(history_out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_history[0].keys())
            writer.writeheader()
            writer.writerows(all_history)
        print("Saved:", history_out)

    field_out = output_path / "field_all.csv"
    if all_field:
        with open(field_out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=all_field[0].keys())
            writer.writeheader()
            writer.writerows(all_field)
        print("Saved:", field_out)

    summary_out = output_path / "scan_summary.csv"
    if summary_rows:
        with open(summary_out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
            writer.writeheader()
            writer.writerows(summary_rows)
        print("Saved:", summary_out)


def main():
    """
    主函数：汇总结果
    """
    if len(sys.argv) != 3:
        print("Usage: python aggregate.py runs_root output_dir")
        sys.exit(1)

    runs_dir = sys.argv[1]
    output_dir = sys.argv[2]
    aggregate_case(runs_dir, output_dir)


if __name__ == "__main__":
    main()
