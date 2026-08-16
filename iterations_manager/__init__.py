# -*- coding: utf-8 -*-
"""管理 Azure DevOps 项目 iterations（Sprint）的工具包。

用法:
    python manage_iterations.py -c config.yml [--dry-run]
    python -m iterations_manager -c config.yml [--dry-run]
"""

from iterations_manager.cli import main

__all__ = ["main"]
