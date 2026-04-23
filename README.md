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

## 旧链路处理

旧比赛层、旧 RAG / DeepSeek 试验链路、旧评测与旧 CLI 已归档到 `archive_legacy/`，不再属于当前主链。
