# Coding Codex 执行 Prompt：离线修复 M2 扩大评估请求绑定

> 起点：`99d31b0fbc0529d18e6aca15518cce084b7b76bc`。上一轮获批的 32 槽在第 1 槽成功发送后按 `attempt_offline_binding_mismatch_stopped` 停止：本轮实际请求 1、重试 0、余下 31 槽未执行。**本任务真实 DeepSeek 请求上限为 0。不得延续旧授权、重试第 1 槽或执行其余槽。** 修复交回规划复审后，新的完整评估才另定预算并申请明确授权。

## 目标与边界

修复评测器把离线占位模型名与真实配置模型名造成的 Request 差异误判为策略/状态漂移的问题，同时保持对实际模型配置、请求正文、公开状态、合法候选和推荐闭环的严格绑定。原第 1 槽未记录具体不匹配字段；`request_utf8_bytes` 是已用禁网合成输入复现的缺口，不能把它未经核实写成唯一现场根因。提供固定低敏字段分类，使下次停止能定位差异而不泄露请求、prompt、凭据或异常正文。

先读适用 `AGENTS.md`、项目 Skills 清单、`README.md`、`CLAUDE.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、[扩大评测器](../evaluation/m2_expanded_same_state_eval.py)、[首轮评测器](../evaluation/m2_same_state_model_eval.py)及相关测试；核对 Git status/diff/HEAD。只改评测器与相关 tests，不改生产 `agents/`、引擎、RAG、Botzone、`.env`、规划 docs、封板 tag/bundle。不得访问或轮换两个 Botzone workspace；不运行 Botzone/live/connector/browser/preflight。若要比较封板代码，仅用隔离 baseline worktree，保持活动 `cao` 不动。

## 实现与验证

1. 逐项审计 `_attempt_binding_stage` 现有严格字段，明确哪些应在离线与真实版本间完全相同，哪些会仅因占位模型名与运行模型名不同而变化。`request_utf8_bytes` 是整个 JSON Request 的长度，生产构造器将 `model` 写入正文；因此不能继续把它当跨占位/真实的精确同一性条件，也不能简单删除所有正文保护。保留两版各自的 prompt 长度、最终原始 ID、推荐、RAG 命中、完整关系和状态校验。
2. 在 fake transport 与真实发送边界的**内存中**计算可比较的规范化请求体摘要，例如只将 `model` 字段替换为固定哨兵后对完整 Request JSON 的稳定编码取摘要；摘要必须覆盖其余控制字段和实际 prompt，不保存请求正文或自由文本。真实模型名继续通过配置导出的预期控制指纹单独绑定，`temperature=0`、`stream=true`、零重试、timeout 与 119 秒预算不得变。若发现还有合法的占位差异，明确字段及依据，再做最小修正；任何不可解释差异保持 fail closed。
3. 把 `attempt_offline_binding_mismatch` 改为固定低基数的**字段类别**停止结果（或等价的安全分类），至少能区分请求规范化正文、公开状态/canonical 候选、prompt/推荐、超时预算与运行控制。对外结果不得含实际字段值、模型名、prompt、正文摘要、URL、密钥或异常正文；不得对错误重试或补位。已发送次数仍计入预算。
4. 用完全禁网的端到端测试让同一冻结状态分别经过占位模型名和另一个合成模型名的实际生产 Request 组装，证明第 1 槽的正常绑定与双版本交错可继续；再分别篡改模型控制、prompt、候选 ID、推荐和状态，证明各自被正确分类并停止。测试须覆盖 32 槽硬上限、零重试、未授权零回调、预发送失败/未知发送停止和低敏输出。单纯把两个相同合成 dataclass 传给校验器不足以验收此次缺口。

重新建立原 8 状态及双版本 16 条**禁网**资格，核对原 seed/step/状态摘要、完整 canonical 动作数、最终候选不超过 80、B/C 适用和模型路径。对实际配置不读取或输出 `.env`、真实模型名、密钥；有必要验证配置接线时只使用 `config.py` 和合成设置。整个任务的 provider 请求、重试均应为 `0`。

## 完成条件与交付

- 评测器可在纯禁网条件下证明合法的模型名差异不会触发绑定停止；请求正文或运行控制的真实漂移仍会停止并给出固定低敏类别。对第 1 槽的原始停止原因只报告“可复现缺口”或有独立证据支持的更精确结论，不用合成测试冒充现场归因。
- 运行相关 `unittest`、主规则回归、适用全量测试和 `git diff --check`；报告禁网资格、测试数、真实请求 `0`、实际修改、仍可能阻断下一轮评估的限制。只提交本轮自有评测/测试文件并报告 commit、最终 Git status。
- 交回规划复审后，才制定新的完整 32 槽真实比较及新授权请求；旧第 1 槽只保留为诊断记录，不拼入新一轮成对效果结果。
