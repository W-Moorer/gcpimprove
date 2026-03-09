# -*- coding: utf-8 -*-
"""
Usage:
  abaqus cae noGUI=extract_odb.py -- path/to/Job-1.odb out_dir
  或通过环境变量:
  set ABAQUS_ODB_PATH=path/to/Job-1.odb
  set ABAQUS_OUT_DIR=out_dir
  abaqus cae noGUI=extract_odb.py
"""

import csv
import json
import math
import os
import sys

from odbAccess import openOdb


def load_args():
    """
    加载命令行参数，支持两种方式：
    1. 命令行参数: -- odb_path out_dir
    2. 环境变量: ABAQUS_ODB_PATH 和 ABAQUS_OUT_DIR
    """
    odb_path = None
    out_dir = None
    
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        if idx + 1 < len(sys.argv):
            odb_path = sys.argv[idx + 1]
        if idx + 2 < len(sys.argv):
            out_dir = sys.argv[idx + 2]
    
    if odb_path is None:
        odb_path = os.environ.get("ABAQUS_ODB_PATH")
    if out_dir is None:
        out_dir = os.environ.get("ABAQUS_OUT_DIR")
    
    if odb_path is None or out_dir is None:
        raise RuntimeError("Expected arguments: odb_path out_dir (via -- or environment variables)")
    
    return odb_path, out_dir


def ensure_dir(path):
    """
    确保目录存在
    """
    if not os.path.isdir(path):
        os.makedirs(path)


def get_case_meta(out_dir):
    """
    获取案例元数据
    """
    meta_path = os.path.join(out_dir, "meta.json")
    if os.path.isfile(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"case_id": "unknown", "param_id": "unknown"}


def write_history_csv(odb, out_dir, meta):
    """
    导出历史数据到CSV文件
    """
    step_name = list(odb.steps.keys())[-1]
    step = odb.steps[step_name]
    history_path = os.path.join(out_dir, "history.csv")

    rp_region_name = None
    surf_region_name = None
    for k in step.historyRegions.keys():
        ku = k.upper()
        if "Node" in k or "Node " in k or "NODE" in ku:
            rp_region_name = rp_region_name or k
        if "Surface" in k or "SURFACE" in ku:
            surf_region_name = surf_region_name or k

    with open(history_path, "w", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "case_id", "param_id", "step_name", "frame_i", "time",
            "u2", "rf2", "cfnm", "carea", "xn1", "xn2", "xn3", "cmn1", "cmn2", "cmn3"
        ])

        rp_hist = step.historyRegions[rp_region_name].historyOutputs if rp_region_name else {}
        sf_hist = step.historyRegions[surf_region_name].historyOutputs if surf_region_name else {}

        u2_series = rp_hist["U2"].data if "U2" in rp_hist else []
        rf2_series = rp_hist["RF2"].data if "RF2" in rp_hist else []
        cfnm_series = sf_hist["CFNM"].data if "CFNM" in sf_hist else []
        carea_series = sf_hist["CAREA"].data if "CAREA" in sf_hist else []
        xn_series = sf_hist["XN"].data if "XN" in sf_hist else []
        cmn_series = sf_hist["CMN"].data if "CMN" in sf_hist else []

        n = max(len(u2_series), len(rf2_series), len(cfnm_series), len(carea_series), len(xn_series), len(cmn_series))
        for i in range(n):
            def get_series_val(series, idx, default=None):
                if idx < len(series):
                    return series[idx]
                return default

            u2 = get_series_val(u2_series, i, (None, None))
            rf2 = get_series_val(rf2_series, i, (None, None))
            cfnm = get_series_val(cfnm_series, i, (None, None))
            carea = get_series_val(carea_series, i, (None, None))
            xn = get_series_val(xn_series, i, (None, (None, None, None)))
            cmn = get_series_val(cmn_series, i, (None, (None, None, None)))

            time = next(v[0] for v in [u2, rf2, cfnm, carea, xn, cmn] if v is not None and v[0] is not None)
            u2v = u2[1] if u2 else None
            rf2v = rf2[1] if rf2 else None
            cfnmv = cfnm[1] if cfnm else None
            careav = carea[1] if carea else None
            xnv = xn[1] if xn else (None, None, None)
            cmnv = cmn[1] if cmn else (None, None, None)

            writer.writerow([
                meta.get("case_id", "unknown"),
                meta.get("param_id", "unknown"),
                step_name,
                i,
                time,
                u2v,
                rf2v,
                cfnmv,
                careav,
                xnv[0], xnv[1], xnv[2],
                cmnv[0], cmnv[1], cmnv[2],
            ])


def safe_get_field(frame, key):
    """
    安全获取场输出
    """
    return frame.fieldOutputs[key] if key in frame.fieldOutputs else None


def vec_mag(v):
    """
    计算向量模
    """
    return math.sqrt(sum(x * x for x in v))


def write_field_csv(odb, out_dir, meta):
    """
    导出场数据到CSV文件
    """
    step_name = list(odb.steps.keys())[-1]
    frame = odb.steps[step_name].frames[-1]
    field_path = os.path.join(out_dir, "field_last.csv")

    cstress = safe_get_field(frame, "CSTRESS")
    cdisp = safe_get_field(frame, "CDISP")
    cforce = safe_get_field(frame, "CFORCE")
    cstatus = safe_get_field(frame, "CSTATUS")
    cnarea = safe_get_field(frame, "CNAREA")

    with open(field_path, "w", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "case_id", "param_id", "step_name",
            "surface_name", "node_label", "x", "y", "z",
            "cstatus", "copen", "cpress",
            "cnormf1", "cnormf2", "cnormf3", "cnormf_mag", "cnarea"
        ])

        values = cforce.values if cforce else []
        for v in values:
            xyz = (None, None, None)
            if hasattr(v, "instance") and hasattr(v, "nodeLabel"):
                inst = v.instance
                node = inst.getNodeFromLabel(v.nodeLabel)
                xyz = tuple(node.coordinates)

            label = getattr(v, "nodeLabel", None)
            force = tuple(v.data) if hasattr(v, "data") else (None, None, None)

            def lookup_scalar(field_obj, label_):
                if field_obj is None:
                    return None
                for vv in field_obj.values:
                    if getattr(vv, "nodeLabel", None) == label_:
                        if isinstance(vv.data, float):
                            return vv.data
                        if isinstance(vv.data, int):
                            return vv.data
                        if hasattr(vv.data, "__len__") and len(vv.data) > 0:
                            return vv.data[0]
                return None

            cpress = lookup_scalar(cstress, label)
            copen = lookup_scalar(cdisp, label)
            cstat = lookup_scalar(cstatus, label)
            area = lookup_scalar(cnarea, label)

            writer.writerow([
                meta.get("case_id", "unknown"),
                meta.get("param_id", "unknown"),
                step_name,
                "AUTO",
                label,
                xyz[0], xyz[1], xyz[2],
                cstat,
                copen,
                cpress,
                force[0], force[1], force[2], vec_mag(force), area
            ])


def main():
    """
    主函数：从ODB导出CSV
    """
    odb_path, out_dir = load_args()
    ensure_dir(out_dir)
    meta = get_case_meta(out_dir)

    odb = openOdb(path=odb_path, readOnly=True)
    try:
        write_history_csv(odb, out_dir, meta)
        write_field_csv(odb, out_dir, meta)
    finally:
        odb.close()

    print("Exported CSV to", out_dir)


if __name__ == "__main__":
    main()
