# Coding Codex 执行 Prompt

任务：H3-A4q1——纠正八场离线资格工具的假阳性门槛；不做真实模型请求。`c87defa`的八场正例当前均ready，相关/主规则/全量测试也通过，但规划复审发现：注入空RAG scene/hits后仍有6/8场被判ready；fake client没有执行真实`DeepSeekClient.suggest_action_id()`的最终候选/prompt组装。先把这些离线门槛封住，再另立H3-A4真实诊断任务。

## 边界

1. 阅读适用`AGENTS.md`、检查`.agents/skills/`，阅读`README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`以及本任务对应代码/测试。先核对Git status、diff、HEAD及`c87defabb869dfdedc722e8881426e3a8cdbed37`完整diff；保留所有外部修改。
2. 仅修改`evaluation/h3_model_probe_fixtures.py`和`tests/test_h3_model_probe_fixtures.py`中完成纠错所必需的内容。不修改`agents/`、`engine/`、`rag/`、`integrations/`、配置、规划docs、Skill或其它业务文件；若出现生产链路反例，记录低敏最小证据后停下，交规划Codex另立任务。
3. 真实DeepSeek请求/重试、Botzone、live、connector、browser、preflight、网络均为0。不得读取`.env`、旧`h3-a2r.jsonl`/`h3-a4.jsonl`、`D:\VsCodeProject\BotzoneWorkspace`、seed`47004` evidence或系统Temp文件，不新建仓库外ledger。报告只含固定场景名、阶段、计数和布尔值，不输出牌面、action ID、prompt、模型文本、URL、token或异常正文。

## 纠错与测试

1. 保留现有八场engine-backed构造、顺序、冻结动作分类、候选上限与推荐ID闭环。资格结果的`ready`必须检查实际RAG上下文（至少正确结构和当前场景需要的可用scene/命中证据）、route intent与prompt投影的一致性；第4、8场还须验证C级软假设来自实际RAG证据并在最终prompt出现，而非仅凭任意同名文本。失败返回固定低基数阶段，不泄漏内部内容。不要通过在工具中硬填RAG结果或把空上下文视为ready来达标。
2. 对每场使用禁网注入transport或拦截`DeepSeekClient`实际请求组装，验证其最终展示候选、最终prompt与资格判定使用的是同一结果；fake模型只返回已展示原始合法ID，检查source=`model`。不得发真正HTTP请求或依赖dotenv。当前由资格工具手工复制客户端剪枝/组装逻辑的路径如果保留，必须有逐场与实际客户端路径对照的稳定测试，防止两者漂移后继续误报ready。
3. 新增至少以下反例：空RAG scene/hits使全部八场不ready；错配或缺失关键router intent/场景时不ready；实际最终prompt缺必需marker、关系对照或C级可撤回软假设时不ready；客户端最终候选与资格工具重建结果不一致时不ready。用真实生产投影或定点mock制造反例，不自造已通过标记；检查不会因异常被吞掉而误报ready。
4. 八场正例仍须全部ready且稳定，最终候选数及类别守恒要可审计。若当前fixture的router/RAG场景本身与目标语义不符，不改生产策略、不偷换目标类别；报告固定失败阶段，交回规划Codex决定后续处理。

## 验收与交付

- 运行新增测试与`tests.test_strategy_relationship_contrasts tests.test_recommendation_candidate_closure tests.test_h3_a1_projection tests.test_strategy_recommendation tests.test_action_structure`，再运行主规则回归和`python -m unittest discover -q`；必须捕获全量最终汇总或明确说明未能捕获。检查`git diff --check`和完整diff。
- 仅按明确路径暂存并提交本轮自有离线工具/测试修改，不提交其它文件。报告commit、八场低敏资格与反例结果、相关/主规则/全量计数、最终Git status和任何保留外部修改。真实模型请求/重试均为0；不要声称策略质量或H3-A4真实结果已经改善。
