# Coding Codex 执行 Prompt

这是独立的 H3-A2r：恢复八场真实 DeepSeek 代表场景诊断的低敏可审计结果。上一 H3-A2 任务因真实请求进程 stdout 未被会话捕获而判定 `inconclusive / evidence_missing`；本任务不是原任务内重试，不得引用、猜测或合并上一任务不可审计的请求结果。

本任务不修改业务代码、RAG、tests、docs、配置或 Botzone evidence，不创建 commit。项目所有者已长期授权单个明确任务中严格少于10次的预注册真实 DeepSeek 请求；本任务是新的明确恢复诊断，总上限固定为8次、重试0，无需再次申请，不得扩容。

## 开始前

1. 阅读并遵守根目录及适用范围内的 `AGENTS.md`；检查 `.agents/skills/`。本任务不是 Botzone live 或 workspace 清理，不执行两个项目 Skill。
2. 阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/STRATEGY_SOURCE_AUDIT.md`、`docs/RAG_KB.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`。
3. 检查 Git status、HEAD 和最近提交。HEAD 必须包含 `8d2146ea9c10db7dde79f6241951e06ff53300df`，工作树必须 clean；否则失败即停。
4. 确认没有上一 H3-A2 真实请求进程仍在运行；若不能确认则零请求停止，不结束或干预无关进程。
5. 不访问、读取、列举、复制或改写 `D:\VsCodeProject\BotzoneWorkspace` 及 seed `47004` evidence；不启动 browser、Botzone、connector、preflight 或 live。

## Fresh 低敏 ledger 硬门槛

唯一允许的新外部 artifact 为：

`D:\VsCodeProject\GuanDanH3A2Audit\h3-a2r.jsonl`

在首个真实请求前：

1. `D:\VsCodeProject\GuanDanH3A2Audit` 必须不存在；若已存在则失败即停，不删除、不覆盖、不换路径。
2. 创建该普通非链接目录，并以 exclusive-create 建立唯一 ledger；创建后再次确认目录和文件均为普通非链接对象且位于该固定目录内。
3. JSONL 使用 UTF-8，每行一个只含固定低敏字段的 JSON object；每次写入后必须 `flush` 并 `os.fsync`。
4. 禁止写入或输出：牌面、手牌、action ID、canonical action正文、prompt、模型响应、reasoning、异常正文、URL、token、key、Cookie、请求/响应原文或任意凭据。
5. ledger 只允许以下事件：
   - `header`：固定schema `h3-a2r-v1`、Git HEAD、场景数8、请求上限8、重试上限0；
   - `qualification`：场景编号/固定名称、`ready|failed`、候选数、各目标类别数量、固定intent/domain/recommendation/RAG枚举或布尔marker；
   - `qualification_complete`：八场是否全部ready；
   - `request_started`：请求序号与场景编号，必须在调用前持久化；
   - `request_result`：固定provider outcome、低基数动作类别、是否属于最终候选、source是否为model、`ready|not_ready|inconclusive`；
   - `summary`：请求总数、各outcome数、重试数、ready/not_ready/inconclusive总数、是否完整结束。
6. 不得把Python traceback或自由异常字符串写入ledger；异常只映射为既有固定类别。`request_started` 数量是本任务真实请求计数的审计真值。
7. 任务结束后保留ledger供规划复审，不删除、不移动、不修改；报告其绝对路径、bytes和完整SHA-256。

## 离线资格与固定请求预算

- 先运行 `tests.test_recommendation_candidate_closure`、`tests.test_h3_a1_projection`、`tests.test_strategy_recommendation`、`tests.test_action_structure`；失败即停。
- 从头重建并校验全部8个engine-backed fixture，不复用上一任务内存状态。所有八场的 `qualification` 事件都持久化后再写 `qualification_complete`。
- 任一场资格失败时，写入失败资格和 `qualification_complete=false`，真实请求0并停止；不得边调用边修fixture。
- 八场全部通过后，按1–8顺序每场至多1次；总请求上限8，`DEEPSEEK_MAX_RETRIES=0`仅作用于本进程。
- 每次必须先持久化 `request_started`，再调用模型；timeout、exception、invalid suggestion或不理想动作均不重试。
- 不持久化模型自由文本或逐牌局输入；stdout也只输出ledger允许的低敏字段。

## 八个冻结场景

每场必须由引擎公开 `observe()` 与完整 canonical `legal_actions()` 构造；不得手写伪合法action、删除合法候选、硬编码现场action ID，或让本地selector在模型返回后改写结果。允许为诊断关闭既有opening local shortcut，但其他router/RAG/recommendation/prompt生产路径保持开启。

1. **五张同点数炸弹残余关系**：四炸留下同点数孤张，五炸清空该点数组。分类 `five_bomb`、`four_bomb_leaves_singleton` 或 `alternative`。
2. **低成本自然单张试探**：多个结构安全普通自然单张和可保留控制资源并存。分类 `low_cost_single`、`high_single`、`control_resource` 或 `other`。
3. **自然对子与单张清理**：同一低点数natural pair与single并存，队友公开接近走完。分类 `pair_cleanup`、`single_split` 或 `other`。
4. **中性对子/三张软假设**：结构安全中性pair/triple、普通single和C级可撤回软假设同时可达。分类 `neutral_group`、`single` 或 `other`。
5. **队友控桌资源保留**：队友领出、无公开紧急对手、pass与消耗控制资源均合法。分类 `pass_preserve`、`spend_control` 或 `other`。
6. **危险对手阻断**：危险对手领出且公开接近走完，pass与合法压制并存。分类 `block`、`pass` 或 `other`。
7. **短残局最少分组**：公开最少分组集合与严格更差拆组集合均非空。分类 `minimum_group` 或 `strictly_worse`。
8. **炸弹/通配资源软策略**：自然路线与消耗wildcard/炸弹资源路线并存且无公开紧急条件。分类 `preserve_resource`、`spend_resource` 或 `other`。

不得使用seed `47004`，不得在生产代码中增加Q/4/10、固定点数或action ID特判。本任务不修改生产代码。

## 调用前硬校验

八场必须全部证明：

- observation、玩家关系、free/follow/table、hand multiset、declared/carrier/wildcard和完整legal actions通过现有canonical派生器；最终候选不超过80且ID均来自原集合。
- recommendation由完整canonical actions生成并通过同一validator，objective在共享预算内，全部recommendation IDs位于实际prompt candidates；模型前建议、必要域/目标/反例/soft marker存在。
- 预注册类别集合非空且互斥；模型返回最终候选内合法ID时原样保留且source为`model`。
- only-pass、一次出完或opening shortcut不吞掉真实请求路径。

## 判定与停止规则

- provider outcome只允许现有固定类别，例如`success`、`timeout`、`exception`、`invalid_suggestion`。
- success只映射为预注册低基数动作类别，不写动作ID或牌面；最终候选与source守恒则按原规则判`ready`或`not_ready`。
- timeout/exception/invalid suggestion判`inconclusive`，继续下一冻结场景但不重试。
- 若出现模型后策略改写、非`model` source、候选/ID不守恒或必需prompt marker缺失，先写低敏结果事件，再停止剩余调用并在summary标记不完整。
- 不理想模型动作本身不停止后续场景。

## 结束验证与报告

1. 从ledger重新读取并验证：header唯一、八条qualification及qualification_complete完整；`request_started`与`request_result`按场景配对或能明确显示中断点；序号连续唯一；summary计数守恒；请求不超过8、重试0。
2. 报告每场固定名称、资格状态、provider outcome、低基数动作类别、候选/source守恒及ready/not_ready/inconclusive；不得补写不可观测结果。
3. 报告整体汇总和偏差层级，不给胜率、普遍收益或“策略已证明正确”的结论。
4. 报告ledger绝对路径、bytes、完整SHA-256；保留该文件供规划Codex读取复审。
5. 运行 `git status --short --branch` 与 `git diff --check`；Git必须保持开始前HEAD且clean，不创建commit。
6. 明确报告Botzone/live/connector/browser/preflight均未运行，`D:\VsCodeProject\BotzoneWorkspace`未访问，仓库外唯一新artifact就是上述ledger。
