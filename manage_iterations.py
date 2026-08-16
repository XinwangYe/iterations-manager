#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""管理 Azure DevOps 项目 iterations（Sprint）的入口脚本。

业务逻辑位于 iterations_manager 包:
    models.py   数据模型与业务常量
    config.py   YAML 配置加载与字段校验
    planner.py  执行计划构建 (release 解析 / sprint 生成 / team 范围过滤)
    client.py   Azure DevOps REST API 客户端
    cli.py      命令行入口、计划预览与执行

用法:
    python manage_iterations.py -c config.yml            # 实际执行
    python manage_iterations.py -c config.yml --dry-run  # 仅预览生成结果
    python -m iterations_manager -c config.yml           # 等价方式
"""

import sys

from iterations_manager.cli import main

if __name__ == "__main__":
    sys.exit(main())
