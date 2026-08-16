# -*- coding: utf-8 -*-
"""YAML 配置文件加载与字段校验工具。"""

from __future__ import annotations

import re
from datetime import date, datetime

import yaml

SPRINT_REF_RE = re.compile(r"^R(\d+)\.(\d+)$")


class ConfigError(Exception):
    """配置文件错误。"""


def load_config(path: str) -> dict:
    """读取并解析 YAML 配置文件，根节点必须是映射。"""
    try:
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    except FileNotFoundError:
        raise ConfigError(f"配置文件不存在: {path}")
    except yaml.YAMLError as exc:
        raise ConfigError(f"配置文件解析失败: {exc}")
    if not isinstance(cfg, dict):
        raise ConfigError("配置文件根节点必须是映射")
    return cfg


def to_date(value: object, field_name: str) -> date:
    """把配置值转换为 date，支持 date/datetime/ISO 字符串。"""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError as exc:
            raise ConfigError(f"{field_name} 日期格式非法: {value!r}，应为 YYYY-MM-DD") from exc
    raise ConfigError(f"{field_name} 缺失或不是日期")


def to_year(value: object, field_name: str) -> int:
    """把配置值转换为合法年份整数。"""
    if isinstance(value, (bool, dict, list)):
        raise ConfigError(f"{field_name} 必须是年份整数，例如 2026")
    try:
        year = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{field_name} 必须是年份整数，例如 2026") from exc
    if not 1900 <= year <= 9999:
        raise ConfigError(f"{field_name} 超出合理年份范围: {year}")
    return year


def parse_sprint_ref(text: object, field_name: str) -> tuple[int, int]:
    """解析 'Rx.y' 形式的迭代引用，返回 (x, y)。"""
    if not isinstance(text, str):
        raise ConfigError(
            f"{field_name} 非法: 应为 Rx.y 形式的字符串，例如 R1.0，"
            f"实际为 {type(text).__name__} 类型"
        )
    match = SPRINT_REF_RE.match(text.strip())
    if not match:
        raise ConfigError(f"{field_name} 非法: {text!r}，应为 Rx.y 形式，例如 R1.0")
    return int(match.group(1)), int(match.group(2))
