# Coding Codex 执行 Prompt

任务：H3-A4——在已封板的 H3-A3/H3-A3a 代码上，完成八类代表场景的独立、低敏、真实 DeepSeek 诊断。只记录当前版本的模型原始选择类别与技术守恒，不把一次动作解释为最优策略、胜率或对 H3-A2r 的因果改善。本任务不修改仓库代码、tests、RAG、docs、配置或既有 evidence，不创建 commit。

## 前置边界

1. 阅读适用 `AGENTS.md`，检查 `.agents/skills/`；本任务不是 Botzone live/清理，不执行那两个项目 Skill。阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/STRATEGY_SOURCE_AUDIT.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`。
2. 检查 Git status、diff、HEAD 和最近提交；HEAD 必须包含 `b67075391d81add85ab9dc744d8cb886052fde77`，工作树必须 clean，否则零请求停止。确认没有其它本项目真实 DeepSeek 诊断进程正在运行；不能确认则零请求停止，不干预无关进程。
3. 不访问 `D:\VsCodeProject\BotzoneWorkspace`、seed `47004` evidence、H3-A2r 旧 ledger 的内容或系统 Temp 流文件。不运行 Botzone、connector、browser、preflight 或 live。不得人工打开或输出 `.env`；真实模型配置只通过既有 `config.py` 读取，不输出密钥、URL、Cookie、prompt、模型响应/reasoning 或异常正文。
4. 项目所有者长期授权单个明确任务中严格少于10次的预注册真实 DeepSeek 请求；本任务最多8次、每场至多1次、重试0，不得扩容或合并上一任务不可审计请求。`DEEPSEEK_MAX_RETRIES=0` 仅用于本进程。

## 唯一新外部 artifact

固定路径：`D:\VsCodeProject\GuanDanH3A2Audit\h3-a4.jsonl`。父目录必须是已存在的普通非链接目录，新文件必须不存在；不删除、覆盖、移动或改名任何既有文件。用 exclusive-create 建立普通非链接 UTF-8 JSONL，每个事件写入后立即 flush + `os.fsync`。若路径门槛不通过，零请求停止，不换路径。任务结束保留文件，报告绝对路径、bytes、完整 SHA-256。

每行只能包含固定低敏枚举、布尔值、计数和 Git HEAD，事件依次为：`header`（schema=`h3-a4-v1`、场景数8、请求上限8、重试上限0）、8条`qualification`、`qualification_complete`、每场调用前的`request_started`与调用后的`request_result`、最终`summary`。资格事件只记场景编号/固定名称、ready/failed、候选数量、分类数量、recommendation/关系对照/intent/RAG/prompt marker 的固定枚举或布尔值；结果事件只记请求序号、场景编号、固定provider outcome、预注册动作类别、是否在最终候选、source是否为`model`及技术守恒判定。`request_started` 必须在调用前落盘，作为本任务请求计数审计真值。禁止在文件或 stdout 输出牌面、手牌、action ID、完整 canonical action、prompt、模型自由文本、请求/响应原文、异常正文、URL、token、凭据；异常只映射固定 outcome。

## 八场冻结类别与离线资格

先独立运行 `tests.test_strategy_relationship_contrasts`、`tests.test_recommendation_candidate_closure`、`tests.test_h3_a1_projection`、`tests.test_strategy_recommendation`、`tests.test_action_structure`。随后从头构造八个不同的 engine-backed 场景：只能从 `observe()` 与完整 `legal_actions()` 取得公开输入和 canonical action，不手写伪合法动作、不删合法候选、不用 seed `47004` 或现场 ID。允许仅为诊断关闭 opening local shortcut，其余生产 router/RAG/recommendation/prompt 路径保持开启。八场全部资格 ready 并写入 `qualification_complete=true` 前，不得发起任何真实请求；任一场失败则记录失败、`qualification_complete=false`，零请求停止。

1. `bomb_residual`：非紧急自由领牌，同点数自然四/五炸均合法，四炸留同点孤张、五炸清空；两侧完整进入推荐、最终候选和“公开关系对照”。动作类别：`five_bomb` / `four_bomb_leaves_singleton` / `alternative`。
2. `low_cost_single`：普通自由领牌，有多个结构安全自然单张、较高单张和控制资源，且常见对子关系可达但不抢占低成本小单推荐。类别：`low_cost_single` / `high_single` / `control_resource` / `other`。
3. `pair_cleanup`：队友公开剩余1–2张、无更高公开紧急目标，自然对子和拆出同点单张均合法；两侧完整进入推荐、最终候选和关系对照。类别：`pair_cleanup` / `single_split` / `other`。
4. `neutral_soft_pair`：无队友紧急条件，有结构安全中性pair/triple、普通single和已激活C级软假设；关系推荐不得无故挤掉低成本单张。类别：`neutral_group` / `single` / `other`。
5. `teammate_controls`：队友领出、无紧急对手，pass与消耗控制资源均合法。类别：`pass_preserve` / `spend_control` / `other`。
6. `danger_block`：危险对手领出且接近走完，pass与合法压制并存。类别：`block` / `pass` / `other`。
7. `short_endgame`：最少剩余分组动作和严格更差拆组动作均合法。类别：`minimum_group` / `strictly_worse`。
8. `bomb_wildcard_soft`：自然路线与消耗炸弹/通配资源路线并存，无公开紧急性，C级软假设必须可撤回。类别：`preserve_resource` / `spend_resource` / `other`。

每场调用前证明：公开输入与完整动作集通过现有 canonical 派生器；最终候选 `<=80`、ID 均来自原集合、签名唯一；recommendation 通过同一validator且全部推荐ID进入最终候选；router/RAG/模型前建议/反例等该场必需 marker 实际进入最终 prompt，第1、3场另须有完整关系对照，第4、8场另须有C级可撤回软假设 marker；类别集合非空且互斥；only-pass、一次出完与本地开局快捷路径不会吞掉请求。对第1、3场尤其核对两侧同在实际最终候选及关系对照，不只检查上游关系可达。

## 请求、停止与报告

- 按1–8顺序每场最多调用一次，总数最多8、重试0。每次先持久化 `request_started`，再调用模型；provider outcome仅用固定 `success|timeout|exception|invalid_suggestion`，success只分类为上述低基数动作类别，合法模型原始ID必须属于实际最终候选且source=`model`。动作类别本身不构成策略 ready/not_ready 判定。
- timeout、exception、invalid suggestion 只记固定`inconclusive`技术结果，不重试，可继续下一场。若出现推荐/候选/ID/source守恒破坏或后置改写，先写低敏结果并停止剩余调用，在summary标记不完整。单纯选了`alternative`/`other`不停止，也不得擅自认定为错误。
- 结束后重读新 ledger，校验唯一header、八条资格、资格完成、请求序号连续、started/result配对或明确中断点、各provider和动作类别计数守恒、请求`<=8`、重试0、summary完整性。报告八场资格、provider outcome、动作类别、最终候选/source技术守恒及总计；不要输出牌面、动作ID或模型文本，不给胜率或因果结论。明确说明新fixture若不与H3-A2r逐字同一，不能把两轮类别变化称为同状态改善。
- 最后检查 Git HEAD/status 与 `git diff --check`；仓库不得有修改或commit。报告新 ledger 的绝对路径/bytes/完整SHA-256、既有H3-A2r ledger和系统Temp文件未改、Botzone/live/connector/browser/preflight为0、workspace未访问。若stdout再次丢失，只以已持久化事件报告可审计到的边界，不猜测缺失结果。
