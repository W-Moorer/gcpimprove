可以。下面给你一套**可直接改写**的骨架，按这条链路跑：

`case.json -> build_model.py -> run_job.py -> extract_odb.py -> sweep.py`

这套方式符合 Abaqus 的官方脚本入口：可以用 `abaqus cae noGUI=script.py -- args...` 无界面执行，也可以用 `job.submit()` 和 `job.waitForCompletion()` 提交并等待作业完成；ODB 结果则分别从 `historyRegions` 和 `fieldOutputs` 读取。Abaqus 2024 起脚本环境是 Python 3.10.5，这对字符串、路径和旧脚本兼容性都有影响。([docs.software.vt.edu][1])

你后续最关键的接触输出，建议固定成这几类：whole-surface history 用 `CFNM`、`CAREA`、`XN`、`CMN`；field output 用 `CSTRESS`、`CDISP`、`CFORCE`、`CSTATUS`、`CNAREA`，分别对应你常用的 `CPRESS`、`COPEN`、`CNORMF`、接触状态和结点接触面积。官方也明确给出了这些变量的可用性。([docs.software.vt.edu][2])

---

## 1) `case.json`

先用一个统一配置文件驱动建模。

```json
{
  "case_id": "sphere_plane_axisym",
  "param_id": "p0001",
  "analysis": {
    "product": "Abaqus/Standard",
    "step_type": "StaticStep",
    "nlgeom": false
  },
  "geometry": {
    "type": "sphere_plane_axisym",
    "R": 10.0,
    "block_w": 40.0,
    "block_h": 20.0
  },
  "material": {
    "name": "Mat-1",
    "E": 210000.0,
    "nu": 0.3
  },
  "contact": {
    "mode": "contact_pair",
    "normal": "hard",
    "tangential": "frictionless",
    "finite_sliding": true
  },
  "mesh": {
    "family": "CAX4I",
    "global_size": 1.0,
    "refine_size": 0.1,
    "refine_radius": 5.0
  },
  "loading": {
    "disp": -0.02,
    "time_period": 1.0,
    "initial_inc": 0.001,
    "max_inc": 0.01,
    "min_inc": 1e-08
  },
  "output": {
    "history_surface_vars": ["CFNM", "CAREA", "XN", "CMN"],
    "field_surface_vars": ["CSTRESS", "CDISP", "CFORCE", "CSTATUS", "CNAREA"]
  }
}
```

---

## 2) `build_model.py`

这个脚本只负责：**读配置、建模、网格、输出请求、保存 `.cae` 和 Job**。

```python
# -*- coding: utf-8 -*-
"""
Usage:
  abaqus cae noGUI=build_model.py -- case.json run_dir
"""

import json
import os
import sys
from math import fabs

# Abaqus imports
from abaqus import mdb
from abaqusConstants import *
import regionToolset
import mesh


def load_args():
    if "--" not in sys.argv:
        raise RuntimeError("Expected arguments after '--': case.json run_dir")
    idx = sys.argv.index("--")
    case_json = sys.argv[idx + 1]
    run_dir = sys.argv[idx + 2]
    return case_json, run_dir


def ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def read_case(path):
    with open(path, "r") as f:
        return json.load(f)


def create_material_and_section(model, cfg):
    mat = cfg["material"]
    model.Material(name=mat["name"])
    model.materials[mat["name"]].Elastic(table=((mat["E"], mat["nu"]),))


def build_axisymmetric_sphere_plane(model, cfg):
    """
    简化骨架：
    - 下方可变形块体
    - 上方解析刚体圆弧（轴对称里可作为刚体轮廓）
    这里保留了主要接口，具体几何点位可按你的尺度微调。
    """
    geo = cfg["geometry"]
    block_w = geo["block_w"]
    block_h = geo["block_h"]
    R = geo["R"]

    # ---- deformable block ----
    s = model.ConstrainedSketch(name="block_sketch", sheetSize=max(block_w, block_h) * 4.0)
    s.rectangle(point1=(0.0, 0.0), point2=(block_w, block_h))
    p_block = model.Part(name="Block", dimensionality=AXISYMMETRIC, type=DEFORMABLE_BODY)
    p_block.BaseShell(sketch=s)
    del model.sketches["block_sketch"]

    # section assignment
    model.HomogeneousSolidSection(name="SolidSection", material=cfg["material"]["name"], thickness=None)
    region = regionToolset.Region(faces=p_block.faces)
    p_block.SectionAssignment(region=region, sectionName="SolidSection")

    # ---- rigid indenter as analytic rigid surface ----
    s2 = model.ConstrainedSketch(name="ind_sketch", sheetSize=max(block_w, block_h) * 4.0)
    # 这里用圆弧近似球头剖面；位置留出初始间隙
    y0 = block_h + 0.2 * R
    x_mid = 0.0
    s2.ArcByCenterEnds(center=(x_mid, y0), point1=(0.0, y0 - R), point2=(R, y0), direction=CLOCKWISE)
    p_ind = model.Part(name="Indenter", dimensionality=AXISYMMETRIC, type=ANALYTIC_RIGID_SURFACE)
    p_ind.AnalyticRigidSurf2DPlanar(sketch=s2)
    del model.sketches["ind_sketch"]

    # reference point for rigid body
    rp = p_ind.ReferencePoint(point=(0.0, y0))
    rp_region = regionToolset.Region(referencePoints=(p_ind.referencePoints[rp.id],))
    surf_region = regionToolset.Region(side1Edges=p_ind.edges)
    model.RigidBody(name="RigidBody-Indenter", refPointRegion=rp_region, surfaceRegion=surf_region)

    return p_block, p_ind


def assemble_model(model, p_block, p_ind):
    a = model.rootAssembly
    a.DatumCsysByDefault(CARTESIAN)
    i_block = a.Instance(name="Block-1", part=p_block, dependent=ON)
    i_ind = a.Instance(name="Indenter-1", part=p_ind, dependent=ON)
    return a, i_block, i_ind


def create_step(model, cfg):
    ld = cfg["loading"]
    model.StaticStep(
        name="Step-1",
        previous="Initial",
        nlgeom=cfg["analysis"]["nlgeom"],
        timePeriod=ld["time_period"],
        initialInc=ld["initial_inc"],
        maxInc=ld["max_inc"],
        minInc=ld["min_inc"],
    )


def create_bcs_and_loads(model, assembly, inst_block, inst_ind, cfg):
    ld = cfg["loading"]

    # block bottom fixed in Y
    bottom_edges = inst_block.edges.getByBoundingBox(
        xMin=-1e-9, yMin=-1e-9, zMin=-1e-9, xMax=1e9, yMax=1e-9, zMax=1e9
    )
    model.DisplacementBC(
        name="BC-Bottom",
        createStepName="Initial",
        region=regionToolset.Region(edges=bottom_edges),
        u1=UNSET,
        u2=SET,
        ur3=UNSET,
    )

    # axis boundary at x=0
    axis_edges = inst_block.edges.getByBoundingBox(
        xMin=-1e-9, yMin=-1e9, zMin=-1e9, xMax=1e-9, yMax=1e9, zMax=1e9
    )
    model.XsymmBC(
        name="BC-Axis",
        createStepName="Initial",
        region=regionToolset.Region(edges=axis_edges),
    )

    # rigid indenter RP displacement
    rp = inst_ind.referencePoints
    rp_obj = rp[rp.keys()[0]]
    model.DisplacementBC(
        name="BC-Indenter",
        createStepName="Step-1",
        region=regionToolset.Region(referencePoints=(rp_obj,)),
        u1=SET, u2=ld["disp"], ur3=SET
    )


def create_contact(model, assembly, inst_block, inst_ind, cfg):
    ct = cfg["contact"]

    # Define surfaces
    # 这里简化为：block 顶边 / rigid 全边
    block_top = inst_block.edges.getByBoundingBox(
        xMin=-1e9, yMin=cfg["geometry"]["block_h"] - 1e-9, zMin=-1e9,
        xMax=1e9, yMax=cfg["geometry"]["block_h"] + 1e-9, zMax=1e9
    )
    s_block = assembly.Surface(name="S_BLOCK_TOP", side1Edges=block_top)
    s_ind = assembly.Surface(name="S_IND", side1Edges=inst_ind.edges)

    prop = model.ContactProperty("IntProp-1")
    if ct["normal"] == "hard":
        prop.NormalBehavior(pressureOverclosure=HARD, allowSeparation=ON)
    if ct["tangential"] == "frictionless":
        prop.TangentialBehavior(formulation=FRICTIONLESS)

    if ct["mode"] == "contact_pair":
        model.SurfaceToSurfaceContactStd(
            name="Int-1",
            createStepName="Initial",
            master=s_ind,
            slave=s_block,
            sliding=FINITE if ct["finite_sliding"] else SMALL,
            interactionProperty="IntProp-1",
            adjustMethod=NONE,
            thickness=ON,
        )
    else:
        model.ContactStd(name="GeneralContact", createStepName="Initial")
        model.interactions["GeneralContact"].includedPairs.setValuesInStep(
            stepName="Initial", useAllstar=ON
        )
        model.interactions["GeneralContact"].contactPropertyAssignments.appendInStep(
            stepName="Initial", assignments=((GLOBAL, SELF, "IntProp-1"),)
        )


def seed_and_mesh_part_block(p_block, cfg):
    ms = cfg["mesh"]
    family = ms["family"]
    p_block.seedPart(size=ms["global_size"], deviationFactor=0.1, minSizeFactor=0.1)

    # 元素类型
    face_region = (p_block.faces,)
    if family == "CAX4I":
        elem_type = mesh.ElemType(elemCode=CAX4I, elemLibrary=STANDARD)
    elif family == "CAX4R":
        elem_type = mesh.ElemType(elemCode=CAX4R, elemLibrary=STANDARD)
    elif family == "CAX8R":
        elem_type = mesh.ElemType(elemCode=CAX8R, elemLibrary=STANDARD)
    else:
        raise ValueError("Unsupported family: {}".format(family))

    p_block.setElementType(regions=face_region, elemTypes=(elem_type,))
    p_block.generateMesh()


def create_output_requests(model, assembly, inst_block, inst_ind, cfg):
    out_cfg = cfg["output"]

    # 参考点 history
    rp = inst_ind.referencePoints
    rp_obj = rp[rp.keys()[0]]
    model.HistoryOutputRequest(
        name="H-RP",
        createStepName="Step-1",
        variables=("U2", "RF2"),
        region=regionToolset.Region(referencePoints=(rp_obj,)),
        frequency=1
    )

    # whole-surface history
    # Abaqus/Standard 支持 CFNM/CAREA/XN/CMN 等 whole-surface quantity
    s_block = assembly.surfaces["S_BLOCK_TOP"]
    model.HistoryOutputRequest(
        name="H-SURF",
        createStepName="Step-1",
        variables=tuple(out_cfg["history_surface_vars"]),
        region=s_block,
        frequency=1
    )

    # field output
    model.fieldOutputRequests["F-Output-1"].setValues(
        variables=tuple(out_cfg["field_surface_vars"]),
        frequency=1
    )


def save_meta(run_dir, cfg):
    meta_path = os.path.join(run_dir, "meta.json")
    with open(meta_path, "w") as f:
        json.dump(cfg, f, indent=2)


def main():
    case_json, run_dir = load_args()
    ensure_dir(run_dir)
    cfg = read_case(case_json)

    model_name = "Model-1"
    if model_name in mdb.models:
        del mdb.models[model_name]
    model = mdb.Model(name=model_name)

    create_material_and_section(model, cfg)
    if cfg["geometry"]["type"] != "sphere_plane_axisym":
        raise NotImplementedError("Only sphere_plane_axisym is implemented in this skeleton.")

    p_block, p_ind = build_axisymmetric_sphere_plane(model, cfg)
    assembly, i_block, i_ind = assemble_model(model, p_block, p_ind)
    create_step(model, cfg)
    create_contact(model, assembly, i_block, i_ind, cfg)
    create_bcs_and_loads(model, assembly, i_block, i_ind, cfg)
    seed_and_mesh_part_block(p_block, cfg)
    create_output_requests(model, assembly, i_block, i_ind, cfg)

    job_name = "Job-1"
    mdb.Job(name=job_name, model=model_name)

    cae_path = os.path.join(run_dir, "model.cae")
    mdb.saveAs(pathName=cae_path)
    save_meta(run_dir, cfg)
    print("Saved:", cae_path)


if __name__ == "__main__":
    main()
```

---

## 3) `run_job.py`

这个脚本只负责：**打开 `.cae`，提交作业，等它结束**。这是 Abaqus 官方示例里最标准的做法。([docs.software.vt.edu][3])

```python
# -*- coding: utf-8 -*-
"""
Usage:
  abaqus cae noGUI=run_job.py -- run_dir job_name
"""

import os
import sys
from abaqus import openMdb, mdb


def load_args():
    if "--" not in sys.argv:
        raise RuntimeError("Expected arguments after '--': run_dir job_name")
    idx = sys.argv.index("--")
    run_dir = sys.argv[idx + 1]
    job_name = sys.argv[idx + 2]
    return run_dir, job_name


def main():
    run_dir, job_name = load_args()
    cae_path = os.path.join(run_dir, "model.cae")
    if not os.path.isfile(cae_path):
        raise IOError("Missing CAE file: {}".format(cae_path))

    openMdb(pathName=cae_path)
    job = mdb.jobs[job_name]
    job.submit()
    job.waitForCompletion()
    mdb.save()
    print("Completed:", job_name)


if __name__ == "__main__":
    main()
```

---

## 4) `extract_odb.py`

这个脚本只负责：**从 ODB 导出统一的 CSV**。
官方说明 history 数据在 `historyRegions`，field 数据在每个 frame 的 `fieldOutputs` 里。([docs.software.vt.edu][4])

```python
# -*- coding: utf-8 -*-
"""
Usage:
  abaqus cae noGUI=extract_odb.py -- path/to/Job-1.odb out_dir
"""

import csv
import json
import math
import os
import sys

from odbAccess import openOdb


def load_args():
    if "--" not in sys.argv:
        raise RuntimeError("Expected arguments after '--': odb_path out_dir")
    idx = sys.argv.index("--")
    odb_path = sys.argv[idx + 1]
    out_dir = sys.argv[idx + 2]
    return odb_path, out_dir


def ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def get_case_meta(out_dir):
    meta_path = os.path.join(out_dir, "meta.json")
    if os.path.isfile(meta_path):
        with open(meta_path, "r") as f:
            return json.load(f)
    return {"case_id": "unknown", "param_id": "unknown"}


def write_history_csv(odb, out_dir, meta):
    step_name = list(odb.steps.keys())[-1]
    step = odb.steps[step_name]
    history_path = os.path.join(out_dir, "history.csv")

    # 尝试自动找 RP 和 surface history region
    rp_region_name = None
    surf_region_name = None
    for k in step.historyRegions.keys():
        ku = k.upper()
        if "Node" in k or "Node " in k or "NODE" in ku:
            rp_region_name = rp_region_name or k
        if "Surface" in k or "SURFACE" in ku:
            surf_region_name = surf_region_name or k

    with open(history_path, "w") as f:
        writer = csv.writer(f)
        writer.writerow([
            "case_id", "param_id", "step_name", "frame_i", "time",
            "u2", "rf2", "cfnm", "carea", "xn1", "xn2", "xn3", "cmn1", "cmn2", "cmn3"
        ])

        # 读 history 输出
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
    return frame.fieldOutputs[key] if key in frame.fieldOutputs else None


def vec_mag(v):
    return math.sqrt(sum(x * x for x in v))


def write_field_csv(odb, out_dir, meta):
    step_name = list(odb.steps.keys())[-1]
    frame = odb.steps[step_name].frames[-1]
    field_path = os.path.join(out_dir, "field_last.csv")

    cstress = safe_get_field(frame, "CSTRESS")   # CPRESS may be in components
    cdisp = safe_get_field(frame, "CDISP")       # COPEN
    cforce = safe_get_field(frame, "CFORCE")     # CNORMF
    cstatus = safe_get_field(frame, "CSTATUS")
    cnarea = safe_get_field(frame, "CNAREA")

    # 简化处理：按 rootAssembly 全部 surface-node 数据导出
    # 实际项目里建议对指定 surface / nodeSet 做 getSubset(region=...)
    with open(field_path, "w") as f:
        writer = csv.writer(f)
        writer.writerow([
            "case_id", "param_id", "step_name",
            "surface_name", "node_label", "x", "y", "z",
            "cstatus", "copen", "cpress",
            "cnormf1", "cnormf2", "cnormf3", "cnormf_mag", "cnarea"
        ])

        # 以 CFORCE 为主索引
        values = cforce.values if cforce else []
        for v in values:
            # 位置
            xyz = (None, None, None)
            if hasattr(v, "instance") and hasattr(v, "nodeLabel"):
                inst = v.instance
                node = inst.getNodeFromLabel(v.nodeLabel)
                xyz = tuple(node.coordinates)

            label = getattr(v, "nodeLabel", None)
            force = tuple(v.data) if hasattr(v, "data") else (None, None, None)

            # 同 label 匹配其它场
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
```

---

## 5) `sweep.py`

这个脚本建议用**系统 Python** 跑，负责生成参数组合并调 Abaqus。
Abaqus 也支持 `.psf` 参数化研究，但对你这种“统一驱动建模 + 导出 + 与外部优化器对接”的流程，自己写 Python 编排更灵活。([docs.software.vt.edu][5])

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import copy
import csv
import itertools
import json
import os
import subprocess
import sys
from pathlib import Path


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def param_product(grid):
    keys = list(grid.keys())
    vals = [grid[k] for k in keys]
    for combo in itertools.product(*vals):
        yield dict(zip(keys, combo))


def update_case(base_cfg, params, param_id):
    cfg = copy.deepcopy(base_cfg)
    cfg["param_id"] = param_id

    # 你可以在这里扩展映射规则
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


def run_cmd(cmd, cwd=None):
    print("RUN:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=cwd)


def main():
    if len(sys.argv) != 3:
        print("Usage: python sweep.py base_case.json sweep_config.json")
        sys.exit(1)

    base_case_path = Path(sys.argv[1]).resolve()
    sweep_cfg_path = Path(sys.argv[2]).resolve()

    base_cfg = load_json(base_case_path)
    sweep_cfg = load_json(sweep_cfg_path)

    case_id = base_cfg["case_id"]
    runs_root = Path("runs") / case_id
    runs_root.mkdir(parents=True, exist_ok=True)

    summary_path = runs_root / "scan_summary.csv"
    with open(summary_path, "w", newline="") as fsum:
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

            # 1) build
            run_cmd([
                "abaqus", "cae", f"noGUI=scripts/build_model.py",
                "--", str(case_cfg_path), str(run_dir)
            ])

            # 2) solve
            run_cmd([
                "abaqus", "cae", f"noGUI=scripts/run_job.py",
                "--", str(run_dir), "Job-1"
            ])

            # 3) extract
            odb_path = run_dir / "Job-1.odb"
            run_cmd([
                "abaqus", "cae", f"noGUI=scripts/extract_odb.py",
                "--", str(odb_path), str(run_dir)
            ])

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

    print("Saved summary to", summary_path)


if __name__ == "__main__":
    main()
```

---

## 6) `sweep_config.json`

```json
{
  "grid": {
    "global_size": [1.0, 0.5, 0.25],
    "refine_size": [0.1, 0.05],
    "refine_radius": [3.0, 5.0],
    "family": ["CAX4I", "CAX4R"],
    "max_inc": [0.01, 0.005],
    "contact_mode": ["contact_pair"]
  }
}
```

---

## 7) 推荐命令

单次运行：

```bash
abaqus cae noGUI=scripts/build_model.py -- cases/sphere_plane_axisym/case.json runs/sphere_plane_axisym/p0001
abaqus cae noGUI=scripts/run_job.py -- runs/sphere_plane_axisym/p0001 Job-1
abaqus cae noGUI=scripts/extract_odb.py -- runs/sphere_plane_axisym/p0001/Job-1.odb runs/sphere_plane_axisym/p0001
```

参数扫描：

```bash
python scripts/sweep.py cases/sphere_plane_axisym/case.json sweep_config.json
```

---

## 8) 你接下来该怎么用这套骨架

先别同时做很多工况。顺序建议是：

1. 先只做 **球压平面轴对称**。
2. 用 `global_size` 和 `refine_size` 扫三层网格，确认 `CFNM`、`CAREA`、`XN`、`CPRESS` 收敛。
3. 冻结 Abaqus 参考配置。
4. 再开始用同一工况去校准你的 GCP 二次开发模型。
5. 然后复制一份 `build_model.py` 的几何函数，扩展成 **圆柱-平面** 和 **复杂 3D 曲面**。

这套骨架的价值在于：Abaqus 参考解和你自己的模型参数扫描会被**严格分离**。前者只负责出标准答案，后者才负责拟合和比较。

下一步我可以继续把 **`build_model.py` 里的几何函数**补成两版：
一版是 **圆柱-平面平面应变**，另一版是 **3D 刚体曲面压柔性块体**。

[1]: https://docs.software.vt.edu/abaqusv2025/English/?show=SIMACAECMDRefMap%2Fsimacmd-c-aclintintrointerface.htm&utm_source=chatgpt.com "Abaqus Scripting Interface"
[2]: https://docs.software.vt.edu/abaqusv2024/English/SIMACAEOUTRefMap/simaout-c-std-surfacevariables.htm?utm_source=chatgpt.com "Surface Variables"
[3]: https://docs.software.vt.edu/abaqusv2024/English/SIMACAECMDRefMap/simacmd-c-intexaaclskewparametric.htm?utm_source=chatgpt.com "Using a script to perform a parametric study"
[4]: https://docs.software.vt.edu/abaqusv2025/English/?show=SIMACAECMDRefMap%2Fsimacmd-c-odbintroreadhistpyc.htm&utm_source=chatgpt.com "Reading history output data"
[5]: https://docs.software.vt.edu/abaqusv2024/English/?show=SIMACAEEXCRefMap%2Fsimaexc-c-parametricproc.htm&utm_source=chatgpt.com "Parametric Studies - abaqus script"
