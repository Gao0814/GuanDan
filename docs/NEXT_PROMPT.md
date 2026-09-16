# Coding Codex 执行 Prompt

这是 H3-A1.1a：修复 `ba449f5` 后仍存在的 strategy recommendation builder/validator 预算漂移。不要依赖其他对话的隐含上下文，请从当前仓库重新建立事实。

本任务只做纯离线最小纠错，修改直接相关的 AI 生产代码和 tests；不修改 `engine/`、RAG corpus/provenance、docs、Botzone 协议/connector、配置或仓库外 evidence。不得发起真实 DeepSeek 请求，不运行 Botzone、live、browser、connector 或 preflight，不读取或改写 seed `47004` evidence。

## 开始前

1. 阅读并遵守根目录及适用范围内的 `AGENTS.md`，检查 `.agents/skills/`；本任务不执行两个 Botzone 项目 Skill。
2. 阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/STRATEGY_SOURCE_AUDIT.md`、`docs/RAG_KB.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`。
3. 检查 Git status、HEAD 和最近提交。HEAD 必须包含 `ba449f5d173a4e2a4da8d6aa1c98f4ab0e3c7f27`，工作树必须 clean；否则失败即停，不处理外部修改。
4. 阅读 `ba449f5` 完整 diff、`agents/strategy_recommendation.py`、`agents/deepseek_client.py`、`agents/deepseek_ai.py` 和全部相关测试。保留该提交已经正确建立的 recommendation-ID 两层保护、最终80项上限及 prompt-candidate 响应边界。

## 必须先复现的反例

使用真实 `GuanDanGame.observe()` 和完整 canonical `legal_actions()`，由确定性本地合法动作推进整局，而不是手写 observation/action：

- 某些后续自由领牌状态同时触发 structure、probe、control、teammate、danger/endgame 等目标；`build_strategy_recommendation()` 返回 `status="ready"`，但 `objective_codes` 数量为5。
- `_validated_strategy_recommendation()` 固定只接受最多4项，因此拒绝该生产 payload。
- recommendation ID 不获得保护；最终候选缺少部分推荐原始ID，`【模型前建议】`不进入 prompt。

规划复审在40局/3379状态中稳定发现4个此类状态。不得只复现初始局面，也不得以现有测试全绿否认该反例。

## 实现要求

1. 为 recommendation 的 objective 预算建立单一生产真值；builder、validator 和 prompt formatter 不得各自维护会漂移的隐含上限。
2. 保持现有最多4个 objective 的有界输入契约；不得简单提高或删除上限来绕过失败。
3. 当公开局面同时命中超过4个目标时，builder 必须以稳定、显式、可测试的优先级选出至多4项。公开紧急目标（例如立即出完、危险对手阻断、明确残局或队友协同）不得被普通低成本试探或泛化资源管理无理由挤出；优先级只影响模型前目标展示，不选择动作。
4. 每个由生产 `build_strategy_recommendation()` 返回的 `ready` payload，必须能被 `_validated_strategy_recommendation(payload, 同一完整canonical actions)` 接受。若输入证据/canonical本身无效则继续返回 `unavailable`，不得伪造可用 payload。
5. 通过校验的 recommendation action IDs 必须继续全部进入同一个最终 `<=80` prompt candidate 集合；最终 IDs 是原始 IDs 子集、签名唯一、顺序稳定，模型响应只接受实际 prompt candidates。
6. 保留无 shortlist 的合法 ready recommendation 语义；不得把 objective 修复误改为必须存在 action IDs。
7. 外部或畸形 payload 的 type/source/ID/枚举/顺序/预算/canonical 校验继续 fail closed；不得静默截断不可信调用方 payload。只有项目自己的 builder 在构造时执行确定预算选择。
8. 不改变 RAG corpus、来源等级、provenance 隔离、router/intent、opening shortcut、H3-A0a 候选优先级或 DeepSeek 成功 ID/`model` source 保真；不得新增模型后覆盖或 legacy source 主动分支。

## 必须补充的回归

1. 对可同时产生5个原始目标的 engine-backed 后续状态建立回归，证明 builder 最终输出至多4项、validator 接受、公开紧急目标按明确优先级保留、全部 recommendation IDs 位于最终候选且 prompt 包含策略域/目标/反例区块。
2. 加入真实整局全状态性质测试或等价离线探针，覆盖不少于40个非 `47004` seed；每个状态都验证：
   - 生产 recommendation 为 `ready` 时自校验通过；
   - objective 数量在预算内；
   - recommendation IDs 是最终 IDs 子集；
   - 最终数 `<=80`，最终 IDs 是原始 IDs 子集，签名唯一；
   - 相同输入重复运行结果稳定。
3. 保留 `ba449f5` 的大候选、五类关系、standalone Client、Agent、overflow 竞争、畸形 payload 和未展示模型 ID 拒绝回归。
4. 新增边界测试证明：外部构造的5项 objective payload仍被 validator拒绝；生产 builder 则在进入 validator 前按确定优先级收敛到预算内。不得让 validator 暗中截断。

## 验证

1. 运行新增和直接相关测试。
2. 运行 H3/DeepSeek/RAG/Botzone observability 相关回归，至少覆盖 action pruning、action structure、strategy recommendation、candidate closure、H3-A1 projection、DeepSeek prompt/agent、strategy router/intent、RAG provenance/投影及 Botzone adapter/observability/decision trace。
3. 运行主规则回归：

```powershell
python -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q
```

4. 运行全量：

```powershell
python -m unittest discover -q
```

5. 运行 `git diff --check`，扫描确认没有 seed `47004`/现场牌面/固定 action ID 生产特判，没有新模型后覆盖或 legacy source 主动分支，provenance 治理字段未进入模型输入，候选上限仍为80。

## 提交与报告

1. 只提交本任务直接相关的业务代码和 tests，使用一个清晰 commit；不得修改或提交 docs、`.env`、配置、日志、workspace evidence 或其他外部修改。
2. 报告反例、统一预算与优先级设计、修改文件、整局全状态性质结果、测试结果、commit hash 和最终 Git status。
3. 明确报告真实 DeepSeek 请求、重试、Botzone/live/connector/browser/preflight 均为0，seed `47004` evidence 未触碰。
4. 不声称 H3-A2 已完成、策略收益或胜率提升；纠错提交仍需规划 Codex 独立复审，之后才可恢复原八场 H3-A2 资格检查。
