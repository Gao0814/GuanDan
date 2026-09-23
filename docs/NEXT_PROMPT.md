# Coding Codex 执行 Prompt

任务：H3-A6——对 H3-A5/H3-A5b 修正后的八个固定场景做一次真实 DeepSeek 低敏单点诊断。只记录当前版本原始模型动作的预注册类别、provider 结果及最终候选/source 守恒。两项开局 fixture 已改为完整 108 张分配，且开局公式在禁网资格中保持启用；旧 H3-A2r/H3-A4r 使用不同 fixture/链路，类别差异不能解释为同状态策略改善。本任务不修改或提交仓库文件。

## 前置门槛

1. 阅读适用 `AGENTS.md`，检查 `.agents/skills/`；阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、`evaluation/h3_model_probe_fixtures.py` 和对应测试。检查 Git HEAD、status、diff、最近提交；HEAD 必须包含 `13b9817c9b4dd55f14fc31368acfc8ee8e1a5a59` 且工作树 clean。确认没有其它本项目真实 DeepSeek 诊断进程；不能确认时零请求停止，不干预无关进程。
2. 先运行 `python -m unittest tests.test_h3_model_probe_fixtures tests.test_strategy_relationship_contrasts tests.test_recommendation_candidate_closure tests.test_h3_a1_projection tests.test_strategy_recommendation tests.test_action_structure -q`，再调用当前 HEAD 的 `qualify_h3_model_probe_fixtures()`。八场须依固定顺序全部 `ready`，最终候选非空且不超过 80；两项开局须经完整双副牌、每家 27 张、第 0 步/空历史与引擎公开输入重放断言；推荐、RAG 来源、软假设实际请求正文、关系对照、请求体绑定、分类覆盖、开局公式启用及模型原始 ID/source 门槛均须通过。任一失败时零请求停止并报告固定场景名、失败阶段与低敏计数。零网络准备错误可原地修正并重做完整资格，但不得改变 fixture、生产代码或门槛。
3. 本任务真实 DeepSeek 请求最多 8 次，固定每场最多 1 次、重试 0；这是项目所有者已长期授权的严格少于 10 次范围。`DEEPSEEK_MAX_RETRIES=0`、`CARD_TRACKING_ENABLED=0` 仅设在本进程，运行时确认客户端实际 max_retries=0；开局公式、hand evaluation、router/intent/recommendation 与禁网资格的配置一致。不得补跑或扩容。
4. 不运行 Botzone、live、connector、browser 或 preflight；不访问 `D:\VsCodeProject\BotzoneWorkspace`、seed `47004` evidence、旧 H3 ledger 内容或系统 Temp 文件。不人工打开或输出 `.env`；真实配置仅经 `config.py` 读取。不得输出或持久化牌面、手牌、动作 ID、prompt、请求/响应自由文本、reasoning、异常正文、URL、token 或凭据。

## 唯一新审计 artifact

固定路径：`D:\VsCodeProject\GuanDanH3A2Audit\h3-a6.jsonl`。仅在八场离线资格全部 ready 后创建；父目录须已存在且为普通非链接目录，目标须不存在，否则零请求停止，不换路径。用独占创建的 UTF-8 JSONL，逐行 flush 并 `os.fsync`。不覆盖、移动、删除或补写任何旧 artifact。结束后报告新文件的绝对路径、bytes 与完整 SHA-256。

固定事件顺序：一个 `header`（schema=`h3-a6-v1`、Git HEAD、八场顺序、请求上限 8、重试 0），八条 `qualification`，一条 `qualification_complete=true`，每场调用前持久化 `request_started`，调用后持久化 `request_result`，末尾 `summary`。资格事件只记录场景名、阶段、原始/最终候选数、预注册类别计数与必要的布尔门槛。结果事件只记录连续序号、场景名、固定 provider outcome、固定动作类别或 `inconclusive`、是否属于实际最终候选、source 是否为 `model` 和守恒布尔值。`request_started` 完成持久化后才发起该场调用；若进程中断，保留可审计中断点，不猜测结果。

## 八场请求与判定

使用当前 `build_h3_model_probe_fixtures()` 和生产 `DeepSeekAIAgent`/`DeepSeekClient`，同一公开 observation、完整 canonical 动作及与资格一致的配置：`rag_top_k=3`、hand evaluation/开局公式/router shadow/intent prompt/recommendation 开启，card tracking 关闭，verbose 关闭。不得以禁网客户端代替真实请求，不缩减原始候选，也不增加模型成功后的动作改写。只在内存里检查实际最终候选与原始模型 action ID/source，再映射为以下类别：

1. `bomb_residual`：`five_bomb|four_bomb_leaves_singleton|alternative`
2. `low_cost_single`：`low_cost_single|high_single|control_resource|other`
3. `pair_cleanup`：`pair_cleanup|single_split|other`
4. `neutral_soft_pair`：`neutral_group|single|other`
5. `teammate_controls`：`pass_preserve|spend_control|other`
6. `danger_block`：`block|pass|other`
7. `short_endgame`：`minimum_group|strictly_worse`
8. `bomb_wildcard_soft`：`preserve_resource|spend_resource|other`

Provider outcome 使用预注册的低基数枚举 `success|timeout|exception|invalid_suggestion`。成功时，动作必须属于实际最终候选、source 必须为 `model`，然后记录其固定类别。失败只记 `inconclusive` 并保持零重试；可继续未请求场景。若发现候选、ID 或 source 守恒破坏，持久化该低敏结果后停止其余请求，并将 summary 标记为不完整。`alternative|other` 本身不是技术失败，也不是策略优劣结论。

## 结束审计

重读本轮新 ledger，检查唯一 header、八条资格、请求序号连续、started/result 配对或明确中断点、请求总数不超过 8、重试 0、结果和 summary 守恒。报告逐场固定类别/技术状态与汇总，说明这些是当前 fixture 的单次选择，不能推断胜率或与旧诊断的因果改善。最后核对 Git HEAD/status 与 `git diff --check`：不创建仓库修改或 commit；说明旧 ledger、Botzone workspace 和系统 Temp 文件未访问。
