# Clean Project Handoff

## 1. Project Goal

本项目的长期目标是提供一个可验证的单局掼蛋规则引擎、受规则引擎约束的 AI 决策层，以及用于真实 Botzone 无贡测试桌的本地 AI connector。

当前主线已从严格 Botzone capacity 实验切换为算法优化。真实 Botzone 对局用于阶段性 smoke 和获取公开决策轨迹；只有候选策略先在本地固定 seed 评估中显示稳定收益、且项目所有者明确要求正式对比时，才恢复可比、可审计的 RuleBased/DeepSeek 成对实验。

本项目不是完整的多局升级/贡还比赛引擎。当前 Botzone 主线明确限定为四人、需要进贡为否的单局 play 子集。

最新工作状态以 `docs/PROJECT_STATUS.md` 顶部为准：seed `47005` 单局的六份固定 Codex workspace evidence 仍保留，平台结果为 `platform_error`；额外的空 `D:\VsCodeProject\BotzoneState` 已单独回收。规划 Codex 曾从固定 workspace 短时启动同一个 connector，项目所有者确认页面“已连接”；其新 probe artifact 与旧六份证据共存。随后项目所有者刷新页面，确认个人脚本也显示“已连接”，因此暂停两条启动路径的连接差异排查，不把刷新现象当作已证实的网络或代码根因。`b17c2d9` 已使本地开局直选采用完整关系门槛；`ad7524e` 加入模型前跨牌型指引，`1b8d493` 使 Botzone DeepSeek factory 默认 RAG top‑1 的三个固定开局均收到 B 级来源与新指引，并修复 recommendation 缺席时的判据渲染。规划独立通过相关 96 项、主规则 39 项、全量 835 项及禁网实际 Request 复验。本轮开局输入技术目标已闭环；默认 top‑1 对 C 级软假设的挤出和单点真实响应耗时仍是待决策/待验证事项，不把字符微变当作时延改善。当前无待执行 Coding Prompt。后续如需 live，必须重新盘点 workspace，不能把此处历史快照当作新 inventory 或建目录指令。

## 2. Current Repository State

以下能力已经存在于当前代码，并有测试覆盖：

- `engine/` 实现单局四人掼蛋状态、发牌、牌型、合法动作生成、动作比较、回合推进、接风、名次和终局。
- `GuanDanGame` 暴露 `reset()`、`observe()`、`legal_actions()` 和 `step(action_id)`；公开动作使用稳定的原始 `action_id`。
- `agents/` 包含 `RuleBasedAIAgent`、`DeepSeekAIAgent`、开局公式、手牌评分、记牌、RAG、confidence shadow/prompt 和 strategy intent shadow/prompt。
- `integrations/botzone/` 包含 Botzone 108 实体牌 ID 映射、deal/play 协议、Bot JSON envelope 与 direct-stage 两种 wire mode、HTTP 长轮询、会话持久化、pending/ack 事务、无贡 play adapter、RuleBased/DeepSeek 组合、运行 provenance、聚合审计和前台 runner。
- connector 支持显式 `--agent rule|deepseek|conditional_pressure_pass`、仓库外 state 目录、`--run-token`、零网络 preflight、完成目标和 v7/v8 completion audit。新增条件 mode 只由精确 opt-in 启用，默认仍是 `rule`。可读history负责逐手展示；新增默认关闭的decision trace在Header ack后保存完整公开observation、原始canonical legal actions、selected action及低基数source。
- 仓库级Skills位于 `.agents/skills/`：`botzone-manual-live` 封装单局人工连接、建桌、监测和evidence验收；`botzone-workspace-recycle` 封装已审计artifact的精确回收站清理。run-specific seed、Agent、预算、文件allowlist与hash仍只放在当前任务Prompt。
- `evaluation/botzone_policy_benchmark.py` 能生成正式四座位成对赛程或显式 selected-seat 赛程，并严格聚合 RuleBased/DeepSeek v7/v8 audit。
- `botzone_upload_py36/` 是独立的 Python 3.6.5、无贡、自然牌规则 Bot；`botzone_deepseek_probe_py36/` 的 DeepSeek 调用只做探测，不参与动作选择。
- 最新业务提交链为 `d20dba3`、`7020b35`、`da2fd6b`、`caa1cc0`，由 `7494897` 合入主线：H3-A1 已完成来源策略、十域决策链、RAG/prompt 投影、canonical/预算 fail-closed 和有界代表选择。规划 Codex 独立通过 212 项相关、39 项主规则、732 项全量及 30 局/2730 状态真实引擎离线探针；H3-A0/H3-A0a 已封板，H3-A1 现有基础保留，但 H3-A2 资格检查暴露的 recommendation/final-candidate 跨阶段守恒缺口仍待 H3-A1.1 修复。
- H3-A2 首轮在任何网络调用前停止，请求0、重试0。八场 engine-backed fixture 中五场因完整动作集产生的 recommendation ID 未被 prompt shortlist 保留，严格校验进而删除整个模型前建议区块。规划 Codex 在真实引擎 seed `0..9` 的初始局面全部复现同类失败；当前问题不是模型选择、RAG 来源或 fixture 绕过问题。
- `ba449f5` 已实现通过校验后的 recommendation-ID 两层保护和实际 prompt-candidate 响应边界，但规划复审未封板：40局/3379状态发现4个 builder/validator 预算漂移反例。builder 可产生5个 objective 的 ready payload，而 validator 上限为4，保护随之关闭；当前还需 H3-A1.1a 最小纠错。
- `8d2146e` 已完成 H3-A1.1a：builder/validator 共用4项目标预算，模型前目标按公开紧急性稳定收敛，外部超预算payload继续fail closed。规划Codex独立通过66/39/740项测试和80局/9381状态双推进探针，ready recommendation、受保护ID、最终候选及prompt闭环零失败；H3-A1.1封板。
- H3-A2后续执行报告称八场离线资格均通过，但真实请求进程最终stdout未被会话捕获，且未生成低敏持久结果。请求计数、逐场provider outcome与动作分类不可审计，因此该次真实阶段只记`inconclusive / evidence_missing`，不追认。独立H3-A2r恢复已有可审计低敏ledger：八场资格ready、8请求/8 success/0重试、6 ready/2 not_ready；两个not_ready分别为炸弹残余场景`alternative`与对子清理场景`other`，只支持模型前对照继续诊断。
- canonical危险对手fixture的受约束真实模型检查已判定`danger_opponent_prompt_raw_model_ready`：唯一请求成功、重试0，模型在后置守卫前自行返回固定候选集内的`ordinary`动作；现有`block_opponent / urgent_opponent_controls_table`输入已足以支持退役强制pass阻断。该结果以低敏执行报告为证据，不是整体胜率结论。
- 项目所有者长期授权单个明确诊断/评测任务中严格少于10次的预注册真实DeepSeek请求，无需另行申请；10次及以上仍须事先授权，范围、重试、密钥和自由文本保密边界不变。
- 固定4张自由出牌fixture的守卫前真实模型检查判定为`short_endgame_prompt_raw_model_not_ready`：最少分组集合为`{1,2,5}`，但唯一成功请求的原始动作落在严格更差的单J集合`{3,4}`。当前`ready / control / stable_control`提示未提供最少剩余分组语义；该低敏单点证据支持补充专用prompt，不支持删除或扩大守卫，也不是胜率结论。
- `c32259d`后的同fixture专用prompt复放已判定`short_endgame_dedicated_prompt_raw_model_ready`：唯一请求成功、重试0，原始动作进入最少分组集合`{1,2,5}`；`run_out / short_endgame_minimum_groups`、两项关键语义和RAG低基数字段均符合前提。规划Codex独立复跑126项相关测试；该低敏单点证据支持下一任务退役`short_endgame_plan`生产改写，但不构成整局或胜率结论。
- seed `47004` 的最新HEAD人工DeepSeek采样已形成有效ACK decision trace：25/25/25 request/response/Header、qualified finish=1、24条决策与audit守恒，15次模型success、9次local shortcut、0 fallback、0 transport failure，v8 audit/v4 tombstone provenance一致。平台分类`local_team_loss`不作为策略优劣证据；六份evidence保留在固定workspace。

上述实现检查点：

```text
66009fc
```

当前分支：`cao`。提交数量会随规划检查点继续变化；读取者应以实际 `git rev-list --left-right --count origin/cao...HEAD` 为准，不使用本文中的历史 ahead 数字。

## 3. Confirmed Architecture

### Local game path

```text
GuanDanGame.observe()
        + legal_actions()
        -> Agent.select_action(observation, legal_actions)
        -> original legal action_id
        -> GuanDanGame.step(action_id)
```

`engine/` 是规则真值。AI 只选择动作，不生成规则结果。

### Botzone connector path

```text
Botzone local-AI endpoint
        -> HTTPS GET long poll
        -> poll/parser (Bot envelope or direct stage)
        -> per-match SessionStore
        -> no-tribute public projection + canonical legal actions
        -> RuleBasedAIAgent or DeepSeekAIAgent
        -> validated original action_id + provenance lookup
        -> Botzone [action, claim]
        -> X-Match-* response header
        -> successful delivery acknowledgement
        -> commit pending PlayEffect / update durable session
```

关键实现边界：

- `integrations/botzone/protocol.py`：严格解析 deal/play、history、global、done 和 table view。
- `integrations/botzone/bot_io.py`：处理 Bot envelope replay、direct-stage response 和历史 response 重放。
- `integrations/botzone/session.py`：隔离 match state；成功发送前不提交出牌 effect；完成后生成最小 tombstone。
- `integrations/botzone/play_adapter.py`：把公开 Botzone 局面投影为 engine 兼容的 observation/legal actions，并把选中动作绑定回实体牌 ID。
- `integrations/botzone/agent_runtime.py`：组合 RuleBased 或 DeepSeek；DeepSeek 故障时保留严格分类和 RuleBased fallback。
- `integrations/botzone/runner.py`：运行循环、退出分类、v7/v8 audit 和聚合守恒。
- `evaluation/botzone_policy_benchmark.py`：只消费聚合 audit，不启动 connector、模型或网络。

## 4. Important Invariants

- AI、RAG、confidence、strategy router 和 Botzone adapter 都不得绕过 engine 的合法动作集合。
- 最终动作必须是严格整数 `action_id`，并存在于调用时的原始 `legal_actions()`。
- `declared_cards` 表示声明语义，`carrier_cards` 表示真实消耗牌；两者不能混用。
- `observe()` 只能暴露公开 payload，不能暴露 `GameState`、`PlayerState`、`Action` 或其他 engine 私有对象。
- Botzone adapter 不能让 Agent 直接生成 Botzone 实体牌数组；实体 `[action, claim]` 必须由 provenance 映射生成。
- 当前 live profile 只支持无贡。`tribute`、`return`、非零 tribute 和未知阶段必须 fail-closed。
- Botzone URL、Header、match ID、手牌、prompt、response、reasoning、API key 和 Cookie 不得进入聚合 audit 或日志。
- state 与 audit 必须位于仓库外；每局使用隔离目录。运行 token 只接受 32 位小写十六进制。
- 清理完成后，`D:\VsCodeProject` 下只允许一个 Botzone 顶层运行目录 `D:\VsCodeProject\BotzoneWorkspace`；后续任务复用它，不再按 seed、pilot、pair 或 capacity 创建新顶层目录。清空旧内容必须在结果记录后、live 开始前作为独立任务执行。
- pending response/effect 只在 transport acknowledge 后提交；重发、重启或重复 acknowledge 不得重复扣牌。
- long-poll timeout 是 idle 事件；只有严格匹配的 timeout 计数/诊断才能被 benchmark 接纳。其他 transport failure 仍使样本无效。
- v8 audit、v4 tombstone 和预注册 token 必须一致；不具备可证明归属的证据不能进入正式配对聚合。
- DeepSeek 路径允许本地 shortcut；模型返回异常、无动作或非法 ID 时必须走受控 fallback，不能伪造合法动作。
- 不读取、修改或提交 `.env`、真实密钥、`logs/` 或 `archive_legacy/`。

配置事实：`integrations/botzone/runtime_config.py` 只读取 Botzone URL/state 两个指定变量；`config.AppConfig.from_env()` 会调用 `load_dotenv()`，开关并非由 `config.py` 自己处理。2026-09-01 只读复核确认项目 `.venv` 使用 `python-dotenv 1.2.2`，其 `load_dotenv()` 在创建解析器或读取 `.env` 前检查 `PYTHON_DOTENV_DISABLED`；系统 PATH 中的 Python 使用 `python-dotenv 1.1.1`，不具备该分支。因此禁用流程只在显式使用项目 `.venv\Scripts\python.exe` 时得到当前环境证据支持，裸 `python` 不属于受支持执行方式。

## 5. Current Task

长期目标仍包括在需要时取得条件可比、证据归属明确的真实 Botzone 无贡 RuleBased/DeepSeek 成对对局；但该目标已延期，不再阻塞算法优化。

期望容量在现有文档中定义为两个 seed × 四个本家座位，每个条件各运行 RuleBased 和 DeepSeek，共 8 对/16 局，AB/BA 平衡。这个容量目标是计划，不是已经完成的结果。

connector可读牌谱、普通人工RuleBased history smoke、两阶段候选评测、Botzone显式 `conditional_pressure_pass` wiring、trial validator、默认RuleBased两类保牌、DeepSeek危险对手pass阻断、自由出牌小手牌短序列守卫和队友小王后大王保留均已完成。DeepSeek失败fallback仍使用冻结旧静态基线。seed `47002`已完成真实对局但含2次HTTP error，真实条件化pass为0；其后只读策略审计没有得到新的高置信度缺陷。

seed `47003` 的单局DeepSeek采样已经完成connector与ACK trace闭环：11/11/11 request/response/Header、qualified finish=1、10条decision trace与audit守恒、history/trace均为`ok`，无transport failure。平台终局分类为`platform_error`，所以不能作为正常胜负结果；它不否定已通过binding、selected-action、ACK和provenance校验的逐决策证据。

strategy-intent接线已提交为`454a422`：Botzone DeepSeek factory启用现有router与prompt formatter，未新增后置动作覆盖。规划Codex独立复跑119项定向、39项主规则和709项全量通过；真实第9条公开输入经无网络factory复核得到ready的`support_teammate / teammate_controls_table`，fake模型的原始合法特殊牌仍保持`model`。

受约束执行报告将该固定决策的真实DeepSeek off/on复放判定为`strategy_intent_target_decision_improved`：off侧模型成功返回合法特殊牌，on侧模型成功返回合法pass；on侧意图为`ready / support_teammate / teammate_controls_table`，两侧使用独立Agent，总请求2、重试0，没有RuleBased替代或新增后置pass。规划Codex独立复核trace仍为88,983 bytes / SHA-256 `4ba2ea88a13046f8f7907df6dd124175dceee3a88e9723be88c6581a28bc3512`，仓库仍clean；模型响应按隐私契约未持久化，无法从artifact独立重演。该结果是目标决策的输入消融证据，不是整体胜率结论。

全10条trace及三个成功模型动作后置守卫的只读审计随后判定为`seed_47003_no_additional_high_confidence_candidate`。规划Codex使用当前生产代码独立复算，得到自由2、队友领牌4、对手领牌1、证据不足3，以及pass 5、ordinary 4、special 1；三个守卫对记录动作的触发数均为0。第9条只重复已完成缺口，其他记录不足以定义新的prompt/RAG修改，故seed `47003`分析封板。三个守卫均属策略覆盖而非协议安全，但在没有对应证据时不直接删除。

其后的`teammate_control_block`守卫前真实模型调用成功并返回`target_special`，但评测前提无效：复用的`tests/test_deepseek_step_e.py::_teammate_joker_legal_actions()`同时提供pass、大王和单张9，而当前引擎证明9不能压单张小王。该列表不是canonical legal actions。规划Codex据此把执行判定从`teammate_control_prompt_raw_model_not_ready`改为`teammate_control_prompt_raw_model_inconclusive`；本次调用不授权prompt/RAG修改，因此当时只安排修复测试fixture并锁定engine真值。

测试证据修正已提交为`8db3154`：目标小王场景现只含pass与大王两个canonical候选；原普通低价值动作非触发测试已迁移到队友普通单张8、本家以9合法压制的独立场景，并新增引擎真值回归。规划Codex独立检查两文件提交范围，复跑定向41项、主规则39项和全量710项通过，`git diff --check`通过，工作树clean；随后只对该canonical fixture做了一次新的守卫前真实模型检查，旧inconclusive调用未合并。

受约束执行报告将新的canonical检查判定为`teammate_control_canonical_prompt_raw_model_not_ready`：候选数2，intent为`ready / support_teammate / teammate_controls_table`，RAG为`endgame / endgame`，唯一模型请求成功且原始选择为合法大王；结果在后置守卫前捕获。模型响应按隐私契约未持久化，但规划Codex独立确认提交、fixture、引擎真值与Git clean。当前可复现缺口是strategy-intent只表达泛化“队友当前控桌”，没有表达小王→大王的高价值资源代价和无紧急阻断需要。下一任务只实现共享公开判定驱动的专用prompt reason，不改RAG或后置动作行为。

专用prompt改进已提交为`24fb362`。新增`teammate_big_joker_opportunity()`在模型选择前只从公开observation与canonical legal actions识别原始pass/大王机会，既有后置守卫改为复用它；router新增`teammate_big_joker_preservation` reason，prompt增加小王控桌、pass合法、不能直接出完、无紧急对手及保留大王的策略意义。RAG、engine、Botzone协议、audit、observability与守卫优先级/范围未改。规划Codex独立检查8文件diff并复跑83项定向、39项主规则、712项全量及`git diff --check`，全部通过。

其后的单次canonical真实模型复放判定为`teammate_big_joker_prompt_raw_model_improved`：两个候选与共享机会判定均成立，intent为`ready / support_teammate / teammate_big_joker_preservation`，RAG保持`endgame / endgame`；唯一模型调用成功、重试0，后置守卫前原始选择为合法pass。仓库与workspace未修改。该结果支持下一任务退役`teammate_control_block`主动改写，保留专用prompt和共享机会真值；旧source只保留必要的持久证据读取兼容。

L5-A4h11a partial manifest、seed `45001` evidence、seed `47001` prestart evidence、seed `47002` evidence与已完成审计的seed `47003` evidence均已移入Windows回收站；未永久删除或清空回收站，无残留connector。

seed `45001` 的普通人工 RuleBased history smoke 已完成并通过独立复核：15/15/15 请求闭环、qualified finished 1、14 次 rule primary、零 model/fallback、exit 0、`history=ok`，stderr 空。最后不完整观测段的显示语义与标题格式均已修复，并经16/54/643项独立复跑通过。

14次本家决策审计确认修改前 RuleBased 的首个候选机制：它无条件排除 pass，因此在跟随对手且可用压制全为炸弹类时也不会保牌。真实两手动作因缺少当时完整 legal actions 只能作为线索。候选已在固定级牌2的同状态 one-step 与整局重复触发 trial 上满足 retain 门槛，并已于 `150006a` 合入默认RuleBased；不再追加跨级牌容量。

seed `47001` 已使用且不得复用。项目所有者确认页面一直显示“未连接”，所以游戏从未开始；audit的2次timeout与0 request只说明调用以timeout结束，不能证明页面已连接。该次没有Agent决策、state或history，不能评价条件化策略。其evidence现已回收。后续普通人工live的顺序已经固化进 `AGENTS.md`：先启动唯一connector并确认页面已连接，再分配seed、创建/配置桌。

seed `47002`也已使用且不得复用。页面连接门槛先通过，对局随后exit 0 / `finished_target`并形成17/17/17、qualified finish、v4/v8归属和可读history；但2次 `http_error`使严格零故障smoke标签不成立。16次决策均为 `conditional_rule_based`，真实候选pass未激活。这是非激活runtime兼容性证据，不是候选胜率或激活证据。

seed `47002` 后续只读策略审计确认：16次决策中14次可按公开语义重建，9次pass均只有pass合法；两个可精确比较的自由出牌点不存在严格更优的残余分组。第1、6次缺少足以唯一恢复canonical动作的声明/载体细节。结论是现有evidence不足以支持下一项算法修改，不得据此猜测新规则。

决策证据实现已最终提交为 `045fb75`。五个历史反例全部转绿：fresh输出前置拒绝、跨recorder随机持久binding、Agent深隔离、observation/top-level legal actions强一致，以及history-only direct CLI旧路径兼容。规划复跑88项定向、39项主规则和707项全量通过；当前范围内无已知剩余风险。

seed `47004` 的三处策略观察已经由规划Codex从trace和生产代码独立分因：同点数四/五张炸弹均对模型可见但现有prompt没有残余孤张取舍；自由首出Q来自开局公式local shortcut而非模型，缺陷就是Q这一首攻自身——清理孤张应优先不拆结构的低牌，低成本试探也应优先10或更低的可牺牲普通单张，并保留更高单张的残局牌权机会；对3存在于原始合法集合，却因free-lead transition剪枝在有single时完全不保留pair而对模型不可见。下一任务只修剪枝、开局公式和公开残余结构输入，不恢复任何后置策略改写。

该修正方向随后上提为策略来源重建。规划Codex确认现有经验RAG与开局公式没有可追溯的人类经验来源或权重校准；`docs/STRATEGY_SOURCE_AUDIT.md` 已将官方规则、具名专家/正规出版物、弱来源转载和学术架构资料分层。后续不再按Q、4、10等单点动作追加神秘分数：确定性公式只承载来源清楚、范围明确、fixture稳定的少数定式，证据不足时退出给RAG+DeepSeek；剪枝保持牌型高召回。经验正文只保留纯策略知识和语义标签，作者、书目、URL、来源等级与激活状态由独立治理registry关联，不得参与检索或进入模型prompt。

`5dbdd2c` 已完成上述 H3-A0 主体，但规划复审发现 pair 修复只停留在第一层剪枝。最终 `_limit_prompt_actions()` 在 critical 数量达到 80 时会返回全部 critical，真实引擎初始局面可同时出现最终候选超过 80 且自然 pair 全部消失；已知 seed `47004` 同样复现该低敏结论。因此知识/治理隔离、窄开局定式和炸弹结构输入可以保留，H3-A0 整体仍需 H3-A0a 修复最终预算与 pair 召回后才能封板。

项目所有者随后批准 H3-A1 的 DeepSeek 中心策略方向：本地层负责候选、公开结构、场景/目标、来源经验和模型前推荐，DeepSeek 保持最终策略裁决；开局公式只作为延迟约束下的窄高置信快速路径及可供模型验证的推荐，不扩张成第二套完整策略 AI。H3-A1 将以十个策略域批量覆盖开局、结构、控制、牌权、协同、阻断、炸弹/通配、残局和不确定性，不再按单个现场动作追加神秘分数。provenance 治理字段继续与知识平面隔离。

## 6. Confirmed Symptoms

### Historical formal batch summary

截至 2026-09-03 清理执行前，以下目录曾实际存在：

```text
D:\VsCodeProject\BotzoneVerifiedUiCapacity-42001-42002
D:\VsCodeProject\BotzoneVerifiedUiCapacity-43001-43002
```

只读核对结果：

- `capacity-manifest.json`：4661 bytes，SHA-256 `5989a6dc07441c94b02725a31b29706d9708311ce7eee597e82b96b47921b4ff`。
- `preflight-summary.json`：2273 bytes，SHA-256 `32a9cf1adfdc881037aea6adb8f594a51876a958df88fc0a4432ddf55370cad9`。
- `progress.json`：状态 `invalid`，completed=0，next=1，failed=1，failure stage=`ui_readback`。
- game 1 completion audit：v8、exit 130、`interrupted`、cycles=4、request/response/Header=`0/0/0`、qualified finished=0、transport failure=0、transport timeout=4、agent mode=`rule`。
- 16 个 state 目录当前均无 state 文件。
- 该目录中没有成功完成的正式 pair。

`43001/43002` 只读核对结果：

- `capacity-manifest.json`：4661 bytes，SHA-256 `e98e60423dea922f1ae5454edd847ea8210798a345ad13ffabc8fb343fc0dea6`。
- `preflight-summary.json`：2273 bytes，SHA-256 `207b6408642c1e85ec850c929304fcf5f3e0cc08f82ec844f0977dff45890f42`；双模式零网络 preflight 均通过。
- `progress.json`：284 bytes，SHA-256 `2a4dc0140a2bb406021add3e4af725ce39af93c06267bc6d7734b7c0c1010abc`；状态 `invalid`，completed=0，next=1，failed=1，failure stage=`lobby_gate`。
- 页面在配置写入与 connector 启动前进入 `?msg=destroyed`，可见“游戏桌被房主关闭了”。
- connector、Agent、DeepSeek/model 调用均为 0；16 个 game 目录存在，state/audit 文件总数为 0/0，无残留 connector。
- 正式 root 创建时 HEAD 为 `08962800af7c47779b1435dcac97c8de17471e0f`，正式批次期间仓库保持冻结。

项目所有者随后明确授权清理 `D:\VsCodeProject` 下全部 21 个本任务形成的 `Botzone*` 顶层目录，包括上述两组 formal evidence。L5-A4h10a 已把它们全部移入 Windows 回收站；原路径不再存在，但在回收站清空前仍可由项目所有者恢复。本节记录的状态、大小和 SHA-256 只作为历史摘要。

清理完成后，`D:\VsCodeProject\BotzoneWorkspace` 已再次被独立复核为唯一直属 `Botzone*` 目录、普通非链接，且递归精确只剩空的 `audit/`、`state/`、`streams/`；当前状态应以第 5 节的最新 inventory 为准。

### Functionality known to work

仓库文档记录过以下成功运行结果：

- 一次人工无贡 DeepSeek connector：12/12/12 request/response/Header，qualified finished=1；10 次模型尝试均 success，fallback=0。来源：`docs/PROJECT_STATUS.md` 的 L5-A3c。
- 一次自动 UI RuleBased pilot：34/34/34，qualified finished=1，33 次 `rule_primary`，v8/v4 provenance 一致。来源：`docs/PROJECT_STATUS.md` 的 L5-A4f7。
- 一次 selected-seat 单对只读恢复聚合有效，但两侧均为负且分数相同。来源：`docs/PLAN.md` / `docs/PROJECT_STATUS.md` 的 L5-A4g2。该结果不是策略收益证据。

这些结果证明单局 connector、模型动作进入响应和单对聚合路径曾分别成功；它们不证明完整 8 对容量能够可靠执行，也不证明 DeepSeek 优于 RuleBased。

## 7. Verified Facts

- `GuanDanGame.step()` 拒绝不在当前 action map 中的 ID。来源：`engine/game.py`、`tests/test_game_flow.py`。
- `BaseAgent` 契约只返回 action ID；`require_legal_action_id()` 再次验证 ID。来源：`agents/base.py`。
- `DeepSeekAIAgent` 在模型前执行 only-pass、一次出完和可选开局公式 shortcut。来源：`agents/deepseek_ai.py::select_action()`。
- connector 的 DeepSeek 组合继续关闭confidence prompt，但已由`454a422`启用strategy router shadow与strategy-intent prompt。来源：`integrations/botzone/agent_runtime.py::build_agent_factory()`。
- DeepSeek client wrapper 只保留合法 action ID，丢弃自由文本 reasoning，并分类 success/timeout/exception/invalid_suggestion。来源：`integrations/botzone/agent_runtime.py::_StrictDeepSeekClient`。
- adapter 会对 Agent 返回类型、合法 ID 和 provenance 分别 fail-closed；DeepSeek 外层 fallback 仍必须返回合法 ID。来源：`integrations/botzone/play_adapter.py::NoTributeRuleBasedHandler`。
- transport 只发 HTTPS GET，拒绝重定向，限制响应大小，并用固定类别脱敏错误。来源：`integrations/botzone/http_transport.py`。
- run-token 模式生成 session/tombstone v4 和 audit v8；默认兼容 v3/v7。来源：`integrations/botzone/run_provenance.py`、`session.py`、`runner.py`。
- benchmark 要求成功终止、request=response=Header>0、qualified finished=1、正常结果=1、无真实 transport failure，以及 Agent/model/result 守恒。来源：`evaluation/botzone_policy_benchmark.py::_validate_audit()`。
- benchmark 可接受唯一、计数严格匹配的 idle timeout diagnostic，但拒绝混合诊断或真实 transport failure。来源：同上及 `tests/test_botzone_policy_benchmark.py`。
- `RuleBasedAIAgent` 当前不读取 observation；存在任一非 pass 时排除 pass。最小 `pass+bomb` 与 `pass+straight_flush` 输入均稳定返回非 pass。来源：`agents/rule_based_ai.py` 与2026-09-05只读诊断。
- `evaluation/conditional_pressure_pass.py` 已分开校验完整 legal/table action 与六字段 history row，并只核对二者共同语义。seed `46000` 的真实 public API 回归证明 baseline 选 bomb、candidate 选原始 pass ID。
- 原 `46000..46199` one-step benchmark 两次完全一致：686次机会、617个 changed pairs、candidate/baseline/tie=`191/172/254`、score=`635/619`、名次和=`3053/3079`、零失败/diagnostics；唯一判定 `retain_conditional_pressure_pass_for_runtime_trial`。
- 新 `46200..46399` 整局 trial 两次完全一致：400/400局、197 active pairs、1433次 pass、candidate/baseline score=`422/378`、名次和=`1966/2034`、pair=`73/53/74`；判定 `retain_conditional_pressure_pass_for_botzone_opt_in_smoke`。该结果仍不证明真实 Botzone 胜率。
- trial的pair/game、W/D/L互补、rank/diagnostic、非空容量、active/pass、单方名次范围和digest均已封口；真实两套report/hash不变。
- Botzone显式mode已接通并以 `conditional_pressure_pass` / `conditional_rule_based` 低敏source守恒；正式RuleBased/DeepSeek benchmark拒绝混入conditional audit。
- 当前全量测试：718 项通过。命令：`.venv\Scripts\python.exe -m unittest discover -q`，Python 3.11.9。
- 当前 decision-trace/Botzone 定向：88 项通过；engine主回归：39项通过。精确命令见 `docs/TESTS.md`。
- 当前 benchmark 定向测试：13 项通过。命令：`python -m unittest tests.test_botzone_policy_benchmark -q`。
- 当前 engine 主回归：39 项通过。命令：`python -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q`。
- 当前 preflight 输出定向测试：5 项通过。命令：`.venv\Scripts\python.exe -m unittest tests.test_botzone_preflight_output -q`。
- `git diff --check` 通过。
- 2026-09-03 独立 Edge 排障：Edge 正在运行；ChatGPT Edge 扩展已安装且启用；native-host manifest、注册表路径和允许 origin 均正确；`edge.user.openTabs()` 成功。现有 Botzone destroyed 标签在重新绑定时被报告为属于另一个浏览器控制会话。

## 8. Unverified Hypotheses

- **UNVERIFIED / DEFERRED:** `?msg=destroyed` 是由无操作超时、某个页面动作、房主/平台状态还是其他 UI 生命周期条件触发；自动建桌路线已停止，不再作为当前任务。
- **UNVERIFIED / DEFERRED:** 旧标签的浏览器会话占用是否就是上一轮 Playwright locator 超时的原因；项目所有者改为手工建桌后不再继续此诊断。
- **UNVERIFIED:** UI 自动化是正式容量采集唯一剩余的失败来源；progress、平台状态、长轮询和人工验证码仍可能影响批次。
- **VERIFIED:** 人工建桌、connector 就绪后人工点击开始的新交接顺序已在 seed `45001` 完成一局并形成可归属 history/audit/state/streams evidence；这不证明每次都不会受平台状态影响。
- **UNVERIFIED:** 上一执行报告所称 PowerShell 参数不兼容的精确命令与根因；报告未提供足够错误细节。
- **UNVERIFIED:** 首次 formal preflight 的具体失败断言；报告未提供 return code 或 stdout/stderr 捕获值。当前代码测试支持 LF/CRLF，两者不能仅凭猜测归因为旧验证器误判。
- **UNVERIFIED:** DeepSeek 相对 RuleBased 存在动作质量、因果效果或胜率提升。
- **CONFIRMED（受约束执行报告 + 本地完整性复核）:** seed `47003`第9条固定决策中，off侧真实模型选择合法特殊牌，on侧在队友控桌意图提示下选择合法pass；trace bytes/hash与Git未变已独立复核，模型动作对照因隐私契约不持久化而不能从artifact重演。该证据支持公开上下文改善了目标决策，不外推到其他决策或胜率。
- **VERIFIED（本地 proxy）:** 条件化炸弹资源保留 pass 在修复后的 one-step 与整局固定 seed 评测中均满足预设 retain 门槛，且两次运行结果确定一致。
- **UNVERIFIED:** 该候选在真实 Botzone 对局中是否会触发，以及是否改善长期真实胜率；下一次单局 smoke 只验证 opt-in 路径，不回答长期胜率问题。

已从未验证项移除 dotenv 禁用流程：项目 `.venv` 的依赖实现已只读确认支持该开关；该结论不适用于系统 PATH 中的其他 Python。

## 9. Failed Approaches — Minimal Record

- L5-A4h1 至 L5-A4h11b 的共同流程问题已经确认：**把每一个可以原地修正的准备阶段小错误，都升级成不可恢复的正式实验失败。** 具体故障包括 manifest/fsync、progress schema、命令解析、serializer 分叉、浏览器控制、workspace 准备和 preflight 捕获。它们不是同一个代码 bug，但都说明正式实验边界启用过早、编排层和实验层没有分离。未来恢复正式实验时应保留这些失败记录，并把零外部副作用的准备错误留在可修正 qualification 层。
- connector 已由多次真实完整对局证明可用；上述失败不能概括为 connector 不稳定。严格 16 局 capacity 现已延期，直到存在离线验证有收益的候选算法。

- 自动 `runmatch` 建桌曾产生无法完成归属或闭环的运行；没有形成有效 benchmark。该路线没有删除 connector 代码，但后续正式测试改用网页桌。
- 多个早期容量批次因桌面条件不匹配、进度/evidence 契约或 UI 生命周期失败而停止。相关代码缺口中的 idle timeout 和 run provenance 已由提交 `569d543`、`45d34f0` 修复；旧批次 evidence 按各自文档状态封存。
- `42001/42002` 正式批次在 game 1 提交前的 UI readback 阶段停止，completed=0。目录保持只读，没有恢复或重试。
- `43001/43002` 正式批次在 game 1 / `lobby_gate` 停止，completed=0；页面在配置和 connector 前显示房主关闭。该症状与历史 `33001` 的预提交 UI 生命周期失败同类，但两次都没有足够动作证据确认根因。
- L5-A4h9 只读到任务开始前的 destroyed 标签，随后 locator 超时；新桌和页面写动作均为 0。因此它没有形成新的生命周期结果，执行报告中的 destroyed 判定不作为规划事实，改记为前置 locator 不可用。
- 原定 L5-A4h9a 的新标签 locator 资格尚未执行即由项目所有者取消；以后由项目所有者手工建桌，不再投入任务恢复自动 Edge 操作。
- L5-A4h10 的永久递归删除在启动前被执行环境策略拦截；安全门槛全部通过，但删除和目录创建均为 0。不得使用其他永久删除 API 绕过；下一步只尝试回收站式可恢复清理。
- L5-A4h10a 已将 21 个旧目录移入 Windows 回收站并建立唯一空的固定 workspace；原始 evidence 不再位于原路径。
- L5-A4h11 在首个 workspace artifact 前因笼统的 PowerShell 参数不兼容停止；独立复核 workspace 仍为空，preflight/connector/table/network 为 0。该结果重分类为 preparation precondition failure，不消耗 `44001`。
- L5-A4h11a qualification 与 manifest 成功，但 formal preflight 严格验证失败；manifest 已锁定，state/audit 仍空，未请求建桌。当前只允许诊断后的一次 formal recovery。
- 牌谱完成并决定退役旧 formal recovery 后，manifest 清理任务的全部只读门槛通过，但精确非递归永久删除命令仍在实际执行前被命令级安全策略拦截。授权本身有效；该结果不得误报为授权缺失，也不再继续尝试永久删除。恢复动作改为精确的 Windows 回收站式单文件移动，不清空回收站。
- 回收站式恢复动作随后成功：旧 manifest 原路径不存在，workspace 只含空 `audit/` 与 `state/`；清理工作已完成，不再是当前阻塞项。
- seed `45001` history smoke 随后成功。牌谱的6轮只是6个已观测牌权段；本家在最后一段出完后不再收到请求，finished row 又不含完整尾部，所以不能据此声称裁判整局在第6轮结束。原“第6轮结束后的手牌”展示语义已经修复。
- 该展示语义与新标题空格均已完成修正并通过16/54/643测试；不再是当前待办。
- 文档曾在通用 Windows Computer Use 与 Edge 浏览器扩展之间切换。提交 `0896280` 只修改了文档；后续已证明 Edge family 可绑定，但没有证明它能维持建桌表单或完成正式容量。

## 10. Files Relevant to the Current Problem

- `docs/CLEAN_HANDOFF.md`：本交接事实基线。
- `docs/NEXT_PROMPT.md`：当前计划草案；不是实现事实或已验证方案。
- `docs/PROJECT_STATUS.md`：已记录的里程碑与 live 结果索引。
- `docs/BOTZONE_INTEGRATION_PLAN.md`：Botzone 范围、协议差异和历史阶段。
- `docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`：规则与架构硬边界。
- `integrations/botzone/__main__.py`：connector CLI、preflight、agent 选择、audit 写入。
- `integrations/botzone/runner.py`：前台生命周期、停止条件和 v7/v8 audit。
- `integrations/botzone/connector.py`：poll、session、response Header 和 finished 处理。
- `integrations/botzone/session.py`：持久 session、pending/ack、history merge 和 tombstone。
- `integrations/botzone/play_adapter.py`：公开局面投影、Agent 调用、provenance 和 action/claim 编码。
- `integrations/botzone/agent_runtime.py`：RuleBased/DeepSeek 组合与 fallback。
- `integrations/botzone/http_transport.py`：长轮询传输和 timeout 分类。
- `integrations/botzone/run_provenance.py`：v4/v8 token 契约。
- `integrations/botzone/agent_observability.py`、`result_observability.py`：低基数聚合守恒。
- `evaluation/botzone_policy_benchmark.py`：正式/selected-seat 赛程与 pair 聚合。
- `agents/rule_based_ai.py`：当前最小规则 AI；存在非 pass 时排除 pass，且不读取 observation。
- `evaluation/pass_policy_benchmark.py`：历史 evaluation-only 宽泛战略 pass 轨迹载体；相关正式结果拒绝的是牌面推断信号，不是策略 outcome。不可直接把该结果当作当前质量证据，也不宜改名覆盖原语义。
- `evaluation/confidence_action_quality.py`、`evaluation/strategy_intent_action_quality.py`：已有同状态双分支 RuleBased rollout 与团队结果/名次和比较口径。
- `tests/test_botzone_policy_benchmark.py`：当前 benchmark 的最直接契约测试。
- `tests/test_botzone_connector.py`、`test_botzone_session.py`、`test_botzone_play_adapter.py`、`test_botzone_deepseek_agent_runtime.py`：connector 主链测试。
- `config.py`：DeepSeek 配置和实际 dotenv 加载行为。
- 仓库外运行目录（当时快照）：当时唯一顶层目录为 `D:\VsCodeProject\BotzoneWorkspace`，递归只有三个空目录、文件数0；seed `47003` evidence已在审计后移入回收站。最新状态以文首链接为准。

## 11. Tests and Reproduction

### Deterministic local checks

```powershell
python -m unittest discover -q
python -m unittest tests.test_botzone_policy_benchmark -q
python -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q
git diff --check
```

当前最新独立结果为：strategy-intent/DeepSeek/Botzone相关119项、engine主回归39项、全量709项通过，`git diff --check`通过。更早的decision-trace相关88项、runtime-trial validator单文件8项、条件化相关28项与四个固定SHA-256也已独立复核，不因本阶段改变。

### Minimal reproduction of the current failure state

当前问题不是一个失败的本地单元测试。旧 batch 原始路径已被清理，历史结果只能从本交接及 `docs/PROJECT_STATUS.md`、`docs/PLAN.md` 的低敏摘要复核。

当前 H3-A0 业务检查点为 `5dbdd2c`。规划复审运行197项相关定向、39项主规则和717项全量均通过；知识/治理隔离、来源激活、开局窄定式、炸弹结构摘要及模型动作保真未发现回归。当前失败状态不是规则或协议测试失败，而是最终候选层仍可能突破80项并重新移除全部自然pair。

H3-A0a 已由 `66009fc` 修复并独立复审：原6个真实引擎复现样本的第一层候选为132–243项，最终均为80项且保留natural single和稳定最小natural pair；500个独立初始局面性质检查同样通过。相关230项、主规则39项、全量720项均通过。当前不再存在已知候选预算/pair召回阻塞。

## 12. Working Tree Status

- 分支：`cao`。
- 已验证基础实现检查点：`150006a feat: add observed history and pressure-pass strategy`。
- 队友保炸弹检查点：`5daf326 feat: preserve bombs behind teammate leads`。
- 危险对手阻断检查点：`fb3d791 feat: block passes against near-finish opponents`。
- 小手牌短序列检查点：`dc9638c feat: guard short free-lead endgames`。
- 最新算法检查点：`295b9b5 feat: preserve big joker behind teammate`。
- 最新检查点新增队友小王→大王守卫、`teammate_control_block`、双action-ID schema校验与对应测试；提交前由规划Codex独立运行相关65项、主规则39项和全量689项通过，并完成staged diff检查。
- 最新Botzone诊断检查点：`045fb75 feat: record acknowledged Botzone decisions`；提交前由规划Codex独立复现反例并运行定向88项、主规则39项、全量707项及staged diff检查。
- 最新DeepSeek提示检查点：`454a422 feat: enable strategy intent prompt for Botzone DeepSeek`；规划Codex独立检查三文件diff，复跑119/39/709项，并以真实第9条公开输入验证factory提示接线和模型动作自主权。
- 最新测试证据检查点：`8db3154 test: align teammate joker fixtures with rules`；规划Codex独立检查仅两份测试，复跑41/39/710项并确认生产文件零修改。
- 最新strategy-intent检查点：`24fb362 feat: prompt big joker teammate preservation`；规划Codex独立检查8文件diff，复跑83/39/712项，确认RAG、engine、Botzone协议及后置守卫范围未改变。
- 最新动作自主性检查点：`e30362f feat: retire teammate control action override`；核心退役路径经113/39/713项回归通过，但legacy v7/v8 audit的policy benchmark读取兼容尚未达成。
- 最新audit兼容检查点：`3ee6e0e fix: read legacy DeepSeek audit sources`；规划Codex独立复跑109/39/718项，legacy v7/v8正例可读且错误outcome反例fail closed。
- 最新危险对手覆盖退役检查点：`7499ccc feat: retire danger opponent action override`；规划Codex独立复跑132/39/718项，确认原始pass/9/J保留、旧source只读兼容且`short_endgame_plan`无漂移。
- 最新短残局专用提示检查点：`c32259d feat: prompt short endgame grouping`；规划Codex独立复跑92/39/721项，确认共享分组真值、专用prompt和最终输入验证生效，后置planner/source无漂移。
- 最新动作自主性封板检查点：`f426693 feat: retire short endgame action override`；规划Codex独立复跑134/39/718项，确认所有合法模型ID保真、三个旧source仅legacy可读且专用短残局输入未削弱。
- 最新策略来源重建检查点：`5dbdd2c feat: rebuild sourced opening strategy`；主体边界通过复审，但最终 prompt limiter 的硬预算和 natural pair 召回未通过，尚未封板。
- 最新候选召回封板检查点：`66009fc fix: bound DeepSeek prompt candidates`；规划 Codex 独立确认最终硬上限、natural single/pair、原始 ID、签名去重、稳定顺序及模型自主权，H3-A0/H3-A0a 封板。
- 本交接及其他Markdown由随后独立规划文档检查点封存。读取者应以实际 `git status --short` 判断现场，不使用历史静态清单推断未提交文件。
- Coding Codex负责提交其业务代码、tests及任务直接相关修改；规划Codex独立复核结果，只提交自己产生的 `AGENTS.md`、项目Skills和docs上下文修改，不代为提交未完成或未经复核的业务改动。

## 13. Do Not Assume

- 不要假设当前对话提出过的任何诊断正确。
- 不要默认沿用 `docs/NEXT_PROMPT.md` 最后选择的浏览器控制方案。
- 不要把规划文档中的未来步骤当成已实现、已运行或已验证。
- 不要把一次 connector 成功、一次模型 success 或一个有效 pair 当成策略优势。
- 不要把旧批次的失败自动归因于 connector、浏览器、Codex 权限、Botzone 或用户操作中的任何单一因素。
- 从当前代码、测试、实际文件和新运行的可观察行为重新建立判断。

## 14. Recommended Starting Point

H3-A1 组合实现已通过基础复审并合入 `cao`。最新独立结果为相关 212 项、主规则 39 项、全量 732 项；30 局真实引擎离线探针覆盖 2730 个状态、零异常，十域与全部 11 条 active 经验均有生产路径可达证据。但后续 H3-A2 资格检查证明 recommendation 与实际模型候选未形成闭环，因此不能把“域可达”解释为“建议必然进入最终 prompt”。工作区状态仍必须以实际 `git status --short` 为准。

H3-A2r 低敏ledger位于 `D:\VsCodeProject\GuanDanH3A2Audit\h3-a2r.jsonl`，7270 bytes，SHA-256 `32ec0dcbf7709ff30702fc85f5aae0c0c2aabfbb197fb223ebeb4823d9f0a63a`；规划Codex已复核27条事件、请求/结果和汇总守恒，并独立复跑23/23指定回归。其后进入H3-A3离线模型前对照纠错，不重新运行八场真实请求、不运行Botzone/connector/live，也不读取seed `47004` evidence。现有单点结果不构成胜率结论。

`b40000e` 已实现H3-A3关系识别与prompt对照，规划Codex独立通过30/39/747项测试，合法模型动作ID/source与历史边界未漂移。但30个不同初始局面中30/30将自然对子/单张关系放在推荐最前，其中29个另有安全自然小单；100个初始局面里的18个四/五炸关系虽都在最终候选及prompt可见，0个被完整推荐，因为普通对子关系先占最多3项预算。故H3-A3的模型前范围当时未封板，转入H3-A3a离线推荐优先级收窄。仓库外H3-A2r ledger和Coding任务报告的系统Temp流文件均保留，不因本规划复审清理。

`b670753` 已修复H3-A3的推荐优先级外溢，规划Codex独立通过32/39/749项测试。100个真实引擎初始状态中，推荐预算100/100合规；前30个自然对子关系均存在但占推荐前两位0/30，另有安全自然小单29/30；18个四/五炸关系均完整进入推荐、最终候选和prompt。H3-A3/H3-A3a离线范围封板。当时规划的H3-A4低敏真实模型诊断需先八场资格、再最多8请求/0重试；原H3-A2r ledger与系统Temp文件均保持原样，不接触Botzone workspace或seed `47004` evidence，不把类别变化直接当因果收益。

H3-A4已在网络前依门槛停止，不能称为真实模型探针完成。规划Codex独立核对新低敏`D:\VsCodeProject\GuanDanH3A2Audit\h3-a4.jsonl`为3209 bytes、SHA-256 `033107dcd2fb1b242a0cf824a4ec453cee77c494920a8101b1acd0b6944dc54a`，11条事件记录八场资格全部failed、`qualification_complete=false`、真实请求/重试均0。ledger只给出各场候选数0，没有逐阶段失败码；相关32项回归通过，当前引擎两个合成关系场景可生成非零合法候选及ready推荐，因此不能据此宣称生产回归。旧H3-A4 ledger封存不覆盖。当前执行`docs/NEXT_PROMPT.md`的H3-A4q：仅实现与验证可重复的八场engine-backed离线资格场景及固定失败阶段；独立复审8/8后才另立fresh-ledger真实模型诊断。原H3-A2r ledger、Botzone workspace、seed`47004` evidence与系统Temp文件均保持原样。

`c87defa`已建立八场固定engine-backed资格工具，规划Codex独立复跑35/39/752项测试通过，最终候选数6/5/4/6/3/3/4/25；禁网真实DeepSeekClient组装路径与工具当前八场prompt、原始ID/source对照相等。但资格API对空RAG scene/hits的无网络反例仍有六场返回`ready`，没有实质检验RAG层；fake client还绕过了实际最终客户端组装。故当前不放行真实模型请求。`docs/NEXT_PROMPT.md`已转为H3-A4q1离线纠错：仅补RAG/intent/最终组装的可失败门槛与反例，规划复审通过后再单独发起fresh-ledger真实诊断，不修改旧ledger或Botzone证据。

`b229371`已用真实DeepSeekClient禁网transport与RAG scene/hits阶段收紧资格，规划Codex独立复跑39/39/756项通过；八场正例ready，空/错配RAG八场固定失败。但规划Codex注入仅在`_build_structured_prompt()`返回时删除`【模型前建议】`、保留客户端预先记录的`final_prompt`，transport实际接收的请求缺该区块，资格仍误报ready。这是离线资格工具的请求体绑定缺口，生产策略尚无对应反例。下一项`docs/NEXT_PROMPT.md`为H3-A4q1a最小纠错：在禁网transport内捕获实际请求正文，仅以其与记录的候选/prompt及唯一调用次数守恒判定ready；不读旧ledger，不启动真实模型或Botzone。

`81506f8`已封住请求体绑定缺口。规划Codex独立复跑相关40项、主规则39项、全量757项；八场固定离线资格全部ready，最终候选数6/5/4/6/3/3/4/25；单独篡改实际Request user prompt而保留记录prompt的无网络反例固定落在`request_binding`。完整提交只改`evaluation/h3_model_probe_fixtures.py`及对应测试，生产策略未变。H3-A4q组合离线资格门槛封板。当前执行`docs/NEXT_PROMPT.md`的H3-A4r独立真实模型诊断：先全数离线资格，再最多8次/0重试，fresh仓库外低敏ledger；旧H3-A2r/H3-A4 ledger、Botzone workspace、seed`47004` evidence及系统Temp文件均保持原样。

H3-A4r已形成可审计单点技术结果：规划Codex独立核对fresh普通非链接ledger`D:\VsCodeProject\GuanDanH3A2Audit\h3-a4r.jsonl`的5461 bytes、SHA-256`e5e3e2f2ab724ca809af01ef7e513d56974eace0ee5a40fafcb5e95b96f60c51`、27条固定事件及8组连续请求起止；8次success、0重试，八场候选/source守恒。原始类别依序为`alternative / low_cost_single / other / other / pass_preserve / block / minimum_group / spend_resource`，不等于胜率或配对改善。当前HEAD离线资格重跑与ledger计数一致。但八个fixture都被公开phase分到残局，`low_cost_single`不是开局；`neutral_soft_pair`渲染的是炸弹C级条目而非对子C级条目，且该局无炸弹/通配候选。下一项`docs/NEXT_PROMPT.md`为H3-A5离线知识适用性与场景语义纠错；不据这次类别直接改模型prompt或恢复后置覆盖，不读写旧ledger、Botzone workspace或seed证据。

`6ff6d97` 的 H3-A5 来源经验适用门槛已由规划 Codex 独立复审：完整 canonical 候选驱动的炸弹/通配与自然对子激活、知识字段白名单隔离、八场禁网资格均 ready；相关39、主规则39、全量760项通过。两项目标场景已公开分类为 `lead_opening / opening` 并实际投影对子 C 级来源，但其 `step_no=0` 时手牌为 `18/16/16/16`、总数66，非真实完整开局。故下一项 `docs/NEXT_PROMPT.md` 是 H3-A5b：仅修两项评测 fixture 的108张/每家27张或合法回放可达性并重跑离线资格；此前不启动新真实模型诊断。旧 ledger、Botzone workspace、seed证据均保持原样。

`13b9817` 已完成 H3-A5b，规划 Codex 独立审阅提交、复跑57项相关与762项全量测试。两项开局 fixture 现在均为完整108张双副牌、四家各27张、第0步空历史；八场禁网资格均ready，最终候选数按顺序为6/21/4/50/3/3/4/25，source均为`model`。下一项`docs/NEXT_PROMPT.md`为H3-A6：独立最多8次、重试0真实DeepSeek低敏单点诊断，新fresh ledger；旧H3 ledger、Botzone workspace、seed证据与系统Temp文件保持原样。结果只解释当前fixture的单次选择，不推断旧版同状态改善或胜率。

H3-A6 已有可审计低敏结果：规划 Codex 只读核对 `D:\VsCodeProject\GuanDanH3A2Audit\h3-a6.jsonl` 为普通非链接文件、6730 bytes、SHA-256 `7cb3dd76198929871484a03c44dcb12c362082b3915fe70d8914ae727de863bc`；27条事件与当前HEAD八场离线资格、8对请求起止及summary守恒，账本为8 success、0重试、8个候选/source守恒。指定45项测试独立通过。类别依序`alternative / low_cost_single / other / single / pass_preserve / block / minimum_group / spend_resource`，不能从中还原具体动作或断言策略优劣。下一项`docs/NEXT_PROMPT.md`为H3-A7零网络同状态动作质量代理；旧H3 ledger、Botzone workspace、seed证据和系统Temp文件不清理。

H3-A7 `cb262c5` 已交付六状态零网络同局面动作质量代理。规划 Codex 审阅完整提交，独立复跑相关41项、主规则39项、全量775项，并执行未打桩的六组分支续局：6/6完成、参考动作6/6进入最终候选。两个开局、中局两个、残局族两个均从完整108张单局取得；比较仍只是冻结RuleBased后续策略下的终局/名次代理。当前评测尚以禁网假provider提供ID，未封住真实模型Request、最终候选、原始响应和续局首步的绑定。下一项`docs/NEXT_PROMPT.md`是H3-A7a零网络评测接线与反例测试；独立复审前不做真实模型质量请求，不清理旧ledger或Botzone evidence。

H3-A7a `6e304dc` 已完成零网络真实客户端 transport 接线：规划 Codex 审阅完整提交，独立通过相关46项、主规则39项、全量780项。六个固定样本由禁网假 transport 完成实际请求体/SSE/客户端 ID/source 绑定和未打桩本地续局，报告字节级复现；故障反例固定 fail closed，生产策略未变。下一项`docs/NEXT_PROMPT.md`为H3-A8独立真实模型同状态代理：先六场离线资格，后最多六次/重试零请求，fresh低敏ledger同步审计，遇技术失败即停。不读写旧H3 ledger、Botzone workspace或seed证据；代理结果不是胜率真值。

H3-A8 低敏新ledger `D:\VsCodeProject\GuanDanH3A2Audit\h3-a8.jsonl` 已由规划 Codex 只读核对为5700 bytes、SHA-256 `2fe5525ffe17e1fe5b7335f43fe96d0df878851ec627e81dbd6d342bb1f74a3d`，21条事件的六项资格、六对请求起止、六次success/零重试和summary守恒。当前HEAD独立重建六样本phase/候选数，相关46项及主规则39项通过；终局/名次和代理重算为3 `selected_better`、3 `tie`，没有`reference_better`或`unevaluable`。此结果不是胜率，也不能独立核对网络侧计数或具体动作。下一项`docs/NEXT_PROMPT.md`是H3-A9独立状态队列与至多六次真实模型复核；旧ledger、Botzone workspace及seed证据不触碰。

H3-A9 `6b8bd48` 独立六状态队列已由规划 Codex 复审：当前HEAD重建 seed 920–925 的公开phase/候选数与低敏ledger一致；相关51、主规则39、全量785项通过。`D:\VsCodeProject\GuanDanH3A2Audit\h3-a9.jsonl` 为5724 bytes，SHA-256 `1b374e75a4d034bf1b4a480066867308d0ac75e5d8fc4f718889579c7e0b5fd1`；最终21条事件记录六次success/零重试，比较重算为1 `selected_better`、2 `reference_better`、3 `tie`。执行方披露零网络准备阶段曾移除过早写入的summary，最终文件无法审计这段准备历史；只把它作为客户端侧最终结果账本，不作为不可改写或网络侧独立证明。H3-A8/A9方向混合，下一项`docs/NEXT_PROMPT.md`为H3-A10零网络穷举候选的代理区分度校准，不修改生产策略、不读旧ledger或Botzone evidence。

H3-A10 `ce1a370` 已由规划 Codex 审阅并独立重跑30/39/792项测试及未打桩校准：12个冻结状态的235个最终候选全部完成，参考动作12/12可见；相对同一RuleBased参考的优/平/劣为32/102/101，10个状态有严格差异，2个状态全平。没有生产策略、网络或现场修改。该结果只证明冻结续局代理能区分一些候选，不验证真实策略优劣；旧H3-A8/A9 ledger缺模型动作ID，无法回填其具体排名。当前`docs/NEXT_PROMPT.md`转为H3-A11零网络续局敏感性检查，使用已有FrozenRuleBased作为第二续局，不读取旧ledger或Botzone证据。

H3-A11 `e2b5e43` 由规划 Codex 独立通过相关36、主规则39、全量798项，直接重算总转移矩阵`22,6,4；30,64,8；36,33,32`、两种续局各235/235完成、117次标签改变、40次严格优劣反向；197个候选分支和739个去重公开状态出现真实策略选择差异。此结果使冻结RuleBased续局代理不适合作为生产策略优劣门槛；旧H3-A8/A9低敏结果保持描述性，不追改。项目所有者选择先复盘已有seed`47004`单局证据。固定workspace的六份文件大小/哈希经规划Codex只读复核与既有inventory一致，尚未读取正文或清理。`docs/NEXT_PROMPT.md`现为H3-A12只读历史决策证据复盘，不执行模型、live或代码修改。

2026-09-24 项目所有者进一步明确：先充分整合已找到的攻略到启发式体系的 RAG、公式、公开特征、路由和模型前决策链，再检查旧三处现场问题；未整合前不逐点修补，以免后续整合覆盖或引入冲突。规划 Codex 因此暂停上一段所述独立 H3-A12 旧 trace 复盘 Prompt，改为一个连贯的来源策略整合 Coding 任务；旧 trace 仅在整合后的只读验收中使用。H3-A11 代理敏感性结论仍有效，不再扩建该代理或用其标签判策略优劣。具体当前执行任务以`docs/NEXT_PROMPT.md`最新版本为准。
