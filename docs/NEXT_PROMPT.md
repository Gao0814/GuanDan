# Coding Codex 执行 Prompt

任务：H3-A10——零网络校准同状态动作质量代理的区分度。H3-A8 六状态代理为 3 次 `selected_better`、3 次 `tie`；独立 H3-A9 六状态为 1 次 `selected_better`、2 次 `reference_better`、3 次 `tie`。两批均只是冻结 RuleBased 续局下的模型单次动作比较。现在不继续重复真实请求、不据此改生产策略；先在这 12 个固定状态上评估最终展示候选的完整代理分布，判断该代理有多少可区分的空间。

## 范围

1. 阅读适用 `AGENTS.md`、检查 `.agents/skills/`；阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、`evaluation/action_quality_proxy.py`、`evaluation/h3_a9_quality_queue.py`、现有质量比较 helper 与相关测试。先核对 Git status、diff、HEAD 和最近提交，确认包含 `6b8bd48cef8801f59a3a151524f30bd5025afd97`，保留他人修改。
2. 只在 `evaluation/` 与对应 `tests/` 增加最小的离线校准器。复用现有 H3-A8/H3-A9 共 12 个样本、最终候选、冻结 RuleBased 参考动作、`_rollout` 与 `_compare_quality`；不改变抽样、候选剪枝、比较顺序或生产 `engine/`、`agents/`、RAG、prompt、Botzone。不得从 H3 ledger 推测或重建模型所选 action ID。
3. 真实 DeepSeek 请求/重试、其它网络、Botzone/live/connector/browser/preflight 均为 0。不读取 `.env`、旧 H3 ledger、`D:\VsCodeProject\BotzoneWorkspace`、seed `47004` evidence 或系统 Temp 文件；不创建仓库外 artifact。任何动作 ID、手牌、prompt、模型文本、URL、凭据和原始引擎快照只留在内存，不进入低敏报告。

## 实现与验收

1. 对每个样本，先验证公开 observation 与完整 canonical actions 对应同一真实快照、phase/完整及最终候选数与冻结契约一致、最终候选 ID 唯一且来自完整 canonical 集合、RuleBased 参考 ID 在最终候选中。每个最终展示候选仅在该快照的独立克隆上执行首步，之后使用现有冻结 RuleBased 续局；同动作只计算一次。对每个结果使用既有“团队终局类别优先、团队名次和次之、步数只诊断”的比较口径与参考动作比较。任何非法、快照漂移、续局未完成、步数超限或比较异常均固定失败码并 fail closed，不跳过坏候选后继续给出完整分布。
2. 只输出每状态低敏聚合：样本名、phase、完整/最终候选数、完成候选数、`better_than_reference / tie_with_reference / worse_than_reference` 三类计数、参考动作是否可见、固定状态码；以及 12 状态汇总。不输出候选级明细、动作 ID、牌面、来源 seed 或可反推具体动作的异常文本。不要把“候选数占比”解释为模型随机选择概率、胜率或最优策略证明。特别说明：H3-A8/A9 未保存模型 ID，本任务不能重算两批真实模型动作的具体排名，只校准当前代理的分辨率。
3. 加入最小合成 fixture 与全部 12 个 engine-backed 样本回归，锁定代表性的 better/tie/worse 比较、同动作只续局一次、独立克隆、缺失/非法候选与未完成分支 fail closed、稳定低敏序列化。运行直接相关测试、主规则回归及 `python -m unittest discover -q`；检查 `git diff --check` 与完整 diff。只按明确路径暂存并提交本轮自有 `evaluation/`、`tests/` 文件，报告 commit、各样本聚合及总计、测试数、最终 Git status 与保留的外部修改。

规划 Codex 独立复审此校准结果后，再决定继续真实模型评测、调整代理口径或进入新 live；本任务不预先选择其中一种。
