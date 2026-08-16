# -*- coding: utf-8 -*-
"""Azure DevOps 客户端: 基于官方 azure-devops SDK。

负责迭代分类节点 (classification nodes) 与 team 迭代配置的读写。
为避免逐个 GET 探测节点是否存在（SDK 异常不携带 HTTP 状态码），
首次使用时一次性加载 Iterations 分类树并缓存在内存中。
"""

from __future__ import annotations

from azure.devops.connection import Connection
from azure.devops.exceptions import (
    AzureDevOpsAuthenticationError,
    AzureDevOpsClientRequestError,
    AzureDevOpsServiceError,
)
from azure.devops.v7_1.work.models import TeamContext, TeamSettingsIteration
from azure.devops.v7_1.work_item_tracking.models import WorkItemClassificationNode
from msrest.authentication import BasicAuthentication

from iterations_manager.models import Sprint

STRUCTURE_ITERATIONS = "iterations"


class AzureDevOpsClient:
    def __init__(self, organization: str, project: str, pat: str):
        self._project = project
        credentials = BasicAuthentication("", pat)
        connection = Connection(base_url=f"https://dev.azure.com/{organization}/", creds=credentials)
        self._wit_client = connection.clients.get_work_item_tracking_client()
        self._work_client = connection.clients.get_work_client()
        # Iterations 分类树缓存: {name: {"node": WorkItemClassificationNode, "children": {...}}}
        self._tree: dict | None = None
        self._tree_depth = 0

    # -- 基础 ---------------------------------------------------------------

    @staticmethod
    def _call(action: str, fn, *args, **kwargs):
        """调用 SDK 方法，把 SDK 异常统一转成带操作描述的 RuntimeError。"""
        try:
            return fn(*args, **kwargs)
        except AzureDevOpsAuthenticationError as exc:
            raise RuntimeError(f"{action} 失败（认证失败，请检查 PAT）: {exc}") from exc
        except (AzureDevOpsServiceError, AzureDevOpsClientRequestError) as exc:
            message = getattr(exc, "message", None)
            detail = message if isinstance(message, str) else str(exc)
            raise RuntimeError(f"{action} 失败: {detail}") from exc

    @staticmethod
    def _split_location(location: str) -> list[str]:
        return [seg for seg in location.strip("/\\").split("/") if seg]

    @staticmethod
    def _date_attrs(sprint: Sprint) -> dict:
        # 注意: 分类节点日期属性键为 startDate / finishDate
        return {
            "startDate": f"{sprint.start.isoformat()}T00:00:00Z",
            "finishDate": f"{sprint.end.isoformat()}T00:00:00Z",
        }

    @classmethod
    def _to_tree(cls, node: WorkItemClassificationNode) -> dict:
        return {
            child.name: {"node": child, "children": cls._to_tree(child)}
            for child in (node.children or [])
        }

    def _load_tree(self, min_depth: int) -> dict:
        """加载（或按更深 depth 重新加载）Iterations 分类树。"""
        tree = self._tree
        if tree is None or self._tree_depth < min_depth:
            root = self._call(
                "查询 Iterations 分类树",
                self._wit_client.get_classification_node,
                self._project, STRUCTURE_ITERATIONS, None, min_depth,
            )
            tree = self._to_tree(root)
            self._tree = tree
            self._tree_depth = min_depth
        return tree

    # -- location 目录节点 ----------------------------------------------------

    def ensure_location(self, location: str) -> None:
        """确保 location 路径存在，缺失的中间节点自动创建。"""
        segments = self._split_location(location)
        if not segments:
            return
        tree = self._load_tree(len(segments))
        parent_path = None
        for seg in segments:
            entry = tree.get(seg)
            if entry is None:
                node = WorkItemClassificationNode(name=seg, has_children=False)
                created = self._call(
                    f"创建 location 节点 {seg}",
                    self._wit_client.create_or_update_classification_node,
                    node, self._project, STRUCTURE_ITERATIONS, parent_path,
                )
                tree[seg] = {"node": created, "children": {}}
                child_path = f"{parent_path}\\{seg}" if parent_path else seg
                print(f"  [location] 创建目录节点: {child_path}")
            parent_path = f"{parent_path}\\{seg}" if parent_path else seg
            tree = tree[seg]["children"]

    # -- 迭代节点 -------------------------------------------------------------

    def create_or_update_iteration(self, location: str, sprint: Sprint) -> tuple[str, str]:
        """创建迭代节点；已存在则对齐起止日期。返回 (identifier, 状态)。"""
        segments = self._split_location(location)
        tree = self._load_tree(len(segments) + 1)
        for seg in segments:
            tree = tree.get(seg, {"children": {}})["children"]

        attributes = self._date_attrs(sprint)
        entry = tree.get(sprint.name)
        parent_path = "\\".join(segments) or None
        if entry is None:
            node = WorkItemClassificationNode(
                name=sprint.name, has_children=False, attributes=attributes,
            )
            created = self._call(
                f"创建迭代 {sprint.name}",
                self._wit_client.create_or_update_classification_node,
                node, self._project, STRUCTURE_ITERATIONS, parent_path,
            )
            tree[sprint.name] = {"node": created, "children": {}}
            return created.identifier, "created"

        node = entry["node"]
        existing = node.attributes or {}
        need_update = (
                str(existing.get("startDate") or "")[:10] != sprint.start.isoformat()
                or str(existing.get("finishDate") or "")[:10] != sprint.end.isoformat()
        )
        if need_update:
            updated_node = WorkItemClassificationNode(
                name=node.name,
                structure_type=node.structure_type,
                has_children=node.has_children,
                attributes=attributes,
            )
            self._call(
                f"更新迭代日期 {sprint.name}",
                self._wit_client.update_classification_node,
                updated_node, self._project, STRUCTURE_ITERATIONS,
                "\\".join(segments + [sprint.name]),
            )
            node.attributes = attributes
            return node.identifier, "updated"
        return node.identifier, "unchanged"

    # -- team configuration ---------------------------------------------------

    def _team_context(self, team: str) -> TeamContext:
        return TeamContext(project=self._project, team=team)

    def get_team_iteration_ids(self, team: str) -> set[str]:
        iterations = self._call(
            f"查询 team {team} 的迭代列表",
            self._work_client.get_team_iterations, self._team_context(team),
        )
        return {it.id for it in (iterations or [])}

    def add_iteration_to_team(self, team: str, identifier: str) -> bool:
        """把迭代添加到 team。已存在返回 False，新增成功返回 True。"""
        try:
            self._work_client.post_team_iteration(
                TeamSettingsIteration(id=identifier), self._team_context(team),
            )
            return True
        except (AzureDevOpsServiceError, AzureDevOpsClientRequestError) as exc:
            raw_message = getattr(exc, "message", None)
            message = raw_message if isinstance(raw_message, str) else str(exc)
            if "already" in message.lower():  # 已添加过，视为成功
                return False
            raise RuntimeError(f"添加迭代到 team 失败: {message}") from exc
