# Coding Codex 执行 Prompt

任务：H3-A3a——收窄 H3-A3 的模型前推荐优先级。`b40000eb1b82ddacd44b397e32b77702ea047719` 的严格关系识别、最终候选中的公开对照提示、合法模型原始 ID 与 `model` source 已通过规划 Codex 的代码/测试复审；本任务只修复其过宽的推荐激活，不重做 H3-A3 或引入新策略覆盖。

## 已复现的阻塞点

规划 Codex 独立运行真实引擎初始局面：seed `0..29` 的 30/30 个状态均识别自然对子/单张关系，且推荐 ID 前两位均被该关系占用；其中 29/30 另有结构安全自然小单。这会让一个本为对子清理目标场景设计的优先级系统性影响普通开局。seed `0..99` 中 18 个初始局面识别同点数四/五炸；18/18 的两侧仍在最终候选和 prompt 对照中可见，但 0/18 同时进入最多 3 项推荐 ID，因为普通对子关系先占预算。这是离线范围问题，不是模型质量或胜率结论。

## 开始前与范围

1. 阅读适用 `AGENTS.md` 并检查 `.agents/skills/`；本任务不属于 Botzone live/清理，不执行那两个 Skill。阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/STRATEGY_SOURCE_AUDIT.md`、`docs/RAG_KB.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md` 和 H3-A3 相关代码/测试。
2. 检查 Git status、diff、HEAD 和最近提交。仅在工作树 clean 且 HEAD 包含 `b40000e` 时实施；遇到外部修改保留并停下说明，不用 reset/clean/restore/checkout/stash。
3. 不访问 `D:\VsCodeProject\BotzoneWorkspace`、seed `47004` evidence 或仓库外 H3-A2r ledger；不清理 Coding 任务留下的系统 Temp 流文件。不运行 Botzone、connector、live、browser、preflight、真实 DeepSeek；不读取/输出 `.env`、凭据、prompt 全文或模型自由文本。

## 最小实现目标

- 保留 `summarize_candidate_contrasts()` 的严格、fail-closed 关系识别及 `DeepSeekClient` 的有界“公开关系对照”。比较仅提供公开事实与可推翻条件，不指令模型必须选某侧；合法模型动作不经后置策略改写。
- 调整 `build_strategy_recommendation()` 中完整关系组对最多 3 个推荐 ID 的占位优先级。一次出完仍最高。普通开局若存在结构安全、低成本的自然单张且队友没有公开紧急走牌条件，不得仅因存在常见自然对子就无条件把对子/同点单张置于推荐前两位；保留低成本单张的原有建议意义。队友公开接近出完且无更高公开紧急目标时，仍允许把对子清理/拆分作为完整关系组优先核验，满足 H3-A2r `pair_cleanup` 的目标条件。
- 同点数四/五炸与普通对子关系共存时，不让遍在的对子关系自动耗尽预算，使炸弹残余关系仍能作为完整成组推荐被核验；若一次出完或其它更高公开紧急目标确实竞争预算，必须按既有优先级稳定降级，不保留半组关系。最终 prompt 中的关系对照仍须只描述实际最终候选同时可见的两侧。
- 保持最多 3 个推荐 ID、最多 4 个 objective、最终最多 80 个候选、原始 ID/签名/顺序、两层候选闭环、畸形 payload fail-closed、来源治理字段隔离及其他 H3-A2r ready 场景不发生无关变化。不要增加固定点数、现场 seed/action ID 特判、本地直接动作、post-model override、新 decision source；不改 engine、Botzone、RAG 内容或规划 docs。仅修改直接必要的 AI 文件与 tests。

## 验证与提交

- 新增 engine-backed 多状态/关系竞争回归，明确复现并解决上述 30/30、29/30、18/18、0/18 范围问题；同时保留 H3-A3 的炸弹、队友紧急对子、预算不足不留半组、畸形输入、最终候选/prompt 对照、模型两侧原始 ID/source 测试。至少覆盖一般开局、队友剩余 1–2 张、危险对手、一次出完、四/五炸与对子同存及 80 项候选溢出。测试不得手写伪 canonical action 或使用 seed `47004`。
- 运行改动相关定向、原 H3-A1.1 23 项、主规则 39 项和全量 `python -m unittest discover -q`；运行 `git diff --check`。若环境限制导致某项不能跑，精确报告命令与原因。
- 审查完整 diff 与生产 source：不出现新 post-model 策略分支、新 source、来源治理泄漏或无关文件。只按明确路径暂存自己的业务代码/tests，不用 `git add .`；提交后检查 Git status。
- 报告根因、实现、测试、commit、最终 Git status、保留的外部 Temp 文件和当前范围内剩余风险。本轮真实模型请求必须为 0；不要声称两项 H3-A2r `not_ready` 已转为 ready。交回规划 Codex 独立复审后再单独安排真实模型诊断。
