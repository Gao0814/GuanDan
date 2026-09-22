# Coding Codex 执行 Prompt

任务：H3-A3——修复两类模型前关系对照的表达与代表保留。先独立从当前仓库建立事实，不把下述诊断当作某一具体动作必然最优的证明。

## 背景与边界

规划 Codex 已复核独立 H3-A2r 低敏 ledger：八场资格 ready、8 次真实请求/8 次 success/0 重试、6 ready/2 not_ready；`bomb_residual=alternative`、`pair_cleanup=other`。所有成功动作属于最终候选、source=`model`。这是单点类别结果，不保存原始牌面/action ID/模型文本，也不证明胜率或具体最优动作。原 H3-A2 因 stdout 丢失仍是 `inconclusive / evidence_missing`，不得追认。H3-A2r ledger 保留在 `D:\VsCodeProject\GuanDanH3A2Audit\h3-a2r.jsonl`，本任务不得改写、移动或清理。

当前代码的可检验缺口是：`build_strategy_recommendation()` 的最多 3 个 ID 按 finisher、自然单张、自然对子填充，没有主动把同点数四/五炸作为对照；多个自然单张也可能挤掉用于比较的自然对子。最终 prompt 已有残余结构事实，但没有明确把这两组候选按公开条件和反例并列比较。任务只改善模型前输入，让 DeepSeek 在合法候选中自行裁决；不得新增本地策略动作、过滤合法候选、后置改写、decision source 或固定现场牌点特判。

## 开始前

1. 阅读适用 `AGENTS.md`，检查 `.agents/skills/`；本任务不是 Botzone live 或 workspace 清理，不执行那两个 Skill。阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/STRATEGY_SOURCE_AUDIT.md`、`docs/RAG_KB.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`。
2. 检查 Git status、diff、HEAD 与最近提交。仅在 clean 且包含 `8d2146e` 时开始；保留任何外部修改，不用 reset/clean/restore/checkout/stash。阅读相关生产代码和测试，明确 `recommendation -> 首层剪枝 -> 最终80项 -> prompt` 的真实顺序。
3. 不访问 `D:\VsCodeProject\BotzoneWorkspace` 或 seed `47004` evidence；不运行 Botzone、connector、live、browser、preflight、真实 DeepSeek，也不读取或输出 `.env`、模型原文、凭据。H3-A2r ledger 无需再读取原始内容；若只需核对规划摘要，以 docs 为准。

## 实现范围

1. 从公开 `observe()` 与完整 canonical `legal_actions()` 严格识别两个关系，证据不足则不激活：
   - 同点数自然四张与五张炸弹同时合法，四炸留下同点数孤张、五炸清空该点数组。让两项在最终候选及有界对照中同时可见，并把“少耗一张炸弹资源”和“避免残余孤张/减少后续分组”的取舍明确告诉模型。不得无条件命令选五炸；一次出完、公开紧急性、牌权或更高价值结构可以改变判断。
   - 同点数自然对子与拆出其中一张的单张同时合法，整对清理与留下同点数单张有公开结构差异。两项要在最终候选及有界对照中同时可见；结合队友公开剩余张数说明传递牌型与清理低价值牌的取舍。不得无条件命令出对或根据队友暗牌推理；若存在更紧急的出完、阻断或回手目标，要允许模型推翻。
2. 对照代表与推荐 ID 仍需固定预算、确定顺序、原始 action ID、签名去重和 fail-closed。最多 3 个 recommendation ID，objective 最多 4 个，最终候选最多 80。关系保护只在严格识别且预算允许时启用；明确更高优先级目标与关系竞争时，按既有公开优先级合理取舍并以测试锁定，不得让普通自然单张靠列表顺序偶然挤掉已识别关系。不要放松 canonical 校验或扩大所有场景候选。
3. 仅使用已激活来源知识：B级结构/组牌原则可作条件化建议，C级炸弹/通配内容继续标明 `soft_hypothesis`、可撤回。H3-A2r 的 `bomb_residual` 资格记录 soft marker 为 false；先查明该场相关 C 级假设是否真的进入最终 prompt，不能把“RAG 域可达”当作“具体知识已呈现”。若需要调整检索/投影，只允许基于现有已激活条目做最小修正并加回归；不要把作者、等级、URL、registry 状态等治理字段送入检索正文或 prompt，不为了形式新增经验条目。
4. DeepSeek 成功返回最终候选中的合法 ID 时，原样返回并记录 `model`；legacy source 只读兼容保持。opening 窄快捷路径、其它六个 H3-A2r 场景、engine 和 Botzone 协议不应有无关变化。

## 验证与交付

- 新增/更新 engine-backed 关系型测试，使用多种点数、手牌顺序、队友剩余张数与公开紧急性变体；不用伪 canonical action、现场 action ID 或 seed `47004`。至少覆盖：四/五炸均可见且对照语义出现；自然对子/同点单张均可见且对照语义出现；finisher/危险对手竞争、超过代表预算、接近80候选上限、畸形公开 payload 降级、重复签名/原始顺序、模型返回两侧任一合法 ID 均保持 `model`。
- 运行修改相关定向测试、原 H3-A1.1 23 项、主规则 39 项与全量 `python -m unittest discover -q`；运行 `git diff --check`。若测试环境有限，准确报告命令与原因。
- 检查完整 diff 与生产 source 扫描，确认无 post-model selector/guard、新 source、固定现场点数、seed 特判、provenance 字段泄漏。只提交本任务业务代码和 tests 的自有修改，不修改规划 docs、`.env`、仓库外 ledger 或 Botzone evidence；按明确路径暂存，不用 `git add .`。
- 报告改动原因、文件、测试结果、commit、最终 Git status、保留外部修改及当前范围内剩余风险。不要发起真实请求或以本轮离线实现声称两场已变成 ready；交回规划 Codex 独立复审后，再单独设计不超过既有授权上限的真实模型对照。
