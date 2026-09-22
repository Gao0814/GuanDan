# Coding Codex 执行 Prompt

任务：H3-A4q——只修复诊断资格的可重复性与可定位性，建立八类 engine-backed 离线场景和分阶段资格检查。H3-A4 的新低敏 ledger 已记录八场 `candidate_count=0`、全部资格失败、真实请求0，但没有失败阶段；这不能直接归因为生产策略错误。不要在本任务调用真实 DeepSeek，也不要直接修改策略生产路径来迎合场景。

## 开始与边界

1. 阅读适用的 `AGENTS.md`，检查 `.agents/skills/`；本任务不执行 Botzone live 或 workspace 清理 Skill。阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/STRATEGY_SOURCE_AUDIT.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`，并检查 Git status、diff、HEAD、最近提交。确认当前 HEAD 包含 `b67075391d81add85ab9dc744d8cb886052fde77`；保留所有他人修改，不能混入本次提交。
2. 本任务允许修改 `evaluation/` 中最小必要的离线资格工具及对应 `tests/`；不修改 `engine/`、`agents/`、`rag/`、`integrations/`、配置、规划 docs 或项目 Skill。若离线检查证明生产链路确有缺陷，记录最小反例并停止该生产修复，交回规划 Codex 单独立项；不得在本任务中顺手改策略。
3. 网络/真实 DeepSeek、重试、Botzone、connector、browser、preflight、live 全部为0。不得读取 `.env` 或输出密钥、URL、牌面、完整手牌、action ID、prompt、模型自由文本或异常正文到常规报告。不得访问 `D:\VsCodeProject\BotzoneWorkspace`、seed `47004` evidence、`h3-a2r.jsonl`、`h3-a4.jsonl` 或系统 Temp 流文件；不新增仓库外 ledger。测试中显式避免真实模型与 dotenv 加载。

## 实现

1. 从当前代码重建 H3-A4 八场的资格流程，定位当前可复现的最早失败阶段；旧 ledger 没有阶段信息，不要求也不允许猜测旧进程的确定根因。不要把记录中的0候选当作生产 `legal_actions()` 一定为空。仅用当前代码/测试与新造的离线引擎局面定位，不读旧 ledger 内容。针对可证明的编排问题，建立可复用的固定八场构造与资格 API，例如 `evaluation/h3_model_probe_fixtures.py`，以及单独的 `tests/test_h3_model_probe_fixtures.py`。可以复用既有测试辅助，但不能调用私有引擎状态作为 AI 的输入。
2. 每个场景必须由引擎构造可达状态，从 `observe()` 与完整 `legal_actions()` 取得公开输入和 canonical 动作。不要手写伪 canonical、裁掉合法动作、用现场牌谱/seed `47004`、把预期 action ID 固化为生产逻辑或用空候选/预填 `ready` 占位。固定八场顺序、名称及关系如下：`bomb_residual`（自然四/五炸残余对照）、`low_cost_single`（低成本安全小单与高单/控制资源）、`pair_cleanup`（队友公开剩余1–2张时自然对子/同点单张）、`neutral_soft_pair`（中性对子/三张与C级软假设）、`teammate_controls`（队友控桌 pass/资源消耗）、`danger_block`（危险对手领出 pass/合法阻断）、`short_endgame`（最少分组/严格更差动作）、`bomb_wildcard_soft`（自然路线/炸弹或通配消耗及C级软假设）。原H3-A4冻结类别不扩张、不偷换场景目标。
3. 对每场分阶段检查并返回固定低基数结果：场景构造、公开/canonical校验、完整候选与类别分区、recommendation同一validator、最终候选`<=80`且ID/签名/推荐闭环、router/RAG、最终prompt必需marker、local shortcut/only-pass/一次出完排除、假客户端成功返回已展示原始ID且source=`model`。第1、3场须检查两侧完整进入推荐、最终候选与公开关系对照；第4、8场须检查C级软假设可撤回marker。检查必须调用实际生产投影链路，而不是测试自造marker或只核对上游对象。失败只用固定阶段枚举/计数报告，不泄露牌面、action ID、prompt或异常正文；异常fail closed，不能吞错后标ready。
4. 类别划分保持H3-A4的冻结分类，并在每场验证非空、互斥与完整覆盖实际最终候选：`bomb_residual`: `five_bomb|four_bomb_leaves_singleton|alternative`；`low_cost_single`: `low_cost_single|high_single|control_resource|other`；`pair_cleanup`: `pair_cleanup|single_split|other`；`neutral_soft_pair`: `neutral_group|single|other`；`teammate_controls`: `pass_preserve|spend_control|other`；`danger_block`: `block|pass|other`；`short_endgame`: `minimum_group|strictly_worse`；`bomb_wildcard_soft`: `preserve_resource|spend_resource|other`。若某场既定二分类无法覆盖合法候选，不得把其余动作悄悄归类；报告具体失败阶段，让规划 Codex 决定是否调整下一轮预注册分类。
5. 把场景构造、每阶段成功/失败、候选预算、推荐闭环和marker检查锁进确定性 `unittest`；重复运行结果稳定。允许为诊断显式关闭严格 opening local shortcut，但其余生产 router/RAG/recommendation/prompt 与动作自主权保持不变。工具应可由下一轮独立真实模型任务直接调用，不在模块导入或测试运行时加载密钥、发请求或写仓库外文件。

## 验收与交付

- 先运行新增测试及 `tests.test_strategy_relationship_contrasts tests.test_recommendation_candidate_closure tests.test_h3_a1_projection tests.test_strategy_recommendation tests.test_action_structure`，再运行主规则回归与 `python -m unittest discover -q`；核对 `git diff --check`。若八场不能全部真实资格ready，不得伪造通过或发起模型请求；报告每场固定失败阶段与最小复现，按现有证据停下。
- 检查 diff，只暂存本任务自身的离线工具和测试，提交一次 Coding commit；不要提交规划 docs、环境文件、日志、旧 ledger 或外部修改。报告提交hash、每场资格固定枚举/候选数量、测试结果、最终Git status，以及未处理的外部修改。明确真实 DeepSeek 请求/重试均为0；不得据此宣称H3-A4模型质量改善。
