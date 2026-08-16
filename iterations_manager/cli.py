# -*- coding: utf-8 -*-
"""命令行入口: 计划预览与实际执行。"""

from __future__ import annotations

import argparse
import sys

from iterations_manager.client import AzureDevOpsClient
from iterations_manager.config import ConfigError, load_config
from iterations_manager.planner import Plan, build_plan


def print_plan(plan: Plan) -> None:
    """打印生成的迭代定义与 team 添加范围。"""
    print(f"[定义] 共 {len(plan.sprints)} 个迭代，location: {plan.location or '(Iterations 根节点)'}")
    for s in plan.sprints:
        mark = " (Cool down)" if s.is_cool_down else ""
        print(f"  {s.name:<22} {s.start.isoformat()} ~ {s.end.isoformat()}{mark}")
    if plan.team_name:
        keys = [s.key for s in plan.selected]
        if keys:
            lo, hi = min(keys), max(keys)
            span = f"R{lo[0]}.{lo[1]} ~ R{hi[0]}.{hi[1]}"
        else:
            span = "空"
        print(f"[Team] {plan.team_name} 将添加 {len(plan.selected)} 个迭代，范围: {span}")
    else:
        print("[Team] 未配置 team，跳过")


def execute(plan: Plan, pat: str) -> None:
    """调用 Azure DevOps API 执行计划: 创建迭代节点并添加到 team。"""
    client = AzureDevOpsClient(plan.organization, plan.project, pat)
    print(f"\n[执行] 在 {plan.organization}/{plan.project} 创建迭代节点 ...")
    if plan.location:
        client.ensure_location(plan.location)

    identifiers: dict[tuple[int, int], str] = {}
    for sprint in plan.sprints:
        identifier, status = client.create_or_update_iteration(plan.location, sprint)
        identifiers[sprint.key] = identifier
        print(f"  [{status:>9}] {sprint.name}  {sprint.start} ~ {sprint.end}")

    if plan.team_name and plan.selected:
        print(f"\n[执行] 添加迭代到 team: {plan.team_name} ...")
        existing_ids = client.get_team_iteration_ids(plan.team_name)
        for sprint in plan.selected:
            identifier = identifiers[sprint.key]
            if identifier in existing_ids:
                print(f"  [ exists ] {sprint.name}")
                continue
            client.add_iteration_to_team(plan.team_name, identifier)
            print(f"  [  added ] {sprint.name}")

    print("\n完成。")


def run(config_path: str, dry_run: bool) -> None:
    """加载配置、构建计划、预览并按需执行。"""
    plan = build_plan(load_config(config_path))
    if plan.team_name and not plan.selected:
        print("[警告] team.range 过滤后没有可添加的迭代", file=sys.stderr)

    print_plan(plan)
    if dry_run:
        print("[dry-run] 仅预览，未调用 Azure DevOps API")
        return

    if not plan.pat:
        raise ConfigError(f"未提供 PAT: 请设置环境变量 {plan.pat_env}，或在 azure.pat 中配置")
    execute(plan, plan.pat)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="管理 Azure DevOps iterations")
    parser.add_argument("-c", "--config", default="config.yml",
                        help="YAML 配置文件路径 (默认: config.yml)")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅打印将生成的迭代与执行计划，不调用 API")
    args = parser.parse_args(argv)

    try:
        run(args.config, args.dry_run)
    except (ConfigError, RuntimeError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1
    return 0
