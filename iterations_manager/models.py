# -*- coding: utf-8 -*-
"""数据模型与业务常量。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

SPRINT_LENGTH_DAYS = 14      # 一个 sprint 为 2 周
SPRINT_END_OFFSET_DAYS = 11  # 第一周周一 + 11 天 = 第二周周五
DEFAULT_PAT_ENV = "AZDO_PAT"


@dataclass
class Release:
    """一个 release 的定义，对应配置中 iterations.releases 的一项。"""

    index: int               # release 编号 x，从 1 开始
    start: date              # release 开始日期（必须是周一）
    cool_down: bool          # 第一个 sprint 是否为 Cool down sprint
    sprints: int | None      # 该 release 的 sprint 总数
    year: int | None         # 命名用年份，未指定时回退到 iterations.year


@dataclass
class Sprint:
    """一个生成好的 sprint（迭代）。"""

    release: int             # release 编号 x
    number: int              # release 内编号 y
    name: str                # Sprint YYYY.Rx.y
    start: date
    end: date
    is_cool_down: bool       # 是否为 Cool down sprint

    @property
    def key(self) -> tuple[int, int]:
        """用于排序/范围比较的键 (release 编号, sprint 编号)。"""
        return self.release, self.number
