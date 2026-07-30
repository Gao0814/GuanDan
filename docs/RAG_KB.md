# RAG 规则库与经验库规范

## 1. 定位

RAG 只提供受限知识上下文：

- 规则库解释当前项目规则；
- 经验库为已选策略意图提供参考；
- RAG 不判断合法性、不推进状态、不直接执行动作。

优先级固定为：

1. 规则引擎；
2. 原始 `legal_actions()`；
3. 本地公开局面分析和策略路由；
4. RAG 规则证据；
5. RAG 经验依据；
6. DeepSeek 在候选动作内选择。

## 2. 知识来源

当前正文来源仅限：

- `rag/rule_corpus/guandan_rules.md`
- `rag/experience_corpus/basic_human_experience.md`

规则、经验和当前代码口径必须一致。未实现能力不能通过知识库提前激活。

## 3. 条目格式

每条知识使用 front matter，至少包含：

```yaml
id:
corpus:
scene:
phase:
hand_strength:
action_context:
topic:
priority:
keywords_cn:
```

允许逐步增加：

```yaml
strategy_intent:
threat_source:
opponent_count_bucket:
teammate_count_bucket:
belief_confidence:
```

新增标签必须是 ASCII 枚举值，正文可以使用中文。

## 4. 统一阶段

RAG 不得自行重复计算阶段。阶段必须来自统一阶段分类器：

- `opening`
- `midgame`
- `endgame`
- `near_open_endgame`
- `critical_endgame`

旧条目使用 `endgame` 时，可以匹配更细的两个残局阶段；代码中必须显式处理这种父子关系。

## 5. 场景和策略意图

基础场景：

- `lead_opening`
- `lead`
- `follow_response`
- `endgame`

策略意图：

- `run_out`
- `control`
- `support_teammate`
- `block_opponent`
- `finish_now`

推荐流程是先由本地策略路由器选择 `strategy_intent`，再检索对应经验。RAG 不应仅凭文本相似度独立决定策略。

## 6. 规则库检索

规则库检索由当前桌面约束和候选动作触发，例如：

- 逢人配候选触发 `wildcard`；
- 炸弹、同花顺、天王炸触发 `bomb_hierarchy`；
- 跟牌且存在 pass 触发 `pass`；
- 接风或完赛状态触发 `receiving_lead / finish_order`。

规则证据只能解释规则，不能补造动作。

## 7. 经验库检索

经验库检索至少考虑：

- 统一阶段；
- 首出或跟牌；
- 手牌强弱；
- 队友和对手剩余张数；
- 当前策略意图；
- 是否存在炸弹、王、级牌和逢人配；
- 牌面信念置信度。

当信念置信度低时，经验正文必须使用保守措辞，不得把猜牌当作事实。

## 8. 牌面信念与 RAG

RAG 可以读取信念状态的摘要：

- 外部未知牌总数；
- 每位玩家的候选点数；
- 确定牌和高置信度牌；
- 候选分配数量；
- 推断置信度和证据类型。

RAG 不负责计算信念状态，也不能把 `likely` 提升为 `confirmed`。

## 9. 检索输出

每个 hit 至少包含：

- `source_id`
- `layer`
- `snippet`
- `source_path`
- `status`
- `score`
- 命中的标签

冲突条目必须标记为 rejected，不能进入模型的 accepted evidence。

规则证据和经验依据必须分开传入提示词。

## 10. 限制和降级

- 仅 pass 和一次出完场景应在 RAG 前本地结束；
- 公式化开局命中时可以跳过 RAG；
- 无匹配结果时返回空列表；
- 检索异常不能中断合法决策；
- RAG 上下文必须限制条目数和正文长度；
- API 不可用时回退本地规则 AI。

## 11. 质量验收

单元测试至少验证：

- 元数据解析；
- 阶段和场景匹配；
- 规则 / 经验分层；
- 冲突过滤；
- 空结果和异常降级；
- 提示词长度上限。

离线评测至少记录：

- 场景覆盖率；
- 正确条目 Top-1 / Top-3 命中率；
- rejected 冲突数；
- 平均命中条目数；
- 平均 RAG 字符数；
- 不同策略意图下的命中稳定性。

没有上述数据时，只能声明“检索已接入”，不能声明“策略效果已提升”。
