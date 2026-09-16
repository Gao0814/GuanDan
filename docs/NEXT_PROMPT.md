# Coding Codex 执行 Prompt

这是 H3-A2 的真实 DeepSeek 代表场景诊断。不要依赖其他对话的隐含上下文，请从当前仓库重新建立事实。

本任务只做只读离线构造与真实模型诊断，不修改业务代码、RAG、tests、docs、配置或仓库外 Botzone evidence，不创建 commit。项目所有者已长期授权单个明确任务中严格少于 10 次的预注册真实 DeepSeek 请求；本任务总上限固定为 8 次，无需再次申请，但不得扩容或重试。

## 开始前

1. 阅读并遵守根目录及适用范围内的 `AGENTS.md`；检查 `.agents/skills/`。本任务不是 Botzone live 或 workspace 清理，不执行两个项目 Skill。
2. 阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/STRATEGY_SOURCE_AUDIT.md`、`docs/RAG_KB.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`。
3. 检查 Git status、HEAD 和最近提交。HEAD 必须包含 `caa1cc09e91ea8ad9a56e8eefacee21cb10a24e2`，工作树必须 clean；否则失败即停。
4. 只读核对 H3-A1 的生产接线、candidate structure、strategy recommendation、router、RAG、prompt 与相关测试。先运行 `tests.test_h3_a1_projection`、`tests.test_strategy_recommendation`、`tests.test_action_structure`；失败即停。
5. 不读取、复制或改写 seed `47004` workspace evidence。不得启动浏览器、connector、Botzone、preflight 或 live；`D:\VsCodeProject\BotzoneWorkspace` 必须保持不变。

## 固定请求预算

- 恰好 8 个预注册场景，每场至多 1 次真实 DeepSeek 请求；总请求上限 8，`DEEPSEEK_MAX_RETRIES=0` 仅作用于本进程。
- 不因 timeout、exception、invalid suggestion 或不理想动作重试。任何一次调用都计入 8 次预算。
- 在首个真实请求前完成全部 8 个 fixture 的引擎/canonical 校验、目标分类和 prompt marker 校验；任一 fixture 不成立时零请求停止，不可边调用边修 fixture。
- 使用现有 `config.py` / `.env` 正常读取配置，但不得输出 key、base URL、模型自由文本、reasoning、prompt 全文或响应正文。
- 不持久化模型自由文本或逐牌局输入；只在最终报告输出固定低基数分类与计数。

## 八个代表场景

每个场景必须由引擎公开 `observe()` 与完整 canonical `legal_actions()` 构造或证明；不得手写伪合法 action、删除合法候选、硬编码现场 action ID，或让本地 selector 在模型返回后改写结果。允许为诊断关闭既有 opening local shortcut，使场景真正到达模型，但必须在报告中单独标明；其他 router/RAG/recommendation/prompt 生产路径保持开启。

1. **五张同点数炸弹残余关系**：同一完整合法集合内同时存在四张与五张同点数炸弹；四炸留下该点数孤张，五炸清空该点数组。目标分类：若模型选择炸弹，`five_bomb` 优于 `four_bomb_leaves_singleton`；选择其他不拆结构的合法路线记 `alternative`，不伪装成五炸成功。
2. **低成本自然单张试探**：自由首出同时有多个互不拆结构的普通自然单张，其中至少包含明显较低与较高单张，并有公开控制资源可保留。目标分类：`low_cost_single`、`high_single`、`control_resource` 或 `other`；不得把“先出较低单张”实现为本地动作覆盖。
3. **自然对子与单张清理**：自由首出同时可见同一低点数的 natural pair 与 single，pair 能一次清理两张，且队友公开接近走完。目标分类：`pair_cleanup`、`single_split` 或 `other`；prompt 必须同时包含 hand structure 与 teammate coordination 的目标/反例。
4. **中性对子/三张软假设**：开局或前中盘自由首出存在结构安全的中性 pair/triple 与普通 single，C 级软假设可命中。只检查模型是否收到明确可撤回措辞并作出合法动作；分类为 `neutral_group`、`single` 或 `other`，不预设软假设必胜。
5. **队友控桌资源保留**：canonical 跟牌场景中队友领出且无公开紧急对手，pass 与消耗控制资源均合法。目标为现有 `support_teammate / teammate_controls_table` 路径；分类 `pass_preserve`、`spend_control` 或 `other`。
6. **危险对手阻断**：canonical 跟牌场景中危险对手领出并公开接近走完，pass 与合法压制动作并存。目标为 `block_opponent / urgent_opponent_controls_table`；分类 `block`、`pass` 或 `other`。
7. **短残局最少分组**：使用现有 canonical 短残局 fixture 或引擎等价变体，公开最少分组集合与严格更差拆组集合均非空。目标为 `run_out / short_endgame_minimum_groups`；分类 `minimum_group` 或 `strictly_worse`。
8. **炸弹/通配资源软策略**：完整合法集合同时存在自然路线与消耗 wildcard 或炸弹资源的路线，且没有一次出完或危险对手等公开紧急条件。C 级 `bomb_wildcard_management` soft hypothesis 必须进入 prompt。分类 `preserve_resource`、`spend_resource` 或 `other`，不把保留资源当硬规则。

同一点数、花色和 action ID 可按引擎可构造性选择；不得用 seed `47004`、Q/4/10 或某个固定 ID 写生产特判。本任务不修改生产代码，因此 fixture 中使用具体牌只属于评测输入。

## 调用前硬校验

对八个 fixture 全部先离线证明：

- observation、玩家关系、free/follow/table、hand multiset、declared/carrier/wildcard 与完整 legal actions 均通过现有 canonical 派生器；最终候选不超过 80，所有 ID 来自原 legal actions。
- 记录但不输出完整牌面的固定摘要：候选数、目标类别对应 ID 集合大小、strategy intent/status/reason、strategy domains、recommendation status、RAG scene/phase、命中的知识 ID 与 guidance mode、最终 prompt 是否含必要域/目标/反例/soft 标记。
- 8 个场景的预期类别集合均非空且互斥；模型返回任何最终候选内合法 ID 都原样保留，source 必须为 `model`。
- only-pass、一次出完或 opening local shortcut 不得抢先吞掉需要真实请求的场景；若存在则离线修正 fixture 后重新做全部资格，但真实请求开始后不得再改 fixture。

## 判定与停止规则

- 按上述顺序执行 1–8，每场一次；调用结果只允许 `success`、`timeout`、`exception`、`invalid_suggestion` 等现有固定类别。
- 对 success 仅报告原始动作的预注册低基数类别、是否属于最终候选、source 是否为 `model`；不输出动作牌面、prompt 或模型文本。
- 任一合法模型 ID 被模型后策略改写、出现非 `model` source、候选/ID 不守恒、prompt 缺少该场景预期域/目标/soft 标记，立即停止剩余调用并判为实现边界失败。
- 单个模型选择不理想不触发停止或重试；记为该场景 `not_ready`，继续剩余预注册场景。timeout/exception/invalid suggestion 记 `inconclusive`，继续但不重试。
- 最终逐场判定 `ready`、`not_ready` 或 `inconclusive`。整体只汇总“8 场中多少 ready/not_ready/inconclusive”及分层问题位置，不给胜率、普遍收益或“策略已证明正确”的结论。

## 结束验证与报告

1. 报告真实请求总数、每类模型结果数、重试数，必须满足请求 `<=8`、重试 `0`。
2. 报告八场的低基数分类、intent/domain/RAG/prompt marker 是否就绪、模型 ID/source 保真；不报告手牌、动作详情、prompt、模型文本、URL、token 或凭据。
3. 报告偏差位于候选召回、公开特征、router、RAG、prompt 还是模型选择；没有证据时写 `inconclusive`。
4. 运行 `git status --short --branch` 和 `git diff --check`；Git 必须与开始前一致且 clean。不得创建 commit。
5. 明确报告未运行 Botzone/live/connector/browser，workspace evidence 未触碰，并声明结果不是胜率结论。
