# Coding Codex 执行 Prompt

任务：H3-A4r——使用已封板的八场engine-backed资格fixture，完成一次独立、低敏、真实DeepSeek单点诊断。只报告当前版本的原始模型动作类别与候选/source技术守恒；不把一次选择解释成最优打法、胜率或相对H3-A2r的因果改善。本任务不改仓库代码、tests、RAG、docs、配置或既有evidence，不创建commit。

## 前置门槛

1. 阅读适用`AGENTS.md`、检查`.agents/skills/`；本任务不是Botzone live或workspace清理，不执行那两个项目Skill。阅读`README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`与`evaluation/h3_model_probe_fixtures.py`及对应测试。检查Git status、diff、HEAD及最近提交；HEAD必须包含`81506f802f22e492d2cfec54f92061e45f5ffa04`，工作树必须clean。确认没有其它本项目真实DeepSeek诊断进程；不能确认则零请求停止，不干预无关进程。
2. 不访问`D:\VsCodeProject\BotzoneWorkspace`、seed`47004` evidence、旧`h3-a2r.jsonl`/`h3-a4.jsonl`内容或系统Temp流文件；不运行Botzone、connector、browser、preflight或live。不得人工打开或输出`.env`；真实配置只经`config.py`读取，不输出密钥、URL、Cookie、牌面、手牌、action ID、prompt、模型响应/reasoning或异常正文。
3. 本任务预注册真实DeepSeek外部请求总数最多8次，每场最多1次、重试0；属于项目所有者已授权的严格少于10次范围。`DEEPSEEK_MAX_RETRIES=0`和`CARD_TRACKING_ENABLED=0`仅设于本进程；后者用于与离线资格的固定关闭记牌配置一致。运行时确认实际客户端max_retries为0。不得扩容或补跑某场，也不得把上轮H3-A4零请求任务的审计文件当成本轮artifact。
4. 独立运行`python -m unittest tests.test_h3_model_probe_fixtures tests.test_strategy_relationship_contrasts tests.test_recommendation_candidate_closure tests.test_h3_a1_projection tests.test_strategy_recommendation tests.test_action_structure -q`。随后调用`qualify_h3_model_probe_fixtures()`，按冻结顺序核对八场全部`stage=ready`、最终候选非空且`<=80`、请求体绑定、RAG、推荐/关系/软假设、分类覆盖和source门槛。任一不通过时零请求停止，只报告固定场景名/失败阶段/计数；准备阶段零外部副作用错误可原地修正并重新做完整离线检查，但不得绕过门槛或改变fixture/策略代码。

## 唯一新外部artifact

固定新路径：`D:\VsCodeProject\GuanDanH3A2Audit\h3-a4r.jsonl`。八场离线资格全部ready后才创建。父目录必须已存在且为普通非链接目录，新目标必须不存在；条件不满足则零请求停止，不换路径。使用exclusive-create普通非链接UTF-8 JSONL，每行写入后立即flush并`os.fsync`。不覆盖、删除、移动或改名任何既有文件。结束后保留并报告绝对路径、bytes与完整SHA-256。

固定低敏事件顺序：`header`（schema=`h3-a4r-v1`、Git HEAD、8场、上限8、重试0）、按场景顺序8条`qualification`、`qualification_complete=true`、每次调用前的`request_started`和调用后的`request_result`、最终`summary`。资格事件只含固定场景名、ready阶段、原始/最终候选数、各预注册类别计数及必需布尔门槛；结果事件只含序号、场景名、固定provider outcome、固定动作类别或`inconclusive`、是否在实际最终候选、source是否`model`、守恒布尔值。`request_started`必须在每次真正调用前完成持久化，作为本任务请求预算的审计上界。禁止持久化或打印完整observation/action、牌面、action ID、prompt、请求/响应原文、模型自由文本、异常正文、URL、token或凭据；异常只能映射固定outcome。

## 八场真实请求

使用`build_h3_model_probe_fixtures()`与生产`DeepSeekAIAgent`/`DeepSeekClient`，保持离线资格同一公开输入、完整canonical动作及配置：`rag_top_k=3`、hand evaluation开启、opening formula关闭、card tracking关闭、router shadow与intent prompt及recommendation开启、card-confidence默认关闭、verbose关闭。不得用禁网fixture client代替真实请求，不人为缩减合法动作，也不得增加成功模型动作后的策略覆盖。运行时仅在内存中捕获实际最终候选及技术状态以分类；不持久化敏感内容。

冻结顺序及类别：

1. `bomb_residual`：`five_bomb|four_bomb_leaves_singleton|alternative`
2. `low_cost_single`：`low_cost_single|high_single|control_resource|other`
3. `pair_cleanup`：`pair_cleanup|single_split|other`
4. `neutral_soft_pair`：`neutral_group|single|other`
5. `teammate_controls`：`pass_preserve|spend_control|other`
6. `danger_block`：`block|pass|other`
7. `short_endgame`：`minimum_group|strictly_worse`
8. `bomb_wildcard_soft`：`preserve_resource|spend_resource|other`

每场最多调用一次。provider outcome只用`success|timeout|exception|invalid_suggestion`等预先固定低基数枚举；成功时动作必须属于实际最终候选，source必须为`model`，再按冻结类别记录。超时、异常、无效建议只记技术`inconclusive`且不重试，可继续其它尚未调用场景；任何候选/ID/source守恒破坏或后置改写，在写入低敏结果后停止剩余请求并将summary标为不完整。选择`alternative|other`本身不构成技术失败，也不能擅自判定策略错误。不要从八场类别推断普遍收益；新fixture与H3-A2r不完全同状态，不能宣称配对改善。

## 结束审计

重读本轮新ledger，验证唯一header、八条资格、请求序号连续、started/result逐一配对或明确中断点、请求数`<=8`、重试0、provider与动作类别汇总守恒、summary完整性。报告八场固定类别/技术状态和总计，不输出牌面、动作ID或模型文本；如果stdout丢失，只报告持久事件能证明的边界，不猜测缺失结果。最后检查Git HEAD/status和`git diff --check`：仓库不得有任何本轮修改或commit。明确说明旧ledger、Botzone workspace和Temp文件未访问，Botzone/live/connector/browser/preflight均为0。
