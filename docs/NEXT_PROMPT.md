# Coding Codex 执行 Prompt

任务：H3-A7a——给已封板的六状态离线动作质量代理增加真实 DeepSeek 请求的可验证接线，但本任务严格零网络。`cb262c5` 已证明完整起局、固定抽样、同快照 RuleBased 参考与两分支续局可重复；现有 `selection_provider` 只是在禁网 transport 内返回假 ID，尚未证明下一轮真实请求所选 ID 与这六个样本的实际 Request、最终候选、续局输入严格绑定。先封住这道评测门槛，再另立真实模型质量任务。

## 开始与范围

1. 阅读适用 `AGENTS.md`、检查 `.agents/skills/`，并阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、`evaluation/action_quality_proxy.py`、`evaluation/h3_model_probe_fixtures.py`、相关生产客户端及测试。先核对 Git status、diff、HEAD 与最近提交；确认包含 `cb262c5829df8750cf3febc55b6fa47892f0bfa2`，保留他人修改。
2. 仅最小修改 `evaluation/` 中的评测接线及对应 `tests/`。六个固定样本、RuleBased 参考动作先冻结、同快照独立续局、比较顺序、低敏结果 schema 均保持不变。不改 `engine/`、生产 `agents/`、RAG、prompt、Botzone、规划 docs、依赖或配置；不新增后置策略动作覆盖。
3. 真实 DeepSeek 请求、重试及其它网络调用均为 0；Botzone/live/connector/browser/preflight 均不运行。不读写 `.env`、旧 H3 ledger、`D:\VsCodeProject\BotzoneWorkspace`、seed `47004` evidence 或系统 Temp 文件；不创建仓库外 artifact。

## 实现与验收

1. 为 `evaluation/action_quality_proxy.py` 提供下一任务可注入真实 `DeepSeekClient` transport 的最小接口。H3-A7a 测试只注入禁网 fake transport，但必须真正经过 `DeepSeekAIAgent`/`DeepSeekClient.suggest_action_id()` 的请求组装、候选筛选与响应解析路径；不可在评测器里复制一套 prompt，也不可由假 provider 再发第二次请求。保留开局公式启用及当前 router/RAG/recommendation/手牌评估设置，跟踪关闭、重试上限为 0。
2. 在内存中将每个样本的公开 observation、完整 canonical actions、最终展示候选、实际 Request JSON 的 user prompt、恰好一次 transport 调用、provider 返回的原始 ID、客户端返回的 ID/source 和续局首步逐项绑定。最终候选必须与实际请求正文中的候选一致；所选 ID 必须属于该集合且 source 为 `model`。零次或多次 transport、请求体/候选漂移、local shortcut/fallback、非法或未展示 ID、快照不一致和 provider 异常一律固定失败码、禁止续局或补采；不要把敏感请求正文、动作 ID 或牌面写入报告/文件。
3. 用禁网 fake transport 覆盖六个固定样本正例、真实客户端请求体绑定、相同动作单次续局复用、不同动作双克隆、RuleBased 参考候选可见、以上各类故障 fail closed、低敏序列化与重复运行稳定。实际完成六组离线续局并报告低敏 phase、候选数和完成率；不能把 fake 结果解释为 DeepSeek 策略质量。
4. 运行直接相关测试、主规则回归及 `python -m unittest discover -q`；检查 `git diff --check` 和完整 diff。只按明确路径暂存并提交本轮自有 `evaluation/`、`tests/` 文件。报告 commit、测试计数、最终 Git status、保留的外部修改及零网络确认。若六场接线资格不能全部通过，应停止并报告失败阶段，不进入真实模型任务。

规划 Codex 独立复审 H3-A7a 后，才安排独立 H3-A8：至多六次、重试零的真实模型同状态代理及新低敏审计；冻结 RuleBased 续局结果只能作为动作质量代理，不是胜率或策略真值。
