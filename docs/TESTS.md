# GuanDan 测试说明

本文档描述当前单局核心规则主线的测试入口与验收口径。  
当前测试范围只围绕：

- 单局核心规则
- AI 只在合法动作集合中选择 `action_id`
- 中文人工审核版 CLI 回放输出

不再以旧比赛层、贡还层、多局层、RAG / DeepSeek 试验链路为主测试目标。

## 1. 推荐测试入口

主测试集合：

```bash
python -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q
```

说明：

- `tests.test_patterns`：牌型识别与边界
- `tests.test_rules`：合法动作生成、压制比较、逢人配声明语义
- `tests.test_game_flow`：接口契约、接风、三游终局、平局判定、CLI 烟测
- `tests.test_cli_debug_output`：中文牌面、中文动作、轮次回放、终局摘要格式

历史测试已归档到 `archive_legacy/tests/`，当前不建议纳入主回归。

## 2. 当前必须覆盖的核心测试点

### 2.1 牌型与规则

- 王类白名单与非法王类组合
- 顺子 / 连对 / 钢板 / 同花顺边界
- 三带二严格 `3 + 2`
- 逢人配只能参与非王类牌型，且一手最多 1 张
- 合法动作必须是显式展开后的 canonical action
- 比较按 `declared_cards`
- 扣牌按 `carrier_cards`

### 2.2 状态推进

- 接风只按仍在局中的玩家判断
- 已出完牌玩家退出轮转
- 三游出现立即终局
- 末游自动确定
- 头游队友为末游时判平局，否则头游队获胜

### 2.3 接口契约

- `reset()` 能正确初始化单局
- `observe()` 返回固定 5 个信息块
- `legal_actions()` 返回稳定、可审计的动作列表
- `step(action_id)` 只接受当前合法动作 ID，并正确推进状态

### 2.4 CLI 中文人工审核输出

`cli/run_4ai_debug.py` 的默认输出契约为中文人工审核视图，而不是旧的字段式调试打印。

至少应覆盖：

- `发牌完成：`
- `玩家X手牌：【...】`
- `====第N轮====`
- `玩家X出牌：...`
- `pass`
- `玩家X剩余手牌：【...】`
- `====游戏结束====`
- `头游 / 二游 / 三游 / 末游`
- `队伍1（玩家1，玩家3）获胜` / `队伍2（玩家2，玩家4）获胜` / `本局平局`

同时应验证：

- 普通牌显示为 `♠/♥/♣/♦`
- `SJ / BJ` 显示为 `小王 / 大王`
- 手牌按点数从大到小展示
- 动作中文名正确：`对A`、`顺子`、`连对`、`钢板`、`4炸/5炸`、`同花顺`、`天王炸`
- 逢人配动作会同时显示真实承载牌与声明说明
- 默认不展开 `legal_actions`

## 3. 当前明确不作为主测试目标的内容

- 多局升级赛完整规则
- 打到 A 的长期比赛结算
- 复杂贡还 / 抗贡比赛制
- RAG / DeepSeek 主链接入
- 训练链路、强化学习、自博弈、MCTS

## 4. 验收标准

当前阶段可视为通过的最低标准：

1. `tests.test_patterns` 通过
2. `tests.test_rules` 通过
3. `tests.test_game_flow` 通过
4. `tests.test_cli_debug_output` 通过
5. `observe()` / `legal_actions()` / `step()` 契约稳定
6. CLI 默认输出符合中文人工审核口径
