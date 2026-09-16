# Coding Codex 执行 Prompt

这是 H3-A1.1：修复 strategy recommendation、prompt shortlist 与最终模型候选的原始 ID 闭环。不要依赖其他对话的隐含上下文，请从当前仓库重新建立事实。

本任务只修改与该闭环直接相关的 AI 生产代码和 tests；不修改 `engine/`、RAG corpus/provenance、docs、Botzone 协议/connector、配置或仓库外 evidence。不得发起真实 DeepSeek 请求，不运行 Botzone、live、browser、connector 或 preflight，不读取或改写 seed `47004` evidence。

## 开始前

1. 阅读并遵守根目录及适用范围内的 `AGENTS.md`，检查 `.agents/skills/`。本任务不是 Botzone live 或 workspace 清理，不执行两个项目 Skill。
2. 阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/STRATEGY_SOURCE_AUDIT.md`、`docs/RAG_KB.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`。
3. 检查 Git status、HEAD 和最近提交。HEAD 必须包含 `caa1cc09e91ea8ad9a56e8eefacee21cb10a24e2`，工作树必须 clean；否则失败即停并报告，不处理外部修改。
4. 阅读完整调用链和相关测试，至少包括：
   - `agents/deepseek_ai.py`
   - `agents/deepseek_client.py`
   - `agents/strategy_recommendation.py`
   - `agents/action_structure.py`
   - `agents/rag_advisor.py`
   - `tests/test_action_pruning.py`
   - `tests/test_action_structure.py`
   - `tests/test_strategy_recommendation.py`
   - `tests/test_h3_a1_projection.py`
5. 先独立复现：recommendation 从完整 canonical `legal_actions` 生成，但第一层 `_prune_legal_actions()` 和最终 `_limit_prompt_actions()` 未保护 recommendation ID；最终 `_validated_strategy_recommendation()` 发现任一 ID 不在 prompt candidates 时返回 `None`，连同策略域、目标和反例一起不进入 prompt。不得把该问题归因于模型或用放宽 H3-A2 marker 绕过。

## 实现目标

建立一个确定、可测试、fail-closed 的模型前候选闭环：

1. recommendation 的公开结构、策略域、目标和反例仍从完整、严格 canonical 的原始 `legal_actions` 派生，不得先用剪枝子集改变局面判断。
2. recommendation 中最多 3 个合法原始 `action_id` 必须在第一层剪枝和最终 prompt 硬预算中获得确定性保护，并实际出现在模型可选候选中；不得改写 ID、生成新动作或用语义相似但未登记的另一个 ID 暗中替换。
3. 最终传给模型、用于 recommendation 校验、展示在 `【候选动作】`、用于响应允许集合的必须是同一个有界 canonical 子集。输出的 recommendation action IDs 必须全部属于该集合。
4. 最终候选继续严格 `<= 80`、按签名唯一、保持稳定顺序且全部来自原始 `legal_actions`。为最多 3 个推荐项腾出预算时只能在既有有界优先级内确定性取舍，不能提高上限。
5. H3-A0a 契约不得回归：自由首出仍保留代表性 natural single 与最小 natural pair；跟牌仍保留 pass；finishing、pressure、wildcard、ordinary 的有界优先级及四/五炸关系可见性保持。
6. recommendation payload 若类型、source、枚举、顺序、ID、canonical 归属或预算畸形，继续 fail closed；不得把外部自由文本、非 canonical ID 或伪 action 注入候选。
7. 合法 recommendation 没有 action shortlist 时，策略域、目标和反例仍可按既有 ready 契约进入 prompt；不能为了修 ID 守恒而把知识投影错误绑定为必须存在 shortlist。
8. RAG 继续只消费允许的语义字段；provenance 作者、机构、书目、URL、来源等级和激活状态不得进入检索评分、冲突扫描或模型 prompt。
9. DeepSeek 成功返回最终候选内合法原始 ID 后必须原样返回并记录 `model`。不得新增或恢复任何模型后策略覆盖、selector、guard 或 legacy decision source。

实现方式由你根据现有结构选择，但不得只在 `_validated_strategy_recommendation()` 中静默删除缺席 ID 来伪造闭环：如果完整 recommendation 明确推荐了合法候选，生产 shortlist 应在预算内真正保留它。也不得只修 `_build_structured_prompt()` 的第二层，因为 recommendation ID 可能已被第一层剪枝删除。

## 必须补充的回归

1. 用真实 `GuanDanGame.observe()` 与完整 `legal_actions()` 构造 engine-backed 自由首出大候选场景，证明：完整 recommendation 为 ready；它的全部推荐 ID 进入最终 `<=80` 候选；`【模型前建议】`、策略域、目标和反例均进入最终 prompt。
2. 至少覆盖此前 H3-A2 被阻断的五类关系：
   - 低成本自然单张试探；
   - natural pair 与 single 清理；
   - 中性 pair/triple 的可撤回 soft hypothesis；
   - 短残局最少分组；
   - 炸弹/通配资源管理。
   fixture 必须来自引擎公开 `observe()` 与完整 canonical `legal_actions()`，不得手写伪合法动作、删除合法候选或硬编码现场 action ID。
3. 覆盖推荐项与既有 finishing/pressure/wildcard/ordinary 溢出竞争的场景，证明硬上限、稳定顺序、签名唯一和代表性保留同时成立。
4. 覆盖 standalone `DeepSeekClient.suggest_action_id()` 与 `DeepSeekAIAgent.select_action()` 两条生产入口，证明二者使用同一最终候选/推荐闭环；fake client 返回任一最终合法 ID 时 ID 与 `model` source 保真。
5. 保留并扩展畸形 recommendation/canonical 反例：非原始 ID、重复 ID、超 3 项、未知枚举、错误顺序或与候选不守恒时必须 fail closed，且不能扩大候选集合。
6. 加一个多 seed 真实引擎性质测试或等价离线探针，至少验证：最终数 `<=80`、推荐 IDs 是最终 IDs 子集、最终 IDs 是原始 IDs 子集、签名唯一、重复运行结果稳定。测试不得依赖 seed `47004`。

## 验证

1. 先运行新增和直接相关测试。
2. 运行 H3/DeepSeek/RAG/Botzone observability 相关回归，至少覆盖 action pruning、action structure、strategy recommendation、H3-A1 projection、DeepSeek prompt/agent、strategy router/intent、RAG provenance/投影和 Botzone adapter/observability/decision trace。
3. 运行主规则回归：

```powershell
python -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q
```

4. 运行全量：

```powershell
python -m unittest discover -q
```

5. 运行 `git diff --check`，并做生产扫描，确认：
   - 无 seed `47004`、Q/4/10 或某组点数/action ID 特判；
   - 无新模型后策略覆盖或 legacy source 主动分支；
   - provenance 治理字段未进入模型输入；
   - H3-A0a 最终预算常量未提高。

## 提交与报告

1. 只提交本任务的业务代码和 tests，使用单一清晰 commit；不得修改或提交 docs、`.env`、配置、日志、workspace evidence 或其他外部修改。
2. 报告根因、数据流修复方式、修改文件、关键测试/性质检查结果、commit hash 和最终 Git status。
3. 明确报告真实 DeepSeek 请求、重试、Botzone/live/connector/browser/preflight 均为 0，seed `47004` workspace evidence 未触碰。
4. 不声称策略收益、胜率提升或 H3-A2 已完成；H3-A2 必须在规划 Codex 复审本提交后，从原八场完整离线资格检查重新开始。
