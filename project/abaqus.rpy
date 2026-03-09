# -*- coding: mbcs -*-
#
# Abaqus/CAE Release 2024 replay file
# Internal Version: 2023_09_21-20.55.25 RELr426 190762
# Run by W on Mon Mar  9 10:55:04 2026
#

# from driverUtils import executeOnCaeGraphicsStartup
# executeOnCaeGraphicsStartup()
#: Executing "onCaeGraphicsStartup()" in the site directory ...
from abaqus import *
from abaqusConstants import *
session.Viewport(name='Viewport: 1', origin=(1.07451, 0.865979), width=158.168, 
    height=85.9052)
session.viewports['Viewport: 1'].makeCurrent()
from driverUtils import executeOnCaeStartup
executeOnCaeStartup()
execfile(
    'E:/workspace/geometric-contact-potential-main/project/scripts/extract_odb.py', 
    __main__.__dict__)
#: 模型: E:/workspace/geometric-contact-potential-main/project/runs/sphere_plane_2d/p0000/Job-1.odb
#: 装配件个数:         1
#: 装配件实例个数: 0
#: 部件实例的个数:     2
#: 网格数:             2
#: 单元集合数:       1
#: 结点集合数:          1
#: 分析步的个数:              1
#* 0
#* File 
#* "E:/workspace/geometric-contact-potential-main/project/scripts/extract_odb.py", 
#* line 236, in <module>
#*     main()
#* File 
#* "E:/workspace/geometric-contact-potential-main/project/scripts/extract_odb.py", 
#* line 228, in main
#*     write_field_csv(odb, out_dir, meta)
#* File 
#* "E:/workspace/geometric-contact-potential-main/project/scripts/extract_odb.py", 
#* line 156, in write_field_csv
#*     frame = odb.steps[step_name].frames[-1]
