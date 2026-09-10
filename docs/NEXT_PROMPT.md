# 给执行 Codex 的下一任务 Prompt

只读审计seed `47003`的全部10条已确认decision trace，以及当前DeepSeek成功动作路径中的三个确定性策略后置守卫。目标是判断是否存在下一个应优先迁移到prompt/router/RAG的高置信度公开上下文缺口；本任务不修改代码，也不调用模型。

## 【开始前】

1. 阅读并遵守`AGENTS.md`，检查适用项目Skills；本任务不使用live或workspace-cleanup Skill。
2. 阅读`docs/CLEAN_HANDOFF.md`及DeepSeek、strategy router/intent、RAG和三个后置守卫相关代码与测试。检查Git状态必须clean，确认HEAD包含`454a422`。
3. 只读核对`D:\VsCodeProject\BotzoneWorkspace\decision-trace.json`仍为88,983 bytes、SHA-256 `4ba2ea88a13046f8f7907df6dd124175dceee3a88e9723be88c6581a28bc3512`，schema、binding、顺序及10条记录结构有效。仅在内存分析，不修改任何workspace artifact。

## 【已确认事实】

- 受约束执行报告将第9条固定决策的真实DeepSeek off/on复放判定为`strategy_intent_target_decision_improved`：off=`special`、on=`pass`；on侧为`ready / support_teammate / teammate_controls_table`，两侧动作均合法，总请求2、重试0。规划Codex已独立复核trace与Git未变；模型响应按隐私契约未持久化。
- 该结果只证明补全队友控桌语义改善了这个目标决策，不证明整体胜率。
- DeepSeek是合法动作空间内的主要策略决策者。不得因为模型与RuleBased偏好不同就把RuleBased动作新增为成功模型动作的后置覆盖。
- 当前成功模型动作路径仍存在`danger_opponent_block`、`teammate_control_block`和`short_endgame_plan`三个确定性策略后置守卫；本任务只审计，不删除或扩大它们。

## 【审计任务】

1. 对10条trace逐条使用当前生产代码生成低敏分类：自由/跟随队友/跟随对手、strategy intent状态与类别、RAG scene/action-context标签、记录动作类别，以及三个后置守卫各自是否具备触发前提。不得输出手牌、牌面、action ID、完整observation/legal actions、prompt或模型文本。
2. 对三个后置守卫分别确认：
   - 它解决的公开策略语义是什么；
   - 当前router/intent prompt/RAG是否已经明确向模型表达该语义；
   - 它是合法性/协议安全守卫，还是会改写一个已经合法且成功的模型策略动作；
   - seed `47003` trace中是否存在完整、可复现的相关决策证据。
3. 只在同时满足以下条件时提出一个后续实现候选：
   - 输入来自完整ACK trace和公开字段；
   - 当前prompt/router/RAG确实遗漏或弱化了与动作选择直接相关的公开语义；
   - 能以当前代码稳定复现该信息缺口；
   - 修复方向是让DeepSeek获得更好的策略上下文，而不是用RuleBased替换成功模型动作；
   - 能定义最小单元测试与至多两个真实模型请求的后续验证。
4. 如果没有候选同时满足上述条件，明确判定证据不足，不得根据单局输赢、与RuleBased不同或主观牌感制造新规则。

## 【禁止事项】

- 不访问网络、DeepSeek、Botzone或Edge；不启动connector/preflight/live/容量评测。
- 不读取`.env`，不修改代码、tests、docs、配置或workspace；不创建报告文件或Git commit。

## 【完成标准与报告】

唯一判定只能是：

- `seed_47003_next_prompt_candidate_identified`；或
- `seed_47003_no_additional_high_confidence_candidate`。

最终报告需包含：10条决策的低敏分类聚合；三个后置守卫的策略/安全性质与当前prompt覆盖结论；如有候选，给出唯一候选的缺失上下文、稳定复现、建议修改范围和最小验证；如无候选，说明证据边界。最后报告artifact前后bytes/SHA-256、Git HEAD/status，以及网络/模型/Botzone调用均为0。不得输出任何敏感正文。
