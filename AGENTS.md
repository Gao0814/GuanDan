# GuanDan — Agent Instructions

本仓库目标是**单局掼蛋核心规则引擎 + AI 决策层**的最小闭环。

- 项目入口与用法：见 [README.md](README.md)
- 规格与接口契约：见 [docs/SPEC.md](docs/SPEC.md)
- 变更边界（禁止越界扩展）：见 [docs/CODING_BOUNDARY.md](docs/CODING_BOUNDARY.md)
- 长期不变量（必须始终成立）：见 [docs/INVARIANTS.md](docs/INVARIANTS.md)

## 快速指南（给 AI 编码代理）

- **目标摘要**：引擎逻辑位于 `engine/`，AI 决策位于 `agents/`。若仅修改决策逻辑，只编辑 `agents/`，不要改 `engine/`。
- **契约与格式**：观察（`observe()`）与动作（`legal_actions()`）的精确结构见 [CLAUDE.md](CLAUDE.md) 和 [docs/SPEC.md](docs/SPEC.md)。代理只能基于这些公开 payload 返回 `action_id`。
- **运行与测试**：主回归与运行命令见下节“常用命令”。修改 `engine/` 时请运行主回归以保证不破坏规则实现。
- **行为约束**：不要引用或序列化引擎内部对象；不要构造未由 `legal_actions()` 给出的动作；不要在 AI 层做合法性判断。
- **变更说明**：在 PR 描述中说明为何需要修改 `engine/`（仅在确实必要时），并指明你已运行过哪些测试。

## 1) 最重要的架构边界

- **引擎（engine/）是规则真值**：牌型识别、合法动作生成、比较、状态推进、终局判定都在引擎里完成。
- **AI（agents/）只做选择**：只能基于 `observe()` + `legal_actions()` 的公开 payload，返回一个 `action_id`。
- **严禁**让 AI 触碰引擎内部状态对象、自己做合法性判断、或构造“引擎未给出的动作”。

更详细的两层分工与文件导览见 [CLAUDE.md](CLAUDE.md)。

## 2) 常用命令（回归与复现）

```bash
# 主回归（推荐）
python -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q

# 运行 4 AI 自博弈回放（默认规则 AI）
python -m cli.run_4ai_debug --seed 7

# DeepSeek（需要 .env 里的 DEEPSEEK_API_KEY）
python -m cli.run_4ai_debug --agent deepseek --seed 7

# 仅 DeepSeek 模式：显示玩家 1 的思考过程
python -m cli.run_4ai_debug --agent deepseek --show-thinking --seed 7 --max-stepTraceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "D:\VsCodeProject\GuanDan\cli\run_4ai_debug.py", line 300, in <module>
    raise SystemExit(main())
                     ^^^^^^
  File "D:\VsCodeProject\GuanDan\cli\run_4ai_debug.py", line 291, in main
    return _print_human_replay(
           ^^^^^^^^^^^^^^^^^^^^
  File "D:\VsCodeProject\GuanDan\cli\run_4ai_debug.py", line 213, in _print_human_replay
    chosen_action_id = agent.select_action(observation, legal_actions)
                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\VsCodeProject\GuanDan\agents\deepseek_ai.py", line 471, in select_action
    summary_lines = DeepSeekClient._grouped_legal_actions_summary(
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: DeepSeekClient._grouped_legal_actions_summary() missing 1 required positional argument: 'current_level_rank'30
```

## 3) 修改指引（按目标选改动点）

- **只想改 AI 决策**：只改 `agents/`，不要改 `engine/`。
- **规则/合法性/比较/状态推进有 bug**：改 `engine/`，并跑“主回归”测试集合。
- **CLI 中文回放格式变了**：改 `cli/`，并跑 `tests.test_cli_debug_output`（以及主回归）。
- `archive_legacy/` 为历史链路，默认不改动（除非任务明确要求）。

## 4) 关键契约（不要破坏）

- `observe()`：固定 5 个信息块结构；不得直接暴露引擎内部对象（详见 [docs/SPEC.md](docs/SPEC.md)）。
- `legal_actions()`：返回显式展开后的 canonical action 列表；动作需可审计、可复现（详见 [docs/INVARIANTS.md](docs/INVARIANTS.md)）。
- `step(action_id)`：只接受“当前合法动作集合中的” `action_id`。

## 5) 配置与密钥

- 统一从 [config.py](config.py) 读取环境变量；不要在代码中硬编码 API Key/URL。
- 本地密钥放在 `.env`（不提交）；模板见 `.env.example`。
