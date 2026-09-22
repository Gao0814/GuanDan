# Coding Codex 执行 Prompt

任务：H3-A5b——修复两项开局诊断 fixture 的物理牌局真实性，然后重新封板八场离线资格。`6ff6d97` 已使公开候选适用条件和目标 C 级经验命中生效；规划 Codex 独立复跑 39 项相关、39 项主规则及 760 项全量测试，并确认八场当前资格均为 `ready`。但 `low_cost_single` 与 `neutral_soft_pair` 由 `_opening_hands()` 构造为第 0 步手牌数 `18/16/16/16`、总数 66。虽然公开 phase 分类为 `opening`，这不是固定单局 profile 的真实开局（108 张、每家 27 张），不能直接用于声称真实开局模型质量。

## 开始与边界

1. 阅读适用 `AGENTS.md`，检查 `.agents/skills/`；阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`，以及相关生产代码、评测工具和测试。先核对 Git status、diff、HEAD 和提交 `6ff6d97a1677377e8e99455748160bdcd76d1274`；保留非本任务修改。
2. 只修改 `evaluation/h3_model_probe_fixtures.py` 与直接相关测试；不得修改 `engine/`、生产 RAG/DeepSeek/策略路径、知识语料、来源 registry、Botzone 或规划 docs。无需新增依赖。若发现不能仅用评测文件解决，报告固定反例并停止扩大范围。
3. 真实 DeepSeek 请求和重试均为 0；不运行 Botzone、live、connector、browser 或 preflight；不读写 `.env`、旧 H3 ledger、`D:\VsCodeProject\BotzoneWorkspace`、seed `47004` evidence 或系统 Temp 文件；不创建仓库外 artifact。

## 实现与验收

1. 将 `low_cost_single` 和 `neutral_soft_pair` 改为真实可达的开局公开状态：优先使用确定性的完整 108 张双副实体牌分配、四家各 27 张、`step_no=0`、空历史、自由领牌；或者使用由完整初始对局经合法 `step(action_id)` 走到的可复现早期状态。所有 observation 与完整 canonical actions 必须由引擎生成；不得伪造 hand_count、phase、RAG hit、候选或 prompt。禁止现场 seed、具体现场动作和业务代码点数特判。
2. 两场仍应分别保有原预注册目标的公开竞争结构：低成本自然单张与较高单张/控制资源、常见对子竞争；中性自然对子/三张与普通单张竞争。两场须由真实 `DeepSeekClient.suggest_action_id()` 的禁网 transport 路径验明 `lead_opening / opening`、目标 `exp_soft_pair_probe_001` 的实际适配命中与最终请求正文渲染、推荐 ID 闭环、最终候选不超过 80、真实请求体绑定和原始合法 ID/source=`model`。不要降低已有资格门槛来追求 `ready`。
3. 增加明确回归断言：两场的实体牌多重集恰好为完整双副牌、总数 108、四家各 27、步数/历史相符；八场资格顺序与其余六场既有关系、RAG、软假设和候选预算不漂移。若完整开局触发本地快捷路径，换独立离线局面而非禁用需要验收的生产行为；若确实无法构造目标，交回低敏失败阶段，不编造通过。

## 验证与交付

- 运行 fixture、RAG、推荐、剪枝、DeepSeek prompt 与 Botzone observability 相关测试，主规则回归和全量 `python -m unittest discover -q`，保留可审计汇总；运行 `git diff --check` 并审视完整 diff。
- 只按明确路径暂存并提交本轮自有评测代码与测试；报告 commit、八场低敏资格摘要、两项开局真实性断言、测试计数、最终 Git status 和保留的外部修改。不得输出手牌、牌面、action ID、prompt、模型文本、URL 或凭据。不把本任务同旧 H3-A4r 视为相同 fixture 的策略对照；本任务不做真实模型质量判断。
