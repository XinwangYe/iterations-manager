# -*- coding: utf-8 -*-
"""执行计划构建: 从配置字典生成 release / sprint 定义与 team 范围。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import timedelta

from iterations_manager.config import ConfigError, parse_sprint_ref, to_date, to_year
from iterations_manager.models import (
    DEFAULT_PAT_ENV,
    SPRINT_END_OFFSET_DAYS,
    SPRINT_LENGTH_DAYS,
    Release,
    Sprint,
)


@dataclass
class Plan:
    """一次运行所需的全部信息，由 build_plan() 从配置构建。"""

    organization: str
    project: str
    location: str                          # 迭代所在 location，空表示 Iterations 根节点
    sprints: list[Sprint]                  # 全部生成的迭代
    team_name: str | None = None           # 要添加迭代的 team，None 表示跳过
    selected: list[Sprint] = field(default_factory=list)  # 将添加到 team 的迭代
    pat_env: str = DEFAULT_PAT_ENV
    pat: str | None = None                 # 解析后的 PAT（可能为空，执行前校验）


def build_releases(releases_cfg: object) -> list[Release]:
    """解析并校验 iterations.releases 配置项。"""
    if not isinstance(releases_cfg, list) or not releases_cfg:
        raise ConfigError("iterations.releases 必须是非空列表")
    releases: list[Release] = []
    for i, item in enumerate(releases_cfg, start=1):
        if not isinstance(item, dict):
            raise ConfigError(f"releases[{i}] 必须是映射")
        start = to_date(item.get("start_date"), f"releases[{i}].start_date")
        if start.weekday() != 0:
            raise ConfigError(
                f"releases[{i}].start_date ({start.isoformat()}) 必须是周一，"
                f"sprint 从第一周周一开始"
            )
        sprints = item.get("sprints")
        if sprints is not None and (not isinstance(sprints, int) or sprints < 1):
            raise ConfigError(f"releases[{i}].sprints 必须是正整数")
        year = item.get("year")
        releases.append(Release(
            index=i,
            start=start,
            cool_down=bool(item.get("cool_down", False)),
            sprints=sprints,
            year=to_year(year, f"releases[{i}].year") if year is not None else None,
        ))
    return releases


def resolve_sprint_counts(releases: list[Release]) -> None:
    """确定每个 release 的 sprint 数量。

    优先使用显式配置的 sprints；否则根据下一个 release 的开始日期推算
    （两个 release 开始日期之间必须是 14 天的整数倍）。
    """
    for i, rel in enumerate(releases):
        if rel.sprints is not None:
            continue
        if i + 1 < len(releases):
            days = (releases[i + 1].start - rel.start).days
            if days <= 0 or days % SPRINT_LENGTH_DAYS != 0:
                raise ConfigError(
                    f"R{rel.index} 未指定 sprints，且与下一个 release 的间隔 "
                    f"({days} 天) 不是 {SPRINT_LENGTH_DAYS} 天的整数倍，无法推算数量"
                )
            rel.sprints = days // SPRINT_LENGTH_DAYS
        else:
            raise ConfigError(
                f"R{rel.index} 是最后一个 release，必须显式指定 sprints 数量"
            )


def build_sprints(releases: list[Release], default_year: int | None) -> list[Sprint]:
    """根据 release 定义生成全部 sprint。

    命名年份取 release.year，未指定时回退到 default_year；
    每个 sprint 两周，起始日为第一周周一，结束日为第二周周五。
    """
    resolve_sprint_counts(releases)
    sprints: list[Sprint] = []
    for rel in releases:
        assert rel.sprints is not None  # resolve_sprint_counts 已保证填充
        year = rel.year if rel.year is not None else default_year
        if year is None:  # build_plan 已保证不会出现，这里仅为类型收窄
            raise ConfigError(f"R{rel.index} 缺少命名年份: 请配置 year")
        first_number = 0 if rel.cool_down else 1  # cool down 从 0 开始，normal 从 1 开始
        for k in range(rel.sprints):
            number = first_number + k
            start = rel.start + timedelta(days=SPRINT_LENGTH_DAYS * k)
            end = start + timedelta(days=SPRINT_END_OFFSET_DAYS)
            sprints.append(Sprint(
                release=rel.index,
                number=number,
                name=f"Sprint {year}.R{rel.index}.{number}",
                start=start,
                end=end,
                is_cool_down=(k == 0 and rel.cool_down),
            ))
    return sprints


def filter_by_range(sprints: list[Sprint], range_cfg: object) -> list[Sprint]:
    """按 team.range (from/to, 闭区间) 过滤要添加到 team 的迭代。"""
    if not range_cfg:
        return list(sprints)
    if not isinstance(range_cfg, dict):
        raise ConfigError("team.range 必须是包含 from/to 的映射")
    lo = parse_sprint_ref(range_cfg.get("from"), "team.range.from")
    hi = parse_sprint_ref(range_cfg.get("to"), "team.range.to")
    if lo > hi:
        raise ConfigError("team.range.from 不能晚于 team.range.to")
    return [s for s in sprints if lo <= s.key <= hi]


def build_plan(cfg: dict) -> Plan:
    """把原始配置字典解析为可执行的 Plan，所有校验在此完成。"""
    azure_cfg = cfg.get("azure") or {}
    organization = azure_cfg.get("organization")
    project = azure_cfg.get("project")
    if not isinstance(organization, str) or not organization:
        raise ConfigError("azure.organization 必填且必须是字符串")
    if not isinstance(project, str) or not project:
        raise ConfigError("azure.project 必填且必须是字符串")
    pat_env = azure_cfg.get("pat_env") or DEFAULT_PAT_ENV

    iterations_cfg = cfg.get("iterations") or {}
    location = str(iterations_cfg.get("location") or "").strip().strip("/")
    releases = build_releases(iterations_cfg.get("releases"))

    # 命名年份必须在配置中显式指定: 全局 iterations.year，或每个 release 单独指定 year
    default_year_cfg = iterations_cfg.get("year")
    default_year = (
        to_year(default_year_cfg, "iterations.year") if default_year_cfg is not None else None
    )
    if default_year is None and any(rel.year is None for rel in releases):
        raise ConfigError(
            "未指定迭代命名年份: 请配置 iterations.year，或为每个 release 指定 year"
        )

    team_cfg = cfg.get("team") or {}
    team_name = team_cfg.get("name")
    if team_name is not None and not isinstance(team_name, str):
        raise ConfigError("team.name 必须是字符串")
    sprints = build_sprints(releases, default_year)
    pat = azure_cfg.get("pat")
    if pat is not None and not isinstance(pat, str):
        raise ConfigError("azure.pat 必须是字符串")
    return Plan(
        organization=organization,
        project=project,
        location=location,
        sprints=sprints,
        team_name=team_name,
        selected=filter_by_range(sprints, team_cfg.get("range")),
        pat_env=pat_env,
        pat=pat or os.environ.get(pat_env),
    )
