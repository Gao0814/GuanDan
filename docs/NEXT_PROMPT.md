# Coding Codex 执行 Prompt

任务：H3-A7——建立一套小而可复现的同局面动作质量代理，用于下一步评估 DeepSeek 原始合法动作。H3-A6 的八场真实请求全部 `success`、候选/source 守恒，但 `bomb_residual=alternative`、`pair_cleanup=other` 等类别无法识别具体动作，也不能说明优劣；其六个残局 fixture 是为投影资格构造的短手牌状态，不适合作为完整对局续局质量样本。本任务只做离线评测载体与测试，不调用真实模型，不根据 H3-A6 类别修改生产策略。

## 范围与前提

1. 阅读适用 `AGENTS.md`，检查 `.agents/skills/`；阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`，以及 `evaluation/h3_model_probe_fixtures.py`、`evaluation/strategy_intent_action_quality.py`、对应测试与引擎公开接口。先核对 Git status、diff、HEAD 和最近提交；HEAD 须包含规划提交 `e75cf3a011150ef45a53026b59beb1642a00d6d2`，保留他人修改。
2. 允许新增一个聚焦的 `evaluation/` 评测模块及对应 `tests/`，必要时最小复用或调整现有评测辅助函数。不得修改 `engine/`、`agents/`、RAG、prompt、Botzone、来源语料或规划 docs；不得新增模型成功后的动作覆盖、依赖、运行配置或固定现场牌面特判。
3. 真实 DeepSeek 请求/重试、Botzone/live/connector/browser/preflight 均为 0。不读写 `.env`、`D:\VsCodeProject\BotzoneWorkspace`、seed `47004` evidence、旧 H3 ledger、系统 Temp 文件；不创建仓库外 artifact。

## 实现目标

1. 建立最多 8 个固定、可重放的评测状态，全部从完整 108 张、四家各 27 张、级牌 2、无贡单局开始。可直接复用 H3-A5b 的两项完整开局，也可从独立固定 seed（不得用现场 seed）经合法 `observe()`、`legal_actions()`、`step(action_id)` 回放到中局和残局。保存的是可重放构造方式；评测和报告只使用公开 observation 与完整 canonical actions，不从暗牌构造模型输入。不要把 H3-A6 的短手牌残局 fixture 当成完整对局的续局真值。
2. 评测器接收一个注入的、返回原始 `action_id` 的假 provider 及一个同状态参考动作。严格验证所选 ID 属于实际最终模型候选，参考 ID 属于完整 canonical 候选；分别报告参考动作是否也在模型候选中。模型侧调用仍经过真实 `DeepSeekClient` 的禁网请求组装路径，沿用现有 80 项预算、RAG、推荐与开局公式设置；不得用测试代码重造一套 prompt。评测只在内存中使用动作 ID 和牌局快照。
3. 从同一个引擎状态克隆两条分支，第一步分别执行所选动作与固定参考动作，此后均使用同一冻结 `RuleBasedAIAgent` 续局。优先复用现有 `evaluation/strategy_intent_action_quality.py` 的终局归一、分支续局与比较逻辑；同动作只运行一次并记为 tie。输出固定低敏结果：是否完成、团队 win/draw/loss、团队名次和、续局步数及 `selected_better|reference_better|tie|unevaluable`。不把该代理叫作真实胜率或策略真值。
4. 参考动作固定为同一公开状态下现有 `RuleBasedAIAgent` 从完整 canonical 动作中选择的 ID，并在调用 provider 前确定。状态抽样固定为两项 H3-A5b 完整开局，加从独立 seed `900..919` 按升序推进的真实引擎对局中各取最早满足资格的两个 `midgame`、两个残局族状态，四个新增状态须来自不同 seed。资格要求轮到玩家1、至少两个 canonical 非 pass 选项、真实禁网客户端会进入模型路径且最终候选至少两项；按当前公开 phase 分类，不改写 phase。总数固定 6；同一状态不得重复。最大续局步数固定 5000；比较先看团队 win/draw/loss，再看团队名次和，均相同才记 tie，步数只作诊断。抽样与比较规则在测试中锁定，不能看到模型结果后挑选对照。无合法比较动作、禁网请求体不守恒、所选 ID 不在最终候选、快照不一致、续局失败或步数超限都 fail closed，给固定失败码而非补采或偷偷换样本。若预定样本无法满足，返回明确的离线资格失败，不降低真实性门槛。

## 验证与交付

- 用 fake provider 验证相同动作复用、不同动作独立克隆、参考动作候选可见性、合法性拒绝、终局比较、重跑字节级稳定性、信息边界与故障 fail closed。运行直接相关测试、主规则回归及 `python -m unittest discover -q`；检查 `git diff --check` 与完整 diff。
- 只按明确路径暂存并提交本轮自有评测代码/tests；报告 commit、可重放状态的低敏 phase/候选数分布、分支完成率、测试计数、最终 Git status 和保留的外部修改。不得输出手牌、牌面、action ID、prompt、模型文本、URL 或凭据。只有规划 Codex 独立复审这个离线载体后，才另立真实模型质量代理任务。
