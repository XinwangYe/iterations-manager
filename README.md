# iterations-manager

**English** | [中文](#中文说明)

Batch-generate and manage Azure DevOps project iterations (sprints) from a single
YAML configuration file:

- Automatically creates two-week iteration classification nodes under the project's
  Iterations tree, based on release definitions;
- Auto-creates missing location directory nodes (multi-level paths supported);
- Adds the generated iterations to a team's iteration configuration, optionally
  restricted to a given range.

All operations are idempotent: re-running only aligns dates or skips iterations that
already exist.

## Naming & Date Rules

- Iteration name format: `Sprint YYYY.Rx.y`
  - `YYYY`: naming year, which must be explicitly specified in the config (global
    `iterations.year`, or overridden per release via `year`). It is never derived
    from the sprint start date, because the first release may start in December of
    the previous year.
  - `x`: release number, starting from 1 in order of appearance in the config.
  - `y`: sprint number within the release.
- Each sprint lasts exactly two weeks: from the Monday of week 1 to the Friday of
  week 2.
- For a release with `cool_down: true`, the first sprint is a Cool down sprint and
  numbering starts at **0** (`Sprint 2026.R1.0`, `Sprint 2026.R1.1`, ...);
  otherwise numbering starts at **1**.

## Requirements

- Python 3.10+
- A Personal Access Token (PAT) for your Azure DevOps organization

## Installation

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Configuration

Copy and edit the example:

```powershell
Copy-Item config.example.yml config.yml
```

See [config.example.yml](config.example.yml) for the full example:

```yaml
azure:
  organization: my-org        # the <organization> part of dev.azure.com/<organization>
  project: MyProject          # project name
  pat_env: AZDO_PAT           # env var holding the Personal Access Token (default AZDO_PAT)
  # pat: <token>              # PAT can also be written inline (not recommended)

iterations:
  location: "MyIterations"    # path under the Iterations node, "/" separated levels,
                              # auto-created; empty = directly under the Iterations root
  year: 2026                  # naming year (can be overridden per release via year)

  releases:                   # numbered R1, R2, ... in order of appearance
    - start_date: 2026-01-05  # release start date, must be a Monday
      cool_down: true         # first sprint is a Cool down sprint, numbering starts at 0
      sprints: 5              # total sprint count (incl. cool down); if omitted, derived
                              # from the next release's start date (gap must be a multiple of 14 days)

    - start_date: 2026-03-16
      cool_down: false        # numbering starts at 1
      sprints: 6

team:
  name: MyTeam                # team to add iterations to; omit to skip team configuration
  range:                      # optional: only add iterations in this inclusive range;
    from: R1.0                # omit to add all
    to: R2.6
```

### PAT

Prefer providing the PAT via an environment variable (the variable name can be
changed with `azure.pat_env`, default `AZDO_PAT`):

```powershell
$env:AZDO_PAT = "<your-personal-access-token>"
```

The PAT needs permission to manage project iterations (Work Item Tracking read &
write + Work read & write; the simplest option is a token with Project Administrator
scope).

## Usage

Preview first, then execute once everything looks right:

```powershell
# preview only, no API calls
python manage_iterations.py -c config.yml --dry-run

# actually execute
python manage_iterations.py -c config.yml
```

Module-style invocation (equivalent):

```powershell
python -m iterations_manager -c config.yml [--dry-run]
```

`-c/--config` defaults to `config.yml` in the current directory.

Example dry-run output:

```text
[定义] 共 11 个迭代，location: MyIterations
  Sprint 2026.R1.0         2026-01-05 ~ 2026-01-16 (Cool down)
  Sprint 2026.R1.1         2026-01-19 ~ 2026-01-30
  ...
[Team] MyTeam 将添加 11 个迭代，范围: R1.0 ~ R2.6
```

During execution, each iteration's status is printed: `created` (new node),
`updated` (dates mismatched and aligned), `unchanged`; the team step prints
`added` / `exists`.

## Project Structure

```
iterations_manager/
├── models.py    data models and business constants (sprint length, Release / Sprint)
├── config.py    YAML config loading and field validation
├── planner.py   plan building (release parsing / sprint generation / team range filter)
├── client.py    Azure DevOps client (based on the official azure-devops SDK)
└── cli.py       CLI entry point, plan preview and execution
manage_iterations.py     entry script (equivalent to python -m iterations_manager)
config.example.yml       example configuration file
```

## Dependencies

- [azure-devops](https://pypi.org/project/azure-devops/) — official Azure DevOps Python SDK
- [PyYAML](https://pypi.org/project/PyYAML/) — YAML configuration parsing

---

# 中文说明

[English](#iterations-manager) | **中文**

通过一个 YAML 配置文件，批量生成并管理 Azure DevOps 项目的 iterations（Sprint）：

- 按 release 定义自动生成两周一个的迭代节点（classification nodes），写入项目
  Iterations 分类树；
- 自动创建缺失的 location 目录节点（支持多级路径）；
- 把生成的迭代按可选范围添加到指定 team 的迭代配置中。

所有操作幂等：重复运行只会对齐日期或跳过已存在的迭代。

## 命名与日期规则

- 迭代命名格式：`Sprint YYYY.Rx.y`
  - `YYYY`：命名年份，必须在配置中显式指定（全局 `iterations.year`，或每个 release
    单独用 `year` 覆盖）。不取 sprint 起始日期的年份，因为第一个 release 可能从上一年
    12 月开始。
  - `x`：release 编号，按配置中出现顺序从 1 开始。
  - `y`：release 内的 sprint 编号。
- 每个 sprint 固定两周：从第一周周一开始，到第二周周五结束。
- `cool_down: true` 的 release，第一个 sprint 为 Cool down sprint，编号从 **0**
  开始（`Sprint 2026.R1.0`, `Sprint 2026.R1.1`, ...）；否则编号从 **1** 开始。

## 环境要求

- Python 3.10+
- Azure DevOps 组织的一个 Personal Access Token (PAT)

## 安装

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 配置

复制示例并修改：

```powershell
Copy-Item config.example.yml config.yml
```

完整示例见 [config.example.yml](config.example.yml)：

```yaml
azure:
  organization: my-org        # dev.azure.com/<organization> 中的部分
  project: MyProject          # 项目名
  pat_env: AZDO_PAT           # 从哪个环境变量读取 PAT (默认 AZDO_PAT)
  # pat: <token>              # 也可直接写 PAT (不推荐, 避免泄露/误提交)

iterations:
  location: "MyIterations"    # Iterations 节点下的路径, "/" 分隔多级, 自动创建;
                              # 留空则放在 Iterations 根节点下
  year: 2026                  # 迭代命名使用的年份 (也可在每个 release 中用 year 覆盖)

  releases:                   # 按出现顺序依次编号 R1, R2, ...
    - start_date: 2026-01-05  # release 开始日期, 必须是周一
      cool_down: true         # 第一个 sprint 为 Cool down sprint, 编号从 0 开始
      sprints: 5              # sprint 总数 (含 cool down); 省略时按下一个 release
                              # 的开始日期推算 (间隔必须是 14 天的整数倍)

    - start_date: 2026-03-16
      cool_down: false        # 编号从 1 开始
      sprints: 6

team:
  name: MyTeam                # 要添加迭代的 team; 省略则跳过 team 配置
  range:                      # 可选: 只添加闭区间内的迭代, 省略则添加全部
    from: R1.0
    to: R2.6
```

### PAT

优先通过环境变量提供（变量名可用 `azure.pat_env` 修改，默认 `AZDO_PAT`）：

```powershell
$env:AZDO_PAT = "<your-personal-access-token>"
```

PAT 需要具备管理项目迭代的能力（Work Item Tracking 读写 + Work 读写；
最简单的方式是使用 Project Administrator 范围的 token）。

## 使用

先预览，确认无误再执行：

```powershell
# 仅预览生成结果, 不调用 API
python manage_iterations.py -c config.yml --dry-run

# 实际执行
python manage_iterations.py -c config.yml
```

也可以用模块方式运行（等价）：

```powershell
python -m iterations_manager -c config.yml [--dry-run]
```

`-c/--config` 默认值为当前目录下的 `config.yml`。

dry-run 输出示例：

```text
[定义] 共 11 个迭代，location: MyIterations
  Sprint 2026.R1.0         2026-01-05 ~ 2026-01-16 (Cool down)
  Sprint 2026.R1.1         2026-01-19 ~ 2026-01-30
  ...
[Team] MyTeam 将添加 11 个迭代，范围: R1.0 ~ R2.6
```

执行时每个迭代的状态会逐条打印：`created`（新建）、`updated`（日期不一致，已对齐）、
`unchanged`（无需变更）；team 添加阶段则打印 `added` / `exists`。

## 项目结构

```
iterations_manager/
├── models.py    数据模型与业务常量 (sprint 时长、Release / Sprint)
├── config.py    YAML 配置加载与字段校验
├── planner.py   执行计划构建 (release 解析 / sprint 生成 / team 范围过滤)
├── client.py    Azure DevOps 客户端 (基于官方 azure-devops SDK)
└── cli.py       命令行入口、计划预览与执行
manage_iterations.py     入口脚本 (等价于 python -m iterations_manager)
config.example.yml       配置文件示例
```

## 依赖

- [azure-devops](https://pypi.org/project/azure-devops/) —— Azure DevOps 官方 Python SDK
- [PyYAML](https://pypi.org/project/PyYAML/) —— YAML 配置解析
