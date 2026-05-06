# GuanDan

当前仓库只收敛到一条主线：

1. 单局掼蛋核心规则引擎
2. AI 只读取 `observe()` 和 `legal_actions()`
3. AI 只返回 `action_id`
4. 规则真值全部由引擎维护

当前不接入 RAG、DeepSeek、多局比赛层、贡还层或升级层逻辑。

## 主接口

- `reset()`
- `observe()`
- `legal_actions()`
- `step(action_id)`

## 当前已覆盖的核心规则

- 4 人、1/3 一队、2/4 一队、双副牌、每人 27 张
- 级牌 `current_level_rank`
- 逢人配 = 红桃级牌
- 王类白名单：单王、王对子、天王炸
- 牌型：
  - `single`
  - `pair`
  - `triple`
  - `triple_with_pair`
  - `straight`
  - `pair_straight`
  - `steel_plate`
  - `bomb`
  - `straight_flush`
  - `joker_bomb`
- 同型压制
- 跨型压制层级：`joker_bomb > 6+ bomb > straight_flush > 5-bomb > 4-bomb`
- 接风
- 三游终局
- 胜负 / 平局判定

## 核心测试

```bash
d:/VsCodeProject/GuanDan/.venv/Scripts/python.exe -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q
```

## 调试运行

```bash
d:/VsCodeProject/GuanDan/.venv/Scripts/python.exe -m cli.run_4ai_debug --seed 7 --max-steps 12000
```

`run_4ai_debug` 默认输出中文人工审核视图，结构为：

- `发牌完成：`
- `玩家1手牌：【...】`
- `====第N轮====`
- `玩家X出牌：...`
- `玩家X剩余手牌：【...】`
- `====游戏结束====`
- `头游 / 二游 / 三游 / 末游`
- `队伍1（玩家1，玩家3）获胜` / `队伍2（玩家2，玩家4）获胜` / `本局平局`

默认不展开 `legal_actions`，只打印实际执行动作；若动作使用逢人配，会同时显示真实承载牌与声明说明。

## CLI 调试命令

运行本地 4 AI 自动对局，用于调试引擎规则和 AI 决策：

```bash
# 默认规则 AI 对局（随机发牌）
python -m cli.run_4ai_debug

# 固定发牌种子、限制最大步数（适合复现问题）
python -m cli.run_4ai_debug --seed 42 --max-steps 5000

# 使用 DeepSeek API 接入（需先配置 .env 文件）
python -m cli.run_4ai_debug --agent deepseek --seed 7 --max-steps 10

# 显示 DeepSeek 玩家 1 的思考过程
python -m cli.run_4ai_debug --agent deepseek --show-thinking --seed 7 --max-steps 10

# 静默模式，不输出思考过程（默认行为）
python -m cli.run_4ai_debug --agent deepseek --seed 7

# 设置级牌（默认 2）
python -m cli.run_4ai_debug --agent deepseek --seed 7 --current-level-rank 5
```

说明：`--agent` 可选 `rule`（默认）或 `deepseek`；`--seed` 固定发牌顺序；`--max-steps` 防止死循环；`--show-thinking` 仅在 `--agent deepseek` 时有效，控制是否输出玩家 1 的五段式思考过程（手牌摘要、局面、其他玩家、合法动作摘要、模型推理与选择），对其他模式无影响。DeepSeek 接入需在 `.env` 中配置 `DEEPSEEK_API_KEY`。

## 旧链路处理

旧比赛层、旧 RAG / DeepSeek 试验链路、旧评测与旧 CLI 已归档到 `archive_legacy/`，不再属于当前主链。
