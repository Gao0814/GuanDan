# GuanDan 优化计划

当前进度与风险见 `docs/PROJECT_STATUS.md`。下一步实施任务见 `docs/NEXT_PROMPT.md`。

## 当前优先级（2026-09-14）

1. 当前主线是算法优化，不恢复8对/16局或百局capacity，也不扩展到其他级牌、贡还或多局升级；固定profile为四人、级牌2、无需进贡的单局。
2. 已完成并提交五项窄策略修正：默认RuleBased的对手压力保牌、队友控桌保炸弹，DeepSeek的危险对手pass阻断、1–4张自由出牌短序列规划和队友小王后保留大王。最新算法检查点为 `295b9b5`。
3. seed `47002` 已按“先确认页面已连接，再提示seed和建桌”完成真实对局，但旧history不能唯一重建全部canonical决策输入；该局本身不足以支持新的算法修改。
4. 默认关闭、Header ack后写入的connector decision trace已实现并提交为 `045fb75`。规划Codex独立复现历史反例并通过Botzone定向88项、主规则39项和全量707项。
5. seed `47002` 的五份已审计evidence已于2026-09-10逐项移入Windows回收站。随后执行的seed `47003`单局DeepSeek采样已形成history、decision trace、audit、finished tombstone和streams，现场保留且无connector残留。
6. seed `47003` 的connector/ACK trace闭环有效，但平台终局分类为`platform_error`，不能作为正常胜负结果。10条decision trace与audit、binding、selected action和provenance守恒，仍可用于逐决策诊断。
7. 独立复审在第9个ACK决策发现可复现的模型上下文缺口：prompt显示桌面牌型和玩家队伍，却没有指出桌面动作由谁领出；RAG也没有领牌者关系。现有strategy router能从同一公开输入严格得到`support_teammate / teammate_controls_table`，但Botzone DeepSeek factory将其prompt路径关闭。
8. strategy-intent接线已由`454a422`完成并经规划Codex独立复审：119项定向、39项主规则、709项全量通过；真实第9条公开输入经factory得到ready的`support_teammate / teammate_controls_table`，且fake模型的合法特殊牌仍原样保留。
9. 受约束执行报告将第9条固定决策的真实DeepSeek off/on复放判定为`strategy_intent_target_decision_improved`：off=`special`、on=`pass`，两侧均模型成功且动作合法；on侧意图为`ready / support_teammate / teammate_controls_table`，总请求2、重试0，没有RuleBased替代或新增后置pass。规划Codex独立复核trace与Git未变；模型响应按隐私契约未持久化。该单点结果支持prompt输入改善，不是整局胜率。

10. 全10条trace和三个后置守卫的只读审计判定为`seed_47003_no_additional_high_confidence_candidate`。规划Codex独立复算关系、intent、RAG场景和动作类别一致，三个守卫实际触发数均为0；seed `47003`不再支持新的算法规则。
11. `danger_opponent_block`、`teammate_control_block`、`short_endgame_plan`均属于成功模型动作后的策略覆盖，而非协议安全。它们暂不删除，但作为DeepSeek策略自主权技术债逐项取得prompt-first证据。

12. `teammate_control_block`守卫前真实模型检查返回`target_special`，但执行所复用的测试fixture包含“单张9压单张小王”的伪合法候选。当前引擎独立验证为大王可压小王、9不可压小王，因此该模型输入违反canonical legal actions前提；原`teammate_control_prompt_raw_model_not_ready`改判为`teammate_control_prompt_raw_model_inconclusive`，不形成prompt不足证据。

该阶段因此只安排修复测试fixture：目标小王→大王场景必须使用engine可证明的canonical候选；原“普通低价值动作不拦截”测试若要保留，必须另建真正合法且不满足大王守卫语义的场景。不得借机修改生产guard、prompt或RAG。

13. fixture修正已提交为`8db3154`：目标场景精确为pass与大王两个canonical候选；普通动作非触发测试移至队友单张8、本家以9合法跟牌的独立场景。规划Codex独立复跑41项定向、39项主规则和710项全量通过，生产文件零修改。

该阶段随后对修正后的canonical小王→大王fixture执行一次真实DeepSeek原始动作检查：只允许一个模型请求，必须在任何后置守卫前读取原始选择；上一轮受伪合法候选污染的调用永久保持inconclusive，不并入新结果。

14. 修正后的canonical真实模型检查判定为`teammate_control_canonical_prompt_raw_model_not_ready`：两个候选均符合引擎真值，intent已ready但仅给出泛化“队友当前控桌”，RAG为`endgame / endgame`，原始模型仍选择大王。该结果是窄prompt输入缺口证据，不授权扩大后置覆盖。

15. 小王→大王资源保留的专用strategy-intent已提交为`24fb362`：新增共享`teammate_big_joker_opportunity()`并由router和既有守卫复用；新版reason明确pass合法、不能直接出完、无危险对手及保留大王的策略意义。提示仍是建议，RAG、动作选择和后置守卫范围均未改变。规划Codex独立复跑83项定向、39项主规则和712项全量通过。

下一步只对同一canonical fixture执行一次新版prompt下的守卫前真实模型复放，外部请求上限1、重试0。若原始选择变为pass，再规划把`teammate_control_block`转为shadow/退役；若仍选大王，下一步单独检查`endgame / endgame` RAG，不扩大后置覆盖。

16. 新版canonical真实模型复放判定为`teammate_big_joker_prompt_raw_model_improved`：专用reason ready、RAG保持`endgame / endgame`，唯一请求在后置守卫前返回原始合法pass。该结果支持让prompt承担策略引导并退役强制动作覆盖，不外推为整体胜率结论。

下一步从生产DeepSeek成功路径移除`teammate_control_block`改写，保留`teammate_big_joker_opportunity()`和专用prompt。无需新增shadow source；现有decision trace可重建机会。历史audit/session/trace中的旧source应保持必要读取兼容，但新路径只记录`model`。

17. `e30362f`已移除生产DeepSeek成功路径的`teammate_control_block`改写，fake pass/大王均保留原始ID与`model` source；共享机会判定、router、专用prompt以及`danger_opponent_block`→`short_endgame_plan`相对顺序保持。独立113/39/713项测试通过。

本提交的完整验收仍有一个可复现缺口：正式policy benchmark的独立source allowlist/守恒公式拒绝legacy v7/v8 `teammate_control_block` audit，而session/trace与observability snapshot兼容已通过。下一步只修正这个离线audit消费边界，并一并锁定当前活跃的`danger_opponent_block`和`short_endgame_plan`可被正式消费器按成功模型动作计数。不改生产Agent选择、source产生、audit schema或任何Botzone/live路径。

18. `3ee6e0e`已完成该兼容补漏：legacy v7/v8 `teammate_control_block`、活跃`danger_opponent_block`和`short_endgame_plan`均按成功模型动作被正式benchmark消费，outcome/count不守恒、conditional或未知source仍拒绝。独立109/39/718项通过，生产DeepSeek/adapter未恢复legacy source。`e30362f` + `3ee6e0e`组合验收封板。

19. canonical危险对手fixture的受约束真实模型检查判定为`danger_opponent_prompt_raw_model_ready`：pass/9/J均为原始合法候选，intent为`ready / block_opponent / urgent_opponent_controls_table`，RAG scene为`endgame`；唯一请求成功、重试0，守卫前原始动作类别为`ordinary`且ID属于候选集。Git前后clean，模型自由文本未持久化；规划Codex独立复跑当前相关95项通过。该证据只支持退役既有动作覆盖，不外推为整体胜率。

下一项Coding任务从生产DeepSeek成功路径移除`danger_opponent_block`改写，并在确认无其他生产消费者后删除`_block_dangerous_opponent_pass()`与`dangerous_opponent_pass_id()`。保留现有`block_opponent / urgent_opponent_controls_table` router/prompt与RAG输入，使真实模型继续获得危险对手策略依据；`short_endgame_plan`的范围和行为不得改变。`danger_opponent_block`转为与`teammate_control_block`同类的legacy read-compatible source，新生产DeepSeek/adapter不得产生或主动接受它。

20. `7499ccc`已完成危险对手动作覆盖退役：成功模型的pass/9/J均保持原始ID与`model` source；危险对手router/prompt/RAG保留；`danger_opponent_block`仅作legacy读取，旧证据守恒继续fail closed；`short_endgame_plan`未变。规划Codex独立复跑132/39/718项并确认生产路径零legacy主动分支，提交验收封板。

剩余自主性技术债仅为`short_endgame_plan`。下一步对现有4张自由出牌canonical fixture做一次真实DeepSeek守卫前检查：公开手牌为6、7、J、J，五个合法首出中action 1/2/5均属于最少剩余分组，action 3/4因拆J对而严格更差；当前strategy intent为`ready / control / stable_control`，RAG为`endgame / near_open_endgame`。只用一个零重试请求判定现有通用prompt是否已能自主避开严格更差动作，不修改代码或Botzone。

21. 该受约束真实模型检查判定为`short_endgame_prompt_raw_model_not_ready`：前提与`{1,2,5}`最少分组集合均确认，唯一请求成功、重试0，但守卫前原始动作落在严格更差的单J集合`{3,4}`。HEAD/工作树未变；规划Codex独立复跑78项并复算分组真值一致。该单点证据只说明`stable_control`缺少短残局最少分组语义，不证明整体策略优劣。

下一项Coding任务在不改变后置动作的前提下补充专用prompt输入：从`agents/short_endgame_planner.py`抽出独立于模型选择的共享最少分组机会函数，只有完整公开free-lead/1–4张/canonical证据证明至少一个首手严格更差时才成立；router新增`run_out / short_endgame_minimum_groups`，prompt解释优先最少剩余分组并避免无谓拆组。`short_endgame_plan`继续复用同一真值且行为、source和顺序不变，完成后再对同一fixture做一次真实模型复放。

22. `c32259d`已实现短残局专用公开输入：共享机会函数与后置守卫复用同一分组求解，固定fixture输出`(1,2,5)`；router/prompt变为`ready / run_out / short_endgame_minimum_groups`，DeepSeek最终输入验证接受且RAG场景不变。规划Codex独立复跑92/39/721项，确认后置动作、source、adapter/audit均无漂移，提交验收封板。

23. 新版专用prompt下的同fixture守卫前真实模型复放判定为`short_endgame_dedicated_prompt_raw_model_ready`：全部离线前提通过，intent为`available / run_out / short_endgame_minimum_groups`，prompt为`ready / run_out`且包含两项关键语义，RAG保持`endgame / near_open_endgame / endgame`；唯一请求成功、重试0，原始动作属于固定候选和最少分组集合`{1,2,5}`。规划Codex独立复跑126项相关测试并核对生产/source边界；模型自由文本未持久化，结果不外推为整局或胜率结论。

下一项Coding任务退役生产DeepSeek成功路径的`short_endgame_plan`改写，保留`minimum_group_free_lead_action_ids()`、专用router/prompt与Botzone factory接线。`short_endgame_plan`转为与另外两个已退役覆盖相同的legacy read-compatible source；新DeepSeek/adapter路径只保留原始合法ID并记录`model`，旧v7/v8 audit、session/decision trace和正式benchmark继续执行成功outcome及计数守恒校验。

24. `f426693`已退役最后一个成功模型后置策略覆盖`short_endgame_plan`：固定短残局的五个合法模型action均保留原始ID与`model` source；共享最少分组机会、`run_out / short_endgame_minimum_groups` router/prompt和Botzone factory接线保持。三个旧改写source现统一为legacy read-compatible，adapter归一为`model`，错误outcome/count继续fail closed。规划Codex独立复跑134项定向、39项主规则和718项全量，提交与工作树格式检查及生产路径扫描均通过，无复审发现。

当前成功模型动作后的策略覆盖技术债已清零，没有证据支持立即制造新的Coding改动。下一阶段先按`docs/NEXT_PROMPT.md`在独立任务中回收已完成审计的seed `47003`六份evidence，仅保留固定workspace及三个空目录；之后再单独规划使用最新HEAD的人工单局DeepSeek采样，以新decision trace寻找可复现策略输入缺口。清理和live不得合并。

25. seed `47003` workspace回收在前三项成功后按失败即停规则中止：completion audit、decision trace、history已进入Windows回收站；第四项在回收前因执行脚本误抄预期hash而校验失败，state与两份stream文件均未处理。规划Codex独立确认前三条路径不存在，后三项的类型、115/0/76 bytes及完整SHA-256仍与原allowlist一致，固定root/三个目录、顶层目录集合、Git和无connector状态均未漂移。永久删除为0。

下一步仍是独立清理任务，不进入live：按`docs/NEXT_PROMPT.md`只回收剩余state、stderr、stdout三个精确文件，继续失败即停，并保留空`audit/state/streams`目录。只有规划Codex复审最终文件数为0后，才另行安排最新HEAD的人工单局DeepSeek采样。

26. 恢复清理已完成：剩余state、stderr、stdout按新allowlist逐项进入Windows回收站，前三条旧路径继续不存在；永久删除、回收站清空、connector/live/model/preflight/browser和仓库修改均为0。规划Codex独立确认固定workspace为普通非链接目录，递归精确只含空`audit/state/streams`三个普通目录，文件数0；`D:\VsCodeProject`顶层`Botzone*`仍只有固定workspace，Git与项目connector均无漂移。

27. seed `47004` 人工 `deepseek` decision-trace 采样已完成且未重开：26 cycles，25/25/25 request/response/Header，qualified finish=1，24条ACK决策与audit守恒；15次模型请求全部success、重试0、fallback 0，另有9次local shortcut。规划Codex独立验证v8 audit、v4 tombstone、trace binding/序号/selected action/source、history、stream和运行provenance，复跑Botzone/策略输入相关123项通过。平台结果为`local_team_loss`，只作结果分类，不作为策略质量结论。

本局形成三个可复现且原因不同的策略输入问题。其一，模型在同时看到同点数四张/五张炸弹时选择四张，现有prompt未表达残余孤张和炸弹层级的联合代价；其二，自由首出Q来自`OpeningFormulaStrategy`本地短路，问题是Q这一选择本身——清理累赘应优先不拆结构的低孤张，低成本试探也应优先10或更低的可牺牲普通单张，现有高点奖励反而无条件消耗更可能用于残局夺权的Q类资源；其三，原始legal actions存在对3，但free-lead transition剪枝因已有single而删除全部pair，模型根本不可见。下一项Coding任务按`docs/NEXT_PROMPT.md`只修正公开输入、剪枝和开局公式，不新增任何成功模型后置覆盖。

28. 项目所有者指出更上游根因：公式化开局本应来自稳定人类套路，频繁按现场反例改权重说明公式来源不可靠。规划Codex联网复核后确认，当前经验库全部策略条目无作者/出版物/链接/规则版本/适用范围，开局公式常量也无引用或校准，不能继续称为已验证人类经验。首版来源审计写入`docs/STRATEGY_SOURCE_AUDIT.md`：官方规则、具名专家/正规出版物、弱来源转载和学术架构分层；只有已核对正文支持的有限原则可激活，书目目录不得扩写成策略，未知或冲突场景由公式退出给RAG+DeepSeek。来源信息采用独立治理registry，不进入知识正文、语义评分、冲突扫描或模型prompt。下一任务先建立双平面来源契约和高召回剪枝，再调整行为；不从单局直接造新定式。

29. `5dbdd2c` 已实现 H3-A0 主体：经验 provenance 独立 registry 与严格激活过滤、有限公开经验转述、窄强牌小单开局、第一层自然 pair 召回和公开残余结构提示均已接入。规划 Codex 独立核对来源正文、完整 diff 和数据流，运行 197 项定向、39 项主规则及 717 项全量均通过；合法模型动作继续保持原始 ID 与 `model` source，三个旧 source 没有恢复主动路径。

30. H3-A0 复审未封板。当前最终 prompt limiter 在 critical 数量达到 80 时返回全部 critical，真实初始局面会得到 132–183 等超过 80 的最终候选，并重新丢掉第一层已保留的自然 pair；已知 seed `47004` 也复现最终无自然 pair。下一任务 H3-A0a 只统一最终候选预算与代表性召回：硬上限 80，稳定保留自然 single、最小自然 pair、四/五张目标炸弹，并对 overflow 的 wildcard/pressure/finishing 建立显式有界优先级。修复前不安排真实模型或新 live。

31. `66009fc` 已完成 H3-A0a。最终 prompt action limiter 先按语义签名去重，自由首出预留稳定最小自然 single/pair、跟牌预留 pass，再按 finishing、pressure、wildcard、ordinary 的确定优先级填满且永不超过 80，最终按原始展示顺序返回。规划 Codex 独立复跑相关 230 项、主规则 39 项、全量 720 项，并对 500 个真实引擎初始局面验证预算、召回、签名、原始 ID 与顺序性质全部成立；原 6 个失败样本从 132–243 项收敛为 80 且 pair 恢复。H3-A0/H3-A0a 封板，当前转入 H3-A1。

32. H3-A1 已由 `d20dba3`、`7020b35`、`da2fd6b`、`caa1cc0` 完成，并通过规划 Codex 的组合复审后合入主线。十个策略域现在由公开局面派生，进入 RAG 排序与固定枚举 prompt；B 级来源原则与 C 级可撤回软假设分离，provenance 治理字段仍不进入知识正文或模型输入。candidate/recommendation 对玩家关系、free/follow/table、声明牌、carrier、通配多重集、固定枚举和预算 fail closed；关键代表不再由原顺序前 12 项截断。DeepSeek 成功返回的合法原始 ID 与 `model` source 保持不变，没有新增模型后覆盖。

规划 Codex 独立运行 212 项 H3/DeepSeek/Botzone 定向、39 项主规则和 732 项全量测试；8 类畸形 canonical 反例全部降级为 `unavailable`。30 局真实引擎离线遍历覆盖 2730 个状态、零异常，十域均可达，11 条 active 经验在生产默认 top-k=3 下均至少命中一次。H3-A1 离线阶段封板。

33. H3-A2 在首个真实请求前按预注册门槛停止，请求 0、重试 0。八场离线资格检查证明 canonical、目标分类、router、RAG 与 soft hypothesis 可达，但低成本单张、对子清理、中性 pair/triple、短残局和炸弹/通配五场缺少 `【模型前建议】`。根因是 recommendation 从完整动作集选择原始 ID，而两层 prompt 剪枝未保护这些 ID；最终校验发现任一 ID 缺席便丢弃整个 recommendation，包括策略域、目标和反例。

规划 Codex 用真实引擎初始局面 seed `0..9` 独立复现：十个局面全部至少缺少一个 recommendation ID，最终验证均返回 `None`；其中既有 16 项相关单测仍全绿。下一步不是放宽 H3-A2 marker 或改 fixture，而是先完成 H3-A1.1 集合闭环：完整 canonical 动作继续产生 recommendation，最多 3 个合法推荐 ID 在第一层剪枝和最终 80 项预算中获得确定性保护，prompt 中输出的 recommendation ID 必须精确属于实际候选；若推荐本身畸形仍 fail closed。修复不得改变候选合法性、原始 ID、模型成功动作保真、RAG provenance 隔离或 H3-A0a 预算/优先级契约。

H3-A1.1 通过组合复审后，重新执行原 H3-A2 的全部八场离线资格检查；只有八场同时通过才开始最多 8 次、零重试真实 DeepSeek 诊断。此前 0 次调用不形成模型质量结果，也不允许缩减或替换场景。

34. `ba449f5` 完成了候选保护主链：recommendation 在完整 canonical 动作上先生成，通过严格校验后其最多3个原始ID穿过首层剪枝和最终80项 limiter；Client响应只接受实际 prompt candidates。规划 Codex 独立复跑64项直接相关、39项主规则和738项全量均通过，初始多seed回归也通过。

该提交仍有一个阻塞封板的生产契约反例。40局/3379个真实引擎后续状态中4个状态的 builder 生成5项 objective，但 `_validated_strategy_recommendation()` 只接受最多4项；因此“ready”生产 payload 在进入候选保护前被拒绝，推荐ID继续丢失且模型前建议区块消失。下一步 H3-A1.1a 只统一 recommendation 生成预算、validator预算和超额时的确定优先级，确保所有生产 ready payload 自校验通过；不得简单放宽/删除预算、静默丢ID或削弱畸形外部payload的fail-closed。完成后须用真实整局全状态性质检查证明闭环，再由规划 Codex 复审。

正式实验恢复时必须保留的经验：**把每一个可以原地修正的准备阶段小错误，都升级成不可恢复的正式实验失败**是错误的流程模型。qualification 与实验副作用必须分层，零外部副作用的准备错误允许原地修正。

## 2026-08-14 Botzone v4 诊断画像进度

- L5-A2b5 六种缺失必需字段 profile 已实现并通过扩展定向 36 项、全量 574 项和补丁格式检查。
- audit 升级为 v4，仅新增聚合 `diagnostic_profiles`；v3 的父诊断和 detail 语义保持不变。
- 该实现仍是工作区中的七个源码/测试改动，尚未由实现任务建立独立检查点；规划任务不代为提交非 docs 文件。
- 下一步为 L5-A2b6：先验证独立实现检查点，再运行一次零网络 DeepSeek connector preflight；通过后仅准备新的 L5-A2b7 授权问题，不直接 live。
- L5-A2b4 的无贡 DeepSeek smoke 仍永久无效，原授权已消耗。

### 顺序修正

- 首次 L5-A2b6 因七个实现文件尚未提交而按门槛返回 `precondition_failed: required_fields_profile_checkpoint_missing`。
- 原计划把“检查点已存在”设为前置，却没有先安排具备源码提交权限的任务，形成循环前置。
- 下一步改为 L5-A2b5a：只复核并提交七个已验证文件；不得编辑代码、运行 preflight 或联网。
- L5-A2b5a 成功并确认工作区干净后，才重新安排 L5-A2b6 零网络 preflight。

### 检查点已解除阻塞

- L5-A2b5a 已完成，检查点为 `8e8d639011bd095bcf0af74816609c63e8c6199f`，提交范围精确为七个 profile runtime/test 文件。
- 36 项定向、574 项全量和补丁检查通过，提交后工作区干净。
- 当前进入 L5-A2b6：只做一次零网络 v4 preflight；成功后请求新的 L5-A2b7 授权，不直接 live。

### L5-A2b6 实际结果

- 前置、36/574 回归、配置元数据和零网络边界均通过。
- 唯一 preflight 在 30 秒内 exit 2；stderr/state/残留为空，全部网络与模型计数为 0。
- 判定为 `botzone_deepseek_connector_v4_preflight_invalid`，不请求 live 授权。
- 现有入口将 runtime config、state preflight 和 DeepSeek factory/Agent 组合失败统一折叠为 exit 2；下一步 L5-A2b6a 使用仓库外固定阶段诊断定位边界，不重跑正式 preflight。

### L5-A2b6a 实际结果

- 唯一 process-only 诊断在 `runtime_config_load` 阶段 fail-closed，固定结果 `runtime_config_invalid`；仅记录 `runtime_config_load_started`，未进入后续 state、AppConfig 或 Agent 阶段。
- audit、state 与子进程均已清理；网络、Botzone、DeepSeek、connector cycle 和 `suggest_action_id()` 计数均为 0。
- 不能从该低基数结果推断 URL、state、权限或平台根因。下一步只允许离线细分 runtime-config 边界，不能重跑正式 preflight 或请求 live 授权。

### L5-A2b6b 实际结果与路线调整

- 仓库外诊断载体在合成资格阶段返回 `diagnostic_harness_invalid`，真实配置子阶段未执行；不能形成任何 runtime-config 归因。
- 继续叠加一次性脚本无法提高证据质量，停止该方向。
- 下一步 L5-A2b6c 在仓库内为 `--preflight-only` 建立固定、可单测的安全失败分类；实现阶段不运行真实 preflight。
- 契约封存后，L5-A2b6d 才使用新分类执行一次独立零网络准入；live 仍保持阻塞。

### L5-A2b6c 实际结果

- 安全诊断契约已封存为 `3f2cadb7f242625ca0978c5b47a5bc6f5ed299e7`，精确包含五个允许文件。
- preflight 的十种失败类别、成功输出、exit 2、live 通用错误兼容和零网络测试已锁定。
- 定向 26 项、全量 578 项和补丁检查通过；实现阶段未运行真实 preflight。
- 下一步 L5-A2b6d 在 `PYTHON_DOTENV_DISABLED=1` 的显式子环境中执行唯一一次零网络恢复准入。

### 流程简化决定

- 项目所有者尚未执行原 L5-A2b6d，并明确要求停止继续搭建诊断载体。
- 纯本地、零网络 preflight 改为可重复调试：每次按现有固定分类只修正一项配置，直到 `preflight_ready`。
- 真实 Botzone/DeepSeek 请求仍保持明确授权、固定预算和单 connector。
- 建桌优先采用官方 `runmatch` API，减少“connector 已连接后再人工抢时间建桌”的不稳定窗口。
- `X-Initdata` 的 GuanDan 无贡编码仍未知，首次 runmatch 省略该可选 Header，并在首个请求上严格验证 `global.tribute == 0`；否则 fail-closed。

### dotenv 禁用门槛修正

- `precondition_failed: dotenv_disable_not_honored` 源于检查了错误的解释器/责任层：`config.py` 调用 `load_dotenv()`，禁用开关由 `python-dotenv` 库本身处理。
- 系统 PATH 中的 `python` 所加载版本不具备该能力；项目 `.venv` 的 `dotenv.main.load_dotenv()` 明确先检查 `PYTHON_DOTENV_DISABLED`，命中后在创建 `DotEnv` 或解析文件前直接返回。
- 不需要代码修复。后续所有 preflight 强制使用 `.venv\Scripts\python.exe`，并在同一子环境设置禁用开关。

### L5-A2b6d 本地结果

- 项目 `.venv` 下的受监督 preflight 已通过：exit 0、`preflight_ready`、stderr 空、206 ms、state/进程清理完成。
- 全部 Botzone/DeepSeek/DNS/socket/HTTP/connector/action 计数为 0；判定 `botzone_deepseek_connector_local_preflight_ready`。
- 本地配置调试结束，不再新增诊断任务。
- 下一步 L5-A2b7 一次性收集三个 Bot ID、`me` 座位、旧桌清理、无贡 fail-closed 接受和完整 live 授权，然后执行唯一 runmatch smoke。

### L5-A2b7 已获授权

- 项目所有者已提供三个 GuanDan Bot 位置输入，`me=0`，并确认旧本地 AI 测试桌已全部关闭。
- 三个非本家位置复用同一个现有 Bot。公开 runmatch 契约未要求 Bot ID 互不相同；若平台按建桌限制拒绝，单次运行立即停止，不替换 Bot 或重试。
- 项目所有者已接受省略 `X-Initdata`，并授权一次 runmatch GET、最多 100 次 local-AI GET、DeepSeek 60 秒/零重试、单 connector、单对局、最长 3600 秒。
- Bot ID 与其他敏感值不写入文档或审计；下一步直接按 `NEXT_PROMPT.md` 执行唯一 live smoke。

### L5-A2b7 实际结果与直接修复

- 唯一 runmatch 创建成功，但 connector 只收到一个请求，未产生 response/Header，随后以协议诊断和一次 transport failure 停止；qualified finished=0。
- 固定画像为 `required_both_missing_inner_stage_candidate`，说明 local-AI poll 交付的是 GuanDan 直接 `stage` object，而当前 poll 入口无条件要求 Bot JSON 外层信封。
- 该 live 结论为 `botzone_deepseek_runmatch_no_tribute_smoke_invalid`，授权已消耗，不重试。
- 下一步 L5-A2b8 直接实现双 wire mode：信封模式保持包装与 replay，direct-stage 模式使用 durable session 并发送 canonical 原始 GuanDan response。停止新增诊断载体。

### L5-A2b8 已完成

- 检查点 `2cd208b9b8f7306decf3182318fb55278c09d641` 精确包含 3 个 integration 文件和 4 个对应测试文件。
- `PollRequest` 已显式区分 `bot_envelope` / `direct_stage`；前者保留 replay 与 response wrapper，后者使用 durable session 和 canonical 原始 GuanDan response。
- direct 冷启动 play、unsupported stage、非法响应、注入、pending 重发/ack 和 action provenance 均 fail-closed；原 envelope 契约保持兼容。
- 68 项定向、583 项全量和补丁检查通过，工作区干净；未联网。
- 下一步 L5-A2b9 只做一次零网络本地准入；ready 后请求新的 L5-A2b10 live 授权，不在同一步联网。

### L5-A2b10 实际结果

- runmatch 创建成功，真实 direct-stage 路径完成一个 request、一个 response 和一个 Header，协议 detail/profile 为空。
- 唯一 connector 在 8 cycles 后以 `failure_limit` 退出：6 次 transport failure，raw finished=1、qualified=0；没有重试。
- 判定仍为 `botzone_deepseek_runmatch_no_tribute_smoke_invalid`。该结果不证明 play ack、DeepSeek 决策或完整对局。
- 现有 runner 把长轮询 timeout 与真实网络故障合并计入 failure limit，audit 也不能细分 raw finished。下一步 L5-A2b11 直接加固固定 transport category、idle timeout 和 finished provenance，不再增加外部诊断载体。

### L5-A2b11 已完成

- 检查点 `220c648a4629453621f534beaeb95e52d85656ce` 精确包含 3 个 integration 文件和 5 个测试文件。
- timeout 已成为独立 idle 计数，不触发退避或 failure limit；其他 transport error 保留固定安全 category 与失败预算。
- audit 升至 v5，在保留既有字段的同时新增 timeout、failure category 和互斥 finished provenance；qualified finished 门槛未降低。
- 80 项定向相关、587 项全量及补丁检查通过，工作区干净且未联网。
- 下一步 L5-A2b12 只运行一次零网络 preflight；ready 后重新请求 L5-A2b13 live 授权。

### L5-A2b12 前置阻塞

- 检查点、工作区、配置元数据与进程门槛均通过，但当前权限范围无法创建系统临时 state 目录。
- preflight 子进程未启动，所有网络、模型、transport、connector 和 Agent 计数为 0；结果为 `precondition_failed: temporary_state_directory_unavailable`。
- 该结果不归因 runtime 或 connector。下一步 L5-A2b12a 只请求一次仓库外临时目录写权限，并执行原零网络 preflight；不改代码、不重复测试、不联网。

### L5-A2b12a 仍受沙箱阻塞

- 获得受限写入请求后仍无法创建系统临时 state 目录；preflight 子进程继续为 0 次，全部网络/模型计数为 0。
- 不再重复 Codex 沙箱路径。L5-A2b12b 改由项目所有者在宿主机 PowerShell 使用全新仓库外目录手动运行同一个 `--preflight-only` 命令。
- 手动结果只回报固定 stdout、exit、state_empty 与 stderr 是否为空；ready 后才请求新的 L5-A2b13 live 授权。

### L5-A2b12b 仍无法创建外部资源

- 项目所有者宿主机步骤也无法创建全新仓库外 state/audit，故 connector/preflight 均未启动，网络计数为 0。
- 不再尝试新目录。只读复核确认既有 `D:\VsCodeProject\BotzoneState` 存在且为空。
- L5-A2b12c 由项目所有者直接复用该既有空目录执行一次最终 `--preflight-only`，不创建 audit、不删除目录；若仍失败则暂停本地准入，先处理宿主机权限。

### L5-A2b12c 暴露独立 audit 前置

- 既有 state 目录存在且为空，但环境无法创建或保证独立仓库外 audit 路径，因此在 connector 首次 GET 前停止，网络计数为 0。
- state 与 audit 不得共用目录。只读确认固定 `D:\VsCodeProject\BotzoneAudit` 尚不存在。
- L5-A2b12d 由项目所有者在宿主机 PowerShell 创建该目录，并用固定空 JSON 探针验证创建、同目录重命名和删除；步骤不运行项目代码或网络。

### L5-A2b12d audit 目录已准备

- 项目所有者确认 `audit_exists=True`、`audit_empty=True`、`audit_probe=passed`。
- 既有 state 与新 audit 目录均为仓库外、独立且为空，不再动态创建或删除目录。
- 下一步 L5-A2b12e 由项目所有者在宿主机 PowerShell 运行一次 `--preflight-only`；通过后再请求 L5-A2b13 live 授权。

### L5-A2b12e 零网络准入通过

- 宿主机输出为 `preflight_ready`、exit 0、state/audit 均为空，stderr 未显示。
- 判定 `botzone_long_poll_deepseek_local_preflight_ready`；该步骤没有 transport、connector、runmatch 或 DeepSeek 网络请求。
- 下一步 L5-A2b13 重新取得完整单次 live 授权；旧授权不延续，授权前不得联网。

### L5-A2b13 实际结果

- 项目所有者完成新授权后，唯一 connector 已启动，唯一 runmatch GET 已发送，但 Botzone 页面未显示对局。
- 为遵守不重试规则，connector 被终止；没有可用完成 audit，state 目录非空且未读取或清理，工作区干净。
- 判定 `botzone_deepseek_runmatch_no_tribute_smoke_invalid`。现有证据不能确认 runmatch 创建、local-AI request、DeepSeek 调用或任何对局闭环。
- 下一步 L5-A2b14 仅做零网络、只读、脱敏的残留 state 与缺失 audit 审计；不得清理 state 或直接恢复 live。

### L5-A2b14 实际结果

- 判定 `botzone_live_residual_state_audit_verified`：completion audit 缺失；state 仅剩一个合法 finished tombstone，没有可归因的 active deal/play、pending/ack 或 Agent 证据。
- state 审计前后目录摘要不变，独立聚合 audit 只保留固定计数并通过结构和值白名单校验。
- 下一步 L5-A2b15 只精确删除该已审计 finished tombstone，并确认 state 为空；暂不修改 connector/audit 生命周期。清理后转为网页人工建桌路线，不再调用 runmatch，且必须另行取得 live 授权。

### L5-A2b15 实际结果

- 判定 `botzone_finished_tombstone_cleanup_verified`：删除前唯一 state 文件再次严格验证为 finished tombstone，删除后固定 state 目录为空。
- L5-A2b14 聚合 audit 的 996 bytes、SHA-256、schema/value allowlist 与敏感扫描保持不变；零测试、preflight、connector 和网络请求。
- 下一步 L5-A2b16 重新取得完整 live 授权；不再调用 runmatch，先启动唯一 connector，项目所有者确认页面已连接后再人工创建且只创建一个无贡 GuanDan 测试桌。

### L5-A2b16 实际结果与直接修复

- 唯一 connector 在项目所有者确认人工新桌前 exit 5；request/response/Header=`4/3/3`，唯一诊断为 `history_alignment_failed`，没有 transport timeout/failure 或 finished。
- 因人工桌确认尚未发生，这些请求不能归入新桌；state 保留一份 active session 且未读取/修改，live 判定 `botzone_manual_no_tribute_deepseek_mode_smoke_invalid`。
- 现有合并器只覆盖有 overlap 的四手滑窗，但两次本家 request 间可恰好发生四个动作，形成合法零重叠 full-window replacement。下一步 L5-A2b17 直接补 durable session 与 envelope replay 的等价离线契约，不新增 live 诊断或重试。

### L5-A2b17 实际结果

- 检查点 `5bb44fd4052e181d08455594ab0879c0ee305dfb` 精确包含两个实现文件和两份测试。
- 完整 4 项零重叠窗口可全量追加；0..3 项零重叠仍拒绝；overlap、重复、累计历史、latest-window 上限及 envelope/direct 等价性保持。
- 定向 17、相关 65、全量 590 项与补丁检查通过，零网络且未读取残留 live state。
- 下一步 L5-A2b18 在项目所有者明确确认旧桌结束并授权后，严格复核旧 active session 无 pending/inflight/effect，再精确删除；不得与新 live 合并。

### L5-A2b18 实际结果

- 判定 `botzone_abandoned_active_session_cleanup_verified`：唯一 session 严格为 `play/idle`，pending/effect/finished 为空，文件名与内部 key 一致；cached response 与 handler completed 仅作聚合记录。
- 仅删除该旧 session，state 文件数由 1 变为 0；目录保留，两份既有 audit 完全不变，零测试/preflight/connector/网络。
- 下一步 L5-A2b19 重新取得人工网页桌完整授权。采用“connector 启动 → 用户确认已连接 → state 仍为空 → 实施任务允许建桌 → 用户确认进入对局”的握手顺序，不调用 runmatch。

### L5-A2b19 实际结果与握手修正

- 唯一 connector 在聊天中的“已连接且已进入对局”确认到达前观察到 state 从 0 变 1，按预注册门槛立即终止；随后确认消息才到达，故该桌不能追认。
- 无完成 v5 audit，runmatch=0，state 保留一个未读文件，无残留 connector；判定 `botzone_manual_no_tribute_deepseek_mode_smoke_invalid`。
- 门槛把正常的“网页建桌立即产生 state、聊天确认稍后到达”误作旧流量。下一次不再以确认消息到达时间约束 state；改为启动前 state=0/旧桌全关/单桌承诺，connector 启动后页面一旦显示连接即可直接建桌并随后确认。
- 下一步 L5-A2b20 先在项目所有者关闭当前桌并明确放弃旧 session 后，生成脱敏聚合并精确清理该单一 state；不与 live 合并。

### L5-A2b20 实际结果

- 判定 `botzone_failed_manual_session_cleanup_verified`：唯一残留 session 为合法 `play/inflight`，pending response/effect 与 handler/cached response 存在，finished 不存在；项目所有者关闭桌面并明确放弃恢复后精确删除。
- state 文件数 1→0，新 cleanup audit 为 564 bytes、SHA-256 `7abc9fdc7b8590b522295cc321d8c4317ce04bdab04e1fd7fa32f6207fbabf8e`，旧 audit 不变；零代码/测试/preflight/网络。
- 下一步 L5-A2b21 采用简化人工时序：connector 成功启动后发出一次建桌窗口消息，用户在页面显示连接时直接建唯一无贡桌并随后确认；state 变为非空不再按聊天消息时序判失败。

### L5-A2b21 实际结果

- 判定 `botzone_manual_no_tribute_deepseek_mode_smoke_verified`：唯一人工无贡桌 connector 正常退出，`finished_target`，23/23/23 request/response/Header，qualified finished=1，transport failure、timeout 和协议 diagnostics 均为 0。
- v5 audit 为 449 bytes，SHA-256 `6eed257558d1ddd58239b8a5d094d3ebe209895abb5c74cd323824dd44c305d4`；state 仅保留一份最小 finished tombstone，无残留 connector，runmatch=0。
- 该结果只证明 `deepseek` 模式 connector 的 Botzone 无贡协议闭环。v5 未记录模型调用或 fallback，不能证明 DeepSeek 实际参与、动作质量或胜率。
- 下一步 L5-A2b22 只在项目所有者明确授权后严格验证并删除唯一 finished tombstone；随后再进入 L5-A3a 的离线模型调用可观测性设计。

### L5-A2b22 实际结果

- 判定 `botzone_successful_smoke_tombstone_cleanup_verified`：唯一最小 finished tombstone 经 schema、文件名和 state 根目录归属验证后精确删除，state 文件数 1→0，目录保留且为空。
- L5-A2b21 v5 audit 保持不变；新 cleanup audit 为 405 bytes，SHA-256 `10037c02ffeca2e4967aa3925e893d4386cd9df76cd213086c8ede2260079c13`。
- network/connector/test/code-change 均为 0。下一步进入 L5-A3a，只离线增加模型尝试、结果、fallback 与最终动作来源的低基数守恒聚合。

### L5-A3a 实际结果

- 判定 `botzone_deepseek_runtime_observability_verified`，检查点 `0c51c5ff85f4edbe980dc1b5e63397da6f5747cc`。
- 新增 frozen/slots 快照与 recorder；v6 audit 加法保留 v5 字段，固定统计五类最终动作来源、四类模型结果、模型尝试与规则回退，并在不一致时拒绝写盘。
- 定向 30 项、全量 597 项与 `git diff --check` 通过；无真实网络、`.env`、凭据、prompt/response 持久化或上传 ZIP 改动。
- 下一步 L5-A3b 只做真实进程零网络 preflight 和 v6 live 门槛预注册，通过后再独立请求 L5-A3c 授权。

### L5-A3c 实际结果

- 判定 `botzone_deepseek_observed_live_smoke_verified`：唯一人工无贡桌 connector `exit=0 / finished_target`，12/12/12 request/response/Header，qualified finished=1，transport failure、timeout 和协议诊断均为 0。
- v6 audit 为 619 bytes，SHA-256 `f29029e9b6dfe0dc8cfcf96b85e7b3a917270eaf4c6f357846d78060c8e60ac9`。
- 11 次 Agent 决策由 `local_shortcut=1`、`model=10` 构成；10 次模型尝试均 success，RuleBased fallback=0，全部守恒通过。
- 这证明本次有 10 次合法模型动作生效，不证明优于规则基线。下一步 L5-A3d 只清理最小 finished tombstone；随后 L5-A4a 设计对照评估。

### L5-A3d 实际结果

- 判定 `botzone_observed_live_tombstone_cleanup_verified`：唯一最小 finished tombstone 严格验证后精确删除，state 文件数 1→0，目录保留且为空。
- L5-A3c v6 与此前 v5/cleanup audits 均不变；新 cleanup audit 为 345 bytes，SHA-256 `a71e233af98d55000a074413b8f4cc97e564db484bf52b5c204e5758681a0225`。
- network/connector/test/code-change 均为 0。下一步 L5-A4a 先离线把官方 finished scores 转换为低基数、守恒的本家团队结果聚合。

### L5-A4a 实际结果

- 判定 `botzone_finished_score_observability_verified`，独立检查点为 `31e2fa5a474a377baa3fb80a4a427766623b96c7`。
- v7 audit 在完整保留 v6 字段语义的基础上，新增 `local_team_win`、`local_team_loss`、`platform_error`、`invalid_score_shape` 与 `score_0..score_3` 的严格聚合。
- 结果只在既有 `finished_qualified` 路径记录；正常结果、分数桶和 qualified finished 守恒，recorder 失效时拒绝写入 v7 audit，但不改变完成清理。
- 定向 24 项、扩展相关 33 项、全量 604 项与 `git diff --check` 通过；实现阶段零网络、零真实配置/state/audit 读取。
- 该结果只解决单局结果可观测性。下一步 L5-A4b 先离线建立固定 seed、四座位轮换、同对手/同设置的 RuleBased/DeepSeek 成对赛程和 v7 audit 微聚合载体，不直接继续 live。

### L5-A4b 计划

- 只新增 evaluation-only 的赛程、严格 v7 audit 复核和成对聚合，不修改 Botzone runtime、engine、agents 或配置。
- 每个调用方显式 seed 覆盖座位 `0..3`，每个条件精确包含 `rule` 与 `deepseek` 两局，并稳定平衡 AB/BA 顺序。
- 整对只有在两侧协议完成、正常分数、策略观测和条件均有效时才进入胜负、score 与 paired delta；任何缺失、重复或异常都整对排除。
- 报告只保留总体/座位整数计数与精确有理数，不保留 seed、Bot ID、match、逐局、牌、动作或模型正文。
- L5-A4b 通过后，L5-A4c 才以 2 个新 seed × 4 座位的 8 对 / 16 局做容量验证；该容量试验不形成策略优劣结论。

### L5-A4b 实际结果

- 判定 `botzone_paired_policy_benchmark_harness_verified`，独立检查点为 `e1b4e14f2806b962c16a08434f8fef589bf9630b`，提交仅含 benchmark 模块与对应测试。
- 载体使用现有 v7 audit，生成确定性的 seed × 四座位 × `rule/deepseek` AB/BA 赛程；缺侧、重复、协议/分数/观测无效时整对排除。
- 报告只输出总体/座位聚合整数和最简分数，不序列化 seed、Bot/match/player、逐局 audit 或模型内容。
- 定向 8 项、全量 612 项与 `git diff --check` 通过；只使用标准库且零网络。
- 下一步 L5-A4c 先离线锁定 seed `24001/24002` 的 8 对 / 16 局操作清单，完成 rule/deepseek 双模式零网络 preflight，并单独请求整批 live 授权；不得直接开始第一局。

### L5-A4c 容量准入计划

- 固定无贡、级牌 2、上轮头游/末游 0/3、双方等级 2、相同三个对手 Bot 及版本。
- 两个 seed 均覆盖 seat `0..3`；每个条件各一局 rule/deepseek，AB/BA `4/4`，共 16 局。
- 仓库外 canonical 操作清单在授权前生成并锁定；每局使用独立 state/audit，串行且不补采。
- rule/deepseek 各执行一次零网络 preflight；全部通过后才提出覆盖 1600 次 Botzone GET、最多 800 次 DeepSeek 请求的批量授权。
- 容量任务只验证人工流程和 v7 audit 配对可用性；即使 8 对全部有效，也不得据此宣称策略收益。

### L5-A4c 首次前置结果

- L5-A4a/L5-A4b 检查点、L5-A4b 提交范围、无残留 connector 与既有 `README.md` 隔离均已确认。
- 项目所有者尚未明确确认全部历史本地 AI 测试桌已结束，也未提供已存在、为空、仓库外的容量试验根目录。
- 因此在回归、清单生成、目录写入和 preflight 前返回 `precondition_failed`；网络与试验预算均未消耗。
- 下一步 L5-A4c1 只收集上述两项人工输入。输入齐全后再由 L5-A4c2 恢复目录资格、8/612 回归、清单生成和双模式零网络 preflight，不得提前 live。

### L5-A4c 实际容量结果

- 原批次已按 seed `24001/24002`、四座位和两策略生成 8 对/16 局清单。
- 第 1 局 rule 与第 2 局 deepseek 均完成协议闭环并正常团队胜；DeepSeek 局有 15 次 local shortcut、9 次 model success、fallback=0。
- 第 3 局 deepseek 在人工建桌前以 `poll_malformed` 停止，request/response/Header/finished 与 Agent/模型计数均为 0；同一时段另有额外人工测试桌操作，不能形成单一根因归因。
- 按预注册停止规则，整批判定 `botzone_paired_policy_capacity_invalid`；第 3 局不重开，第 4–16 局不继续，前两局不迁移到新批次。
- 实际部署比较继续保留 local shortcuts，并通过 v7 单独报告模型暴露；不在容量恢复中改造为 forced-model treatment。

### L5-A4d 恢复计划

- 旧容量根目录、manifest、audit/state 全部只读保留；旧 seed `24001/24002` 永久排除。
- 新批次锁定 seed `25001/25002`，仍为 8 对/16 局、AB/BA `4/4`，并使用全新仓库外根目录。
- 在回归和 preflight 前重新取得“全部历史/额外测试桌已关闭”确认；新批次期间严禁额外测试桌、CLI DeepSeek 对局或第二 connector。
- 先生成新 manifest 并完成 rule/deepseek 双模式零网络 preflight，再单独请求整批 live 授权。
- 若严格单桌的新批次再次在建桌前出现 `poll_malformed`，停止容量运行并另立离线诊断，不在 live 中忽略或重试。

### L5-A4d1 人工前置已满足

- 项目所有者已确认所有历史及额外本地 AI 测试桌均已结束。
- 新容量根目录由项目所有者指定为 `D:\VsCodeProject\BotzonePairedCapacity-25001-25002`；该输入尚需实施任务验证存在、为空、仓库外和原子写能力。
- 下一步只执行目录资格、8/612 回归、新 manifest 和 rule/deepseek 双模式零网络 preflight；不得启动 connector、建桌或联网。
- 全部门槛通过后只提出新的整批授权问题，不在同一步开始 16 局。

### L5-A4d1 实际结果

- 新根目录资格/原子探针、检查点范围、定向 8 项、全量 612 项和 diff check 均通过。
- 调用现有赛程生成器的本地封装命令在任何写入前执行失败；按本步骤不重试规则立即停止。
- 新根目录仍为空，manifest/state/audit 均未创建，两个 preflight 未启动，全部网络/模型计数为 0。
- 判定 `botzone_paired_policy_capacity_recovery_preflight_invalid`；该结果不否定 benchmark、seed 或目录，但阻止进入 live。
- 下一步 L5-A4d2a 只请求一次 manifest 恢复写入授权。授权后 L5-A4d2b 使用独立仓库外 Python runner 做内存断言和一次原子写入，不运行 preflight 或网络。
- L5-A4d2b 的仓库外 runner 在导入项目 `evaluation` 模块时退出，且发生在赛程生成和任何写入之前；根目录仍为空，判定 `botzone_paired_policy_capacity_manifest_recovery_invalid`。
- 下一步 L5-A4d2c 只请求新的导入恢复授权。获授权后的 L5-A4d2d 必须先证明 module spec/origin 指向已核验仓库根，再生成并原子写入 manifest；不得修改持久 `PYTHONPATH`、安装项目、复制源码或运行 preflight/live。
- L5-A4d2d 已通过导入资格并原子生成唯一 manifest：3256 bytes，SHA-256 `3af862cf31f9600746812b0534c4d0b66ce6c8fbd6fdc94c1331f19451b2607e`；赛程守恒为 8 对/16 局、两策略各 8、AB/BA 各 4、四座位各 2 对，判定 `botzone_paired_policy_capacity_manifest_recovery_verified`。
- 下一步 L5-A4d3 按 manifest 创建预注册 state/audit 布局，并分别执行一次 rule/deepseek 零网络 preflight。ready 后只输出 L5-A4d4 授权文本；若唯一缺项是授权，不再修改文档或提交 Git。
- L5-A4d3 已完成布局与 manifest 复核，但残留检查因搜索命令匹配自身而假阳性；两个 preflight 均未启动，结论为 `botzone_paired_policy_capacity_recovery_preflight_invalid`。
- 项目所有者现已授予本项目全部计划内操作的常驻默认授权。后续不再设置项目级授权门槛；L5-A4d3a 直接以仅枚举 Python connector 的方式恢复双 preflight，ready 后直接衔接容量执行准备，只在人工建桌时请求操作确认。
- 25001/25002 批次进入第 1 局后发现人工桌已创建但 connector 已不在运行；game 1 无 completion audit 且留下 1 个活动 state。第 1 局不可计入或重开，第 2–16 局不得启动，整批判定 `botzone_paired_policy_capacity_batch_invalid`。
- 项目所有者已关闭网页桌。下一步 L5-A4e1 依据常驻授权严格审计并精确清理唯一 game 1 state；成功后永久封存该 seed/root，再离线设计 connector 存活握手和新批次。
- L5-A4e1 资格审计发现此前未观察到的 game 1 completion audit，因与“audit 不存在”前提冲突而 fail-closed；state 未解析/删除，cleanup audit 未创建，判定 `botzone_paired_policy_failed_game_state_cleanup_invalid`。
- 下一步 L5-A4e2 只读解析 v7 audit 与 session state 的固定聚合并分类两者关系。仅 `abandoned_session_consistent` 可进入后续精确清理；不得以 audit 文件存在推断对局成功。
- L5-A4e2 确认 v7 audit 与 v3 finished tombstone 各自严格合法，但两者都缺少共同 match/本地运行标识，故只能归类 `evidence_relation_unknown`，判定 `botzone_paired_policy_failed_game_evidence_inconclusive`。两个源文件永久保留且不计分。
- 下一步 L5-A4e3 离线增加严格 32-hex `run_token`：同一 token 进入 session/tombstone 与 completion audit，但不进入网络、Agent 或聚合报告；旧 v7/v3 路径保持兼容。通过后才规划全新 seed/root。
- L5-A4e3 已封存为 `45d34f0d443847aea527929e2a7c0ebf9e4bdd5a`：token 模式使用 session/tombstone v4 与 audit v8，默认 v3/v7 兼容；34/35/617 回归通过，判定 `botzone_paired_policy_run_provenance_contract_verified`。
- 下一步 L5-A4e4 使用新 seed `26001/26002`、新根目录和 16 个确定性唯一 token 生成 manifest/布局并运行双 preflight。ready 后按常驻授权进入 L5-A4e5，人工建桌前必须持有并复核实际 connector 子进程句柄。
- L5-A4e4 已通过：tokenized manifest 为 3635 bytes（SHA-256 报告 `f1793c…63241`），16 个 state/audit 隔离布局与 rule/deepseek 双 preflight 均通过；脱敏 summary 为 653 bytes（`785ff0…d995a`），零网络，判定 `botzone_paired_policy_tokenized_capacity_preflight_ready`。
- L5-A4e5 在第 1 局人工建桌提示前失效：唯一 connector 已退出，game 1 state 为空、v8 audit 不存在，后续 15 局未启动；progress 标记 `batch_invalid_before_table`，整批判定 `botzone_paired_policy_tokenized_capacity_invalid`，seed `26001/26002` 永久禁用。
- 由于该启动没有保留 exit/stdout/stderr，不能归因于 connector、Botzone、DeepSeek 或协议。现有 connector 已有成功 live 证据；缺口是容量外层没有复用可捕获流的 launcher，而旧 launcher 又不能传递 agent/state/run-token。
- 下一步 L5-A4e6 只离线扩展现有 `live_launcher.py` 的 tokenized 参数与流证据，不重写 connector 或新增诊断载体。通过后先做全新 seed/root 的单局可见前台启动资格，再决定是否重建 16 局批次。
- 项目所有者已授权后续 live 使用 Codex 桌面/浏览器控制监督页面并代为创建唯一无贡桌；登录完成后不再逐局要求“已连接/已进入对局”文字确认。只有登录、验证码、安全确认或页面不可可靠识别时才暂停人工处理，敏感连接信息不得读取或持久化。
- L5-A4e6 已封存为 `2209bb71e35c4142c28bf1218fb316f8cf67da2d`：既有 launcher 现严格传递 agent、仓库外 state 和 32-hex run token，在同一进程内保留独立 stdout/stderr；32 项定向、619 项全量与 diff check 通过，判定 `botzone_tokenized_live_launcher_contract_verified`。
- 下一步 L5-A4e7 不恢复容量批次，只用全新 seed `27001`、seat 0、deepseek 做一局可见前台 pilot。Codex 监督页面并建桌，必须完成 launcher/process/UI/v8/v4/token 闭环后才允许规划新的 16 局。
- L5-A4e7 仍在页面连接前退出：27001 根目录只留下两个 0-byte stream，state/audit 为空，未建桌或发送对局请求，判定 `botzone_tokenized_launcher_live_pilot_invalid`。stream 已创建但内容为空，边界指向外层进程保活而非参数解析或对局协议，但具体根因未证实。
- Edge Browser 扩展现已能精确识别并绑定 Botzone 根页面。下一步 L5-A4e8 用全新 `28001`，禁止 detached/Start-Process，改用持久统一执行 session ID 保活 launcher；Codex 自动填桌，但按浏览器安全门槛在最终创建提交前请求一次即时确认。
- L5-A4e8 仍未取得 session ID，launcher 随后退出并只留下两个空 stream；seed 28001 永久禁用，判定 `botzone_persistent_session_launcher_pilot_invalid`。随后完全离线的 `.venv` 合成长进程成功返回 session ID `45404`、跨调用保持运行并 exit 0，证明统一执行 session 本身可用。
- 下一步 L5-A4e9 不再修改或使用 launcher，直接以现有 `python -m integrations.botzone` 入口运行在持续 session 中；使用全新 `29001/seat0/deepseek`，由已绑定 Edge Browser 页面完成单局 pilot。

### L5-A2b7 任务上下文阻塞

- 独立实施任务无法读取规划任务中的 Bot ID 与授权原文，按 `precondition_failed: runmatch_participants_missing` 在零配置、零网络状态停止；授权未消耗。
- 这是跨任务敏感输入不可继承，不是 connector、Botzone 或 DeepSeek 故障。
- 下一步 L5-A2b7a 必须在实际执行 live 的同一任务中重新收齐三个 Bot ID、`me=0`、旧桌/无贡确认和完整预算授权；核对后在该任务内直接执行，不再另开任务传递敏感值。

## 1. 当前结论

截至 2026-08-10，项目已经完成：

- 单局掼蛋规则引擎和 4 AI 对局闭环；
- `observe()` / `legal_actions()` / `step(action_id)` 公开契约；
- DeepSeek 接入、失败降级和本地必出 / 仅 pass 快捷路径；
- 手牌评分、动作剪枝、基础记牌；
- 本地公式化开局；
- 带元数据的规则库、经验库和场景化 RAG。
- Step J-A 精确公开牌池和逐玩家公开事实层。
- Step J-B1 未见牌归属域和公开容量约束。
- Step J-B2 受控残局精确可行分配枚举。
- Step J-C1 离线牌面信念真值评测。
- Step J-C2a 公开行为事件提取。
- Step J-C2b1 最小软评分和 rank 候选排序。
- Step J-C2b2 并列安全 Top-K 与零软分单样本消融。
- Step J-C3a 固定种子残局采集与微聚合基准运行器。
- Step J-C3b RuleBasedAI 独立种子正式基准，判定为保留进入策略分布验证。
- Step J-C3c1 evaluation-only 战略性 pass 策略分布基准载体。
- Step J-C3c2 独立种子策略分布验收，判定拒绝无条件 pass 牌面推断信号；不等同于策略 outcome 判定。
- Step J-C3d1 撤销无条件 pass 扣分并恢复 hard-only neutral ranking。
- Step J-C3d2 独立 corpus neutral baseline 封板。
- Step J-D1a 完整分配的精确物理权重与 token 边际整数计数。
- Step J-D1b 完整分配的逐玩家 rank 持有/副本精确整数边际。
- Step J-D1c1 evaluation-only 单样本精确 Brier、copy 误差与十档充分统计量。
- Step J-D1c2a 多样本精确微聚合、ECE/MCE 与规范化 diagnostics。
- Step J-D1c2b critical 固定 seed collector 与开发容量验证。
- Step J-D1c2c 默认 RuleBasedAI 独立语料正式校准。
- Step J-D1c3a forced/25/50/100 strategic-pass corpus 载体与开发容量验证。
- Botzone Python 3.6.5 直接上传规则 Bot 基线；用户已报告在平台完整运行两局。该基线不需要 connector，但目前只覆盖无贡、传统交互和自然牌动作子集。

当前优化目标从“能运行”转为“阶段判断一致、推断可审计、策略质量可测”。`record.txt` 联网单局只读复盘新增了三个直接样本：开局公式拆对出高单、同队互相消耗炸弹、危险对手剩两张时未阻断。单局不构成收益证明，但可以作为确定性回归 fixture。

## 2. 总体目标

AI 决策分为四层：

1. 公开局面：只读取 `observe()` 和原始 `legal_actions()`。
2. 局面分析：统一阶段、手牌评分、未见牌池和逐玩家信念状态。
3. 策略路由：选择开局跑牌、中局控场、协助队友、阻断对手或残局收束。
4. 动作选择：本地确定性策略优先，其余场景由 RAG + DeepSeek 在合法动作中选择。

规则引擎始终是合法性和状态推进的唯一真值。

## 3. 阶段定义

阶段不能再由各模块分别判断，统一由一个阶段分类器输出：

- `opening`：历史动作不超过 8，自己至少 18 张，三个未完赛玩家均至少 16 张。
- `midgame`：不满足开局或残局条件的常规阶段。
- `endgame`：自己少于 10 张、任一未完赛玩家少于 6 张，或已有玩家完赛。
- `near_open_endgame`：外部玩家合计剩余不超过 20 张。
- `critical_endgame`：外部玩家合计剩余不超过 12 张。

优先级从高到低为：

`critical_endgame > near_open_endgame > endgame > opening > midgame`

## 4. 已完成阶段

### Step A-F：规则、接口、DeepSeek 和回归闭环

状态：完成。

### Step G：手牌评分、理牌与基础记牌

状态：完成基础版本。

已实现：

- `agents/hand_evaluator.py`
- `agents/card_tracker.py`
- 阶段感知动作摘要和剪枝

限制：

- `CardTracker` 仍是全局点数统计旧链路；
- Step J-A 已提供独立公开事实层，但尚未形成逐玩家候选牌、置信度和可行分配。

### Step H：公式化开局与场景化 RAG

状态：完成 MVP。

已实现：

- `agents/opening_strategy.py` 本地开局决策；
- 仅 pass、一次出完和公式化开局跳过 API；
- RAG front matter 元数据；
- 按 `scene / phase / hand_strength / action_context` 检索；
- 规则证据和经验依据分层进入提示词。

待量化：

- 开局高价值牌浪费率；
- 开局两轮后的平均散牌数；
- RAG 场景覆盖率和命中质量；
- 新旧策略 A/B 对局结果。

联网单局发现的待修复项：

- 现有公式把拆对的单 K 排在天然单 9 和天然长套之前，因为只对当前动作打分，不评估残余点数结构；
- CLI 只把 `last_decision_source == "local"` 标为本地，没有标记 `local_opening_formula`；
- H2-A1/A1a 与 K-A1 至 K-A3d2 已封板；K-A3c2 原正式结论保持无效，下一步为 K-A3d3a 真实模型质量试验前置审计与授权请求。

## 5. 当前实施阶段

### Step I：统一阶段模型

状态：完成。定向 71 项、全量 126 项测试通过。

目标：

- 新增唯一的阶段分类模块；
- 开局策略、动作剪枝、RAG 和提示词共用同一阶段结果；
- 删除或停止使用重复的阶段判断。

验收：

- 边界值测试完整；
- 同一 observation 在所有模块中阶段一致；
- 不改变合法动作集合。

### Step J：逐玩家牌面信念状态

状态：J-A 至 J-D1c3c2c3c2b 已完成，confidence 默认关闭。H2-A1/A1a 与 K-A1 至 K-A3d2 已完成；K-A3c2 原正式运行无效，下一步为 K-A3d3a。

目标：

- 精确维护两副牌级别的未见牌池，保留点数和花色；
- 按玩家记录已出牌、pass 次数和剩余牌数；
- 输出逐玩家 `possible / likely / confirmed` 信息；
- 所有推断带来源和置信度；
- 只有逻辑唯一时才能标记 `confirmed`。

当前阶段已包含确定性公开事实、硬约束、完整残局枚举、token/rank 级精确物理权重和经策略多样性校准的组合边际契约；排序保持 hard-only neutral。runtime confidence 虽可默认关闭地生成和序列化，但动作质量评测未观察到净增益，因此不进入默认策略消费；仍不做 MCTS 或蒙特卡洛搜索。

验收：

- 未见牌池与真实公开历史 100% 一致；
- 逢人配按 `carrier_cards` 计入真实已出牌；
- 每位玩家剩余容量与 `other_players.hand_count` 一致；
- pass 只作为软证据，不产生错误的硬排除；
- 推断结果可序列化、可测试、可审计。

详细设计见 `docs/BELIEF_STATE.md`。

实施拆分：

1. J-A：牌池守恒、真实已出牌、逐玩家公开状态和诊断，已完成；
2. J-B1：未见牌可能归属域、玩家容量约束和一致性诊断，已完成；
3. J-B2：关键残局的有限可行分配与唯一性证明，已完成；
4. J-C1：使用离线真实手牌建立覆盖率、错误确认和边界违例基线，已完成；
5. J-C2a：从公开历史提取 pass 响应、首出/跟牌和公开牌型事件，已完成；
6. J-C2b1：仅用敌方单张后 pass 建立有上限的 rank 软评分，已完成；
7. J-C2b2：扩展离线评测为并列分数友好的 Top-K 指标，做零软分/实际软分消融，已完成；
8. J-C3a：固定种子离线残局样本采集、总体和分阶段聚合，已完成；
9. J-C3b：用独立固定种子和预注册门槛运行 RuleBasedAI 正式基准，已完成；
10. J-C3c1：实现 evaluation-only 战略性 pass 策略和策略分层报告，已完成；
11. J-C3c2：用独立固定种子运行策略分布稳健性验收，已完成，判定拒绝；
12. J-C3d1：移除无条件 pass 负分并恢复零软分 hard-only ranking，已完成；
13. J-C3d2：验证 neutral ranking 在 forced/战略 pass 轨迹下均不损失召回，已完成；
14. J-D1a：聚合完整分配的精确物理权重和 token 边际整数计数，已完成；
15. J-D1b：在完整 matrix 上聚合 rank 持有与副本数的精确整数边际，已完成；
16. J-D1c1：建立单样本、evaluation-only 的概率评分与校准充分统计量，已完成；
17. J-D1c2a：从单样本原始充分统计量精确微聚合 Brier、copy MSE、ECE/MCE，已完成；
18. J-D1c2b：实现固定 seed 残局采集器并运行开发容量试验，已完成；
19. J-D1c2c：使用预注册独立语料运行正式校准，已完成；
20. J-D1c3a：建立 forced/25/50/100 strategic-pass marginal corpus 载体并运行开发试验，已完成；
21. J-D1c3b：使用独立 seed 运行多策略正式校准，已完成但支持度不足，判定 `benchmark_invalid`；
22. J-D1c3b2：不改模型、分桶或阈值，使用全新 seed 扩大独立样本并重新正式验收，已完成并通过；
23. J-D1c3c1：建立 critical-endgame-only 的 runtime confidence 数据契约，已完成；
24. J-D1c3c1a：严格布尔标志、玩家集合和非法分子守恒路径，已完成；
25. J-D1c3c2a：建立默认关闭的 pipeline 和 DeepSeek shadow 审计，证明动作与 prompt 等价，已完成；
26. J-D1c3c2b1：建立有界、确定、精确分数的 prompt payload，不接入模型，已完成；
27. J-D1c3c2b2：增加默认关闭的 prompt 消费开关并保持关闭态完全兼容，已完成；
28. J-D1c3c2c1：建立四策略配对 prompt 覆盖、预算与精确插入基准并运行开发试验，已完成；
29. J-D1c3c2c2：使用独立 seed 正式验收 prompt readiness 与成本，双运行完成但完整审计证据未留存，判定 `benchmark_invalid`；
30. J-D1c3c2c2a：使用仓库外 canonical JSON 审计文件和全新 seed 恢复正式验收，已完成并通过；
31. J-D1c3c2c3a：建立 evaluation-only、provider 可注入的固定配对动作消融载体，已完成并通过；
32. J-D1c3c2c3b：经用户授权后预注册并运行小规模真实 DeepSeek 响应安全与动作变化验收，已完成并保留；
33. J-D1c3c2c3c1：建立同状态动作分支和确定性 RuleBased 续局质量代理，已完成并通过；
34. J-D1c3c2c3c2：用独立语料运行真实模型动作质量验收，已执行但未完成，判定 invalid；
35. J-D1c3c2c3c2a：用全新 seed 和耐久后台进程恢复同一正式验收，运行完整但正式键序审计失败，判定 invalid；
36. J-D1c3c2c3c2b：只读复核 c3c2a 不可变证据并显式映射策略，已完成，判定无观察到的质量增益；
37. confidence 策略接入：停止推进，保持默认关闭；
38. H2-A1：建立开局动作残余结构代价、避免无收益拆组，并修复公式来源日志，已完成；
39. H2-A1a：精确公开 fixture、真实评分和未知 token fail-closed，已完成并核验；
40. K-A1：建立只读公开信息的策略意图上下文与确定性路由契约，已完成；
41. K-A1a：严格 phase context 数值类型并聚合多项 diagnostics，已完成并核验；
42. K-A2a：在 DeepSeek 主链做默认关闭的策略意图 shadow 装配，已完成并验证；
43. K-A2b1：建立 evaluation-only 离线路由分布载体并运行开发容量试验，已完成，初次严格复核未通过；
44. K-A2b1a：严格复核 router source、phase、available reason-intent 和 unavailable 中性契约，已完成并封板；
45. K-A2b2：根据开发分布运行独立 seed 正式覆盖验收，已完成，判定 `strategy_router_coverage_insufficient`；
46. K-A2b2a：不改实现和门槛，使用全新 seed 将语料扩大到每策略 200 局，已完成并通过；
47. K-A3a：建立有界、默认不消费的 intent prompt payload 初版，已实现但严格复核未通过；
48. K-A3a1：补齐路由优先级与跨字段一致性，已完成并封板；
49. K-A3b：增加默认关闭的 intent prompt 消费接线，已完成并封板；
50. K-A3c1：建立 evaluation-only prompt 覆盖、成本与配对摘要载体，已完成并通过；
51. K-A3c2：使用独立 seed 正式验证 prompt coverage 与字符成本，已完成；结构和覆盖通过，但预注册字符包络失败，判定无效；
52. K-A3c2a：穷举并锁定 phase×reason 的精确字符包络测试契约，已完成并封板；
53. K-A3c2b：以全新 seed `19000..19199` 和预先锁定的正确包络恢复正式验收，已完成并通过；
54. K-A3d1：建立 evaluation-only、provider 可注入、四阶段分桶的策略意图动作消融载体，已完成并通过；
55. K-A3d2：建立同状态 off/on 动作的 RuleBased 分支续局质量代理载体，已完成并通过；
56. K-A3d3a：完成真实模型质量试验的检查点、预算、安全门槛和明确授权前置，下一步。

J-A 验证结果：

- `python -m unittest tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q`：31 项通过；
- `python -m unittest discover -q`：141 项通过；
- 未修改 `engine/`、现有 `CardTracker`、RAG 或 DeepSeek 提示词。

J-B1 验证结果：

- `python -m unittest tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q`：43 项通过；
- `python -m unittest discover -q`：153 项通过；
- 只建立公开硬约束，不枚举完整分配，不输出概率或软推断。

J-B2 验证结果：

- `python -m unittest tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q`：61 项通过；
- `python -m unittest discover -q`：171 项通过；
- 只做受控确定性分配枚举；截断结果不确认、不缩小硬归属域。

J-C1 验证结果：

- `python -m unittest tests.test_belief_metrics tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q`：78 项通过；
- `python -m unittest discover -q`：188 项通过；
- ground truth 仅进入离线评测，运行时模块没有 `evaluation` 依赖。

J-C2a 验证结果：

- `python -m unittest tests.test_card_signals tests.test_belief_metrics tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q`：92 项通过；
- `python -m unittest discover -q`：202 项通过；
- 只提取公开行为事件，没有软评分、概率、置信度或策略集成。

J-C2b1 验证结果：

- `python -m unittest tests.test_card_ranker tests.test_card_signals tests.test_belief_metrics tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q`：107 项通过；
- `python -m unittest discover -q`：217 项通过；
- 只有一个未校准 pass 启发式，尚无多种子 Top-K 改进证据。

J-C2b2 验证结果：

- `python -m unittest tests.test_ranking_metrics tests.test_card_ranker tests.test_card_signals tests.test_belief_metrics tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q`：120 项通过；
- `python -m unittest discover -q`：230 项通过；
- 只建立单样本、并列安全的零软分消融指标；尚无多种子改进证据。

J-C3a 验证结果：

- `python -m unittest tests.test_rank_benchmark tests.test_ranking_metrics tests.test_card_ranker tests.test_card_signals tests.test_belief_metrics tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q`：130 项通过；
- `python -m unittest discover -q`：240 项通过；
- 固定种子运行、阶段采集、原始计数微聚合和真值隔离已经建立；
- seed `0..19` 的开发试跑只用于测量容量：866 个 eligible、480 个 evaluated、386 个因每局 24 上限跳过，不能作为正式启发式结论。

J-C3b 正式结果：

- HEAD：`39bd0247b9459999cdeb489703ff288eed7df791`；
- seed `1000..1199`，两次 200 局运行报告和 canonical JSON SHA-256 完全一致；
- 8719 个目标阶段样本全部有效，无截断、无诊断；
- candidate recall 和 Top-1/Top-3 recall 无回退；
- overall Top-1 precision `+0.007357`、Top-3 precision `+0.006385`、MRR `+0.003233`；
- 唯一判定：`retain_for_policy_diverse_validation`；
- 该结论只覆盖 RuleBasedAI 的被迫 pass 轨迹，不授权置信度校准或策略接入。

J-C3c1 验证结果：

- `python -m unittest tests.test_pass_policy_benchmark tests.test_rank_benchmark tests.test_ranking_metrics tests.test_card_ranker tests.test_card_signals tests.test_belief_metrics tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q`：140 项通过；
- `python -m unittest discover -q`：250 项通过；
- rate 0/25/50/100 的公开、确定性战略 pass 轨迹和隔离报告已经建立；
- seed `20..29` 开发试跑中，25% 战略 pass 的 overall Top-3 recall delta 约为 `-0.126899`，显示当前无条件 pass 负向信号存在明显策略分布风险；
- 该试跑不用于正式判定，J-C3c2 必须使用独立 seed 和预注册召回护栏。

J-C3c2 正式结果：

- HEAD：`f1bfabd7ba136553c12ed61824b79f8e4b9ef446`；
- seed `2000..2099`，四种策略各 100 局，两次报告和 SHA-256 完全一致；
- 所有数据完整性、策略行为、硬候选安全和 forced-only 复验通过；
- 25% 战略 pass 下 overall Top-1/Top-3 recall delta 分别为 `-0.170742` / `-0.092955`；
- near-open/critical Top-3 recall delta 分别为 `-0.088401` / `-0.099062`；
- 唯一判定：`reject_unconditioned_pass_signal`；
- MRR 正增量不能覆盖 Top-K 真实 rank 召回失败；
- 当前 pass 负分必须撤销，不能进入置信度校准或 runtime。

J-C3d1 验证结果：

- `agents/card_ranker.py` 已删除 pass penalty 参数、评分路径和 evidence；
- hard candidates、confirmed、J-B2 收窄和通用 metrics 保持稳定；
- 所有 possible candidate 恢复零软分、空 evidence；
- 定向 140 项、全量 250 项测试通过；
- seed `30..34` 开发试跑中，四种 pass 策略的全部 overall delta 严格为 0；
- 下一步只做独立 seed neutral 封板，不恢复被拒绝信号。

J-C3d2 正式结果：

- HEAD：`3ee050e1ff80615038348b11e7ba185ded463ca2`；
- seed `3000..3049`，四策略各 50 局，两次报告与 SHA-256 一致；
- 所有对局和样本有效，无截断或 diagnostics；
- 12 个 bucket 的 baseline/soft snapshot 完全相等；
- 所有 delta 精确为 0；
- 判定：`neutral_baseline_verified`；
- J-C 分支封板，后续不恢复无条件 pass 负分。

J-D1a 验证结果：

- `CardAllocationResult.physical_assignment_count` 聚合所有完整 count matrix 的物理权重；
- `PlayerAllocationBounds` 聚合逐 token 持有分子与副本数加权分子；
- 权重使用 `math.factorial` 和 Python 整数，未引入第三方依赖或浮点数；
- 不完整、无效、跳过和无解结果不输出部分权重或边际；
- token 副本数分子满足全局守恒；
- 定向 132 项、全量 256 项测试通过；
- 该步骤没有输出 rank 边际、概率、置信度或策略收益。

J-D1b 验证结果：

- 新增逐玩家 `holding_assignment_count_by_rank` 与 `copy_assignment_count_by_rank`；
- rank 持有分子按同一 matrix 中同 rank token 的并集计一次；
- rank 副本数分子等于对应 token 副本数分子之和，并满足跨玩家守恒；
- `10S`、`SJ`、`BJ` 等 token 使用严格公开映射；
- 非法 token 或 token/rank 牌池不一致会在搜索前 fail closed；
- 非完整结果不泄露部分 rank 边际；
- 定向 139 项、全量 263 项测试通过；
- 该步骤尚未输出概率、置信度、校准结论或策略收益。

J-D1c1 验证结果：

- 新增冻结的 `MarginalCalibrationBin` 与 `MarginalEvaluationReport`；
- presence Brier、rank copy 平方误差和桶内预测和全部用 `Fraction` 累计；
- 每个活跃外部玩家 × 每个正数公开 rank 都评分，包含负例；
- fail-closed 覆盖 allocation、rank 边际、守恒和显式真值；
- invalid 报告计数归零、误差为 `0/1`，并固定输出 10 个空桶；
- runtime 目录没有新 evaluation 依赖，报告不保留真实手牌或逐 pair 明细；
- 定向 152 项、全量 276 项测试通过；
- 尚未运行多种子校准，也未生成 runtime 置信度。

J-D1c2a 验证结果：

- 新增 `MarginalCalibrationAggregate` 与 `MarginalBenchmarkBucket`；
- 从 valid 报告原始误差和与 pair count 做精确微聚合；
- 输出 Brier mean、copy MSE、正例率、确定性错误率、ECE 和 MCE 的最简分数；
- 十档预测和跨样本精确通分，空桶稳定为 `0/1`；
- invalid 报告仅进入无效计数和同报告去重后的诊断类别；
- malformed 报告显式失败，输出顺序无关且不保留样本内容；
- 定向 166 项、全量 290 项测试通过；
- 尚未实现 seed 采集器或运行校准语料。

J-D1c2b 验证结果：

- 新增 critical-only collector 与共享 evaluation truth helper；
- overall 和外部牌数三个互斥桶均由原始报告精确聚合；
- 开发 seed `40..59` 两次完整报告和 SHA-256 一致；
- 20/20 局完成，522 个样本全部有效，无跳过和 diagnostics；
- 三个桶分别有 171、177、174 个样本；
- overall Brier mean `335904977521 / 1779098428800`；
- overall copy MSE `135996253741 / 667161910800`；
- overall ECE `459367 / 21393680`，MCE `10435 / 157608`；
- certainty error rate 为 `0/1`；
- 定向 179 项、全量 303 项测试通过；
- 判定 `development_capacity_verified`，尚不是正式校准。

J-D1c2c 预注册参数：

- seed `5000..5099`，100 局，完整运行两次；
- 级牌 `2`，`max_steps=5000`，每局最多 128 样本；
- 外部牌上限 12、节点上限 1,000,000、解上限 100,000；
- 默认 `RuleBasedAIAgent`；
- 正式运行期间不改实现、分桶、参数、阈值或样本筛选。

J-D1c2c 正式结果：

- 两次 100 局报告完全相同，SHA-256 为 `c4a91d81bed216e919189fe4fdddf76c76ee8e35eb28f5fcae21ebc9e401e190`；
- 100/100 局完成，2727 个样本全部有效，无 skip 或 diagnostics；
- 三个外部牌数桶有效样本均超过 900；
- overall 与三个桶的 certainty error 均为 0；
- overall/三桶的 ECE、Brier skill、支持度 MCE 全部通过预注册门槛；
- 判定 `retain_for_policy_diverse_calibration`；
- 该结论只覆盖默认 RuleBasedAI，不授权 runtime confidence。

J-D1c3a 验证结果：

- 多策略 wrapper 只复用 evaluation-only agent 与现有 marginal collector；
- 四个 rate 的 agent、对局、计数器和 corpus 完全隔离；
- 开发 seed `60..69` 双运行 SHA-256 均为 `dc5bfa083d686e57cb711e9892738713904da96178988931deda7318427a58a3`；
- 四策略各 10/10 局完成，invalid/skip/diagnostics 全为 0；
- 主动 pass 比例呈 0、约 0.397、约 0.496、1.0 的行为梯度；
- 三个 external bucket 在每个策略中均有样本；
- 定向 187 项、全量 311 项测试通过；
- 判定 `policy_diversity_capacity_verified`，尚未形成正式多策略校准结论。

J-D1c3b 预注册参数：

- seed `7000..7049`，四策略各 50 局，完整运行两次；
- 级牌 `2`，每局最多 128 样本，其他搜索上限保持不变；
- 正式运行期间不改实现、策略、gate、seed、分桶或校准门槛；
- 任一策略或任一外部牌数桶失败都不能被跨策略平均掩盖。

J-D1c3b 正式结果：

- seed `7000..7049` 四策略各 50 局，双运行报告完全相等；
- SHA-256 为 `67ed39e3b39b22dd7f2b660c70dc66eb5f6add3c11c0e3dc8315a1a8ca6a7eee`；
- 四策略全部完成，无 invalid、skip 或 diagnostics，行为梯度与样本守恒通过；
- 15/16 个策略/范围通过全部护栏；
- `strategic_pass_100 / external_0_4` 只有一个 count>=100 的支持 bin，未达到至少两个支持 bin 的前提；
- 唯一判定 `benchmark_invalid`，不授权 runtime confidence，也不构成模型拒绝结论。

J-D1c3b2 预注册方向：

- seed `7000..7049` 只用于样本量规划，永久排除出后续验收；
- 使用全新 seed `8000..8119`，四策略各 120 局，完整运行两次；
- 保持实现、策略 gate、十档分桶、支持阈值和全部数值护栏不变；
- 扩容目的仅是让偏斜的 `strategic_pass_100 / external_0_4` 获得足够支持，不能做事后调参；
- 只有完整性、支持度和全部数值护栏同时通过，才能进入 J-D1c3c。

J-D1c3b2 正式结果：

- seed `8000..8119` 四策略各 120 局，双运行报告完全相等；
- SHA-256 为 `425bf197c7642894ebb6a0293383b94c160bdddb9dc44c180216278e200e113e`；
- 四策略全部完成，无 invalid、skip 或 diagnostics，主动 pass 比例严格递增；
- 每个策略的三个 external bucket 均超过 980 个有效样本；
- 16 个范围全部满足至少两个支持 bin、certainty=0、ECE、Brier skill 和 supported MCE 护栏；
- 判定 `policy_diverse_calibration_verified`；
- 只授权进入最小 runtime confidence 契约设计，不授权动作决策或胜率声明。

J-D1c3c1 设计边界：

- 新增独立 runtime 模块，消费 `CardBeliefState`、`CardConstraintState` 和完整 `CardAllocationResult`；
- 只覆盖 `critical_endgame` 且外部未知牌不超过 12 张的已验证范围；
- 公开整数分子/分母，不做浮点四舍五入、概率重映射或主观高/中/低分档；
- 任一前置条件或守恒校验失败时返回无玩家、零分母的 unavailable 状态；
- 不导入 `evaluation/`，不读取 observation、history 或 ground truth；
- 本步骤不修改 DeepSeek、RAG、剪枝、提示词或动作选择。

J-D1c3c1 实现结果：

- 新增 `agents/card_confidence.py` 与 `tests/test_card_confidence.py`；
- available 仅限已验证 critical 范围，输出精确 presence/copy 整数边际；
- 已覆盖阶段、精确性、搜索、外部数量、分母、玩家、容量、rank 和多数分子异常；
- 定向 76 项、全量 318 项测试通过；
- 新模块无 evaluation、ground truth、engine state、observation/history、DeepSeek 或 RAG 引用；
- 现有决策路径未导入新模块。

J-D1c3c1a 硬化范围：

- exact、consistent、search-complete 标志必须是实际 `True`，不能接受 `1` 或 truthy 字符串；
- constraints 与 allocation 不得包含公开 active external 集合之外的额外玩家；
- copy 守恒只能使用已验证整数，不得对 malformed 原始值直接求和；
- 字符串、`None`、float、`bool` 等非法 copy 分子必须稳定返回 unavailable，不能抛异常；
- 正常 available 输出和所有现有测试保持不变；
- 以上硬化已完成，允许进入 J-D1c3c2a shadow 装配。

J-D1c3c1a 实现结果：

- 四个布尔语义字段改为严格 `is True`；
- belief/constraints/allocation 的正容量外部候选玩家集合严格比较；
- copy 分子验证后进入规范化整数表，守恒求和不再触碰原始 malformed 值；
- 合法 available `to_dict()` snapshot 保持不变；
- 单文件 11 项、相关 80 项、全量 322 项测试通过；
- 新模块与现有 decision path 边界扫描通过。

J-D1c3c2a 设计边界：

- 新增独立 runtime pipeline，复用统一 phase，只在 critical 阶段执行精确枚举；
- `DeepSeekAIAgent` 新增显式 `card_confidence_shadow_enabled=False`，不接 AppConfig 或环境变量；
- 默认关闭时不导入、不调用 pipeline，现有 client 调用参数、prompt 和 action ID 完全不变；
- 开启时只更新只读审计字段 `last_card_confidence`，不得传给 prompt、RAG、剪枝或策略；
- 每次决策开始清空旧审计值，local shortcut 不计算 confidence；
- pipeline 失败返回 unavailable，不能阻断或改变 DeepSeek 降级路径；
- shadow off/on 动作等价已证明，下一步先封板 J-D1c3c2b1 序列化，再考虑 J-D1c3c2b2 消费。

J-D1c3c2a 实现结果：

- 新增 `agents/card_confidence_pipeline.py` 与对应测试；
- `DeepSeekAIAgent` 增加默认关闭的 shadow 开关和最后审计状态；
- 非 critical 不构建 belief 或 allocation，critical 公开链路各执行一次；
- pipeline 正常 unavailable 原样保留，异常规范为 `pipeline_error`；
- shadow 结果不传给 prompt、RAG、剪枝、client 或动作选择；
- off/on 的 client kwargs、动作、fallback 与 decision source 完全一致；
- 定向 40 项、相关 124 项、全量 331 项测试通过。

J-D1c3c2b1 设计边界：

- 新增独立 formatter 模块和单元测试，不修改 agent 或 DeepSeekClient；
- 只格式化已验证 available source/scope；
- 使用约分精确分数，不输出 float、百分比或 high/medium/low；
- 保留全部玩家和正数公开 rank，不基于概率删选；
- 输出必须在固定字符预算内；超预算整体 omitted，不能截断；
- 后续 J-D1c3c2b2 只能消费该封板 payload，不能直接序列化 runtime dataclass。

J-D1c3c2b1 实现结果：

- 新增 `agents/card_confidence_prompt.py` 与对应测试；
- payload frozen/slots，ready/omitted 字段稳定且 JSON 友好；
- formatter 严格复核 phase/source/scope、外部数、分母、玩家容量和 rank 布局；
- 分数使用 `gcd` 约分，固定边界说明，不输出 float 或主观标签；
- 2400 字符预算超限时整体 omitted，不截断；
- 相关 22 项、DeepSeek/RAG/剪枝 52 项、全量 338 项测试通过。

J-D1c3c2b2 设计边界：

- agent 增加 `card_confidence_prompt_enabled=False`，并要求 prompt 开启时 shadow 必须开启；
- 仅从 `last_card_confidence` 构建封板 payload，不直接读取 observation 或中间边际；
- ready payload 作为类型化对象传给 DeepSeekClient；
- omitted/unavailable 时不增加 client keyword，不增加 prompt 章节；
- DeepSeekClient 只接受合法 ready payload，并在记牌信息之后插入固定 `【残局牌面信念】` 章节；
- 关闭态和 omitted 态 prompt/client kwargs 保持原样；
- 不修改 RAG、剪枝、legal actions、fallback 或默认配置。

J-D1c3c2b2 实现结果：

- agent 增加默认关闭的 prompt 开关和 payload 审计字段；
- 只允许 off、shadow-only、prompt 三种严格 bool 模式；
- ready payload 是 client kwargs 的唯一差异；
- omitted/unavailable 与 shadow-only kwargs、prompt、动作和 fallback 相同；
- client 对 malformed payload 整体忽略；
- 新章节只插入一次且不改变其他 prompt 段落；
- 定向 54 项、相关 48 项、全量 345 项测试通过。

J-D1c3c2c1 设计边界：

- evaluation-only collector，不发出 DeepSeek 网络请求；
- 复用 strategic-pass 0/25/50/100 四种独立轨迹；
- critical 样本构建同一份 off/on prompt，唯一差异应为封板 confidence 章节；
- 聚合 ready/omitted、诊断、payload 字符和 prompt 字符 delta；
- 报告不保留 seed、observation、prompt、手牌、玩家或逐样本内容；
- 开发 seed 只验证容量、确定性、覆盖和成本，不形成动作质量结论。

J-D1c3c2c1 实现与开发结果：

- 新增 `evaluation/confidence_prompt_benchmark.py` 与对应测试；
- 四策略独立采集 critical 样本并按三个 external bucket 聚合；
- off/on prompt 只在内存配对，报告不保留 prompt、observation 或玩家明细；
- seed `80..89` 双运行报告完全一致，SHA-256 为 `15370d48a49a8067d9790bbd89b54431c54e6a4dd5d5403a3b2ec23d10ccfd6b`；
- 四策略共 1084 个样本全部 ready，零 omitted、budget omitted、pair mismatch 和 diagnostics；
- 每个样本 delta 精确为 payload chars + 11；
- 定向 28 项、相关 77 项、全量 351 项测试通过；
- 判定 `confidence_prompt_coverage_capacity_verified`。

J-D1c3c2c2 正式方向：

- 已在检查点 `bc689a37f462672033d754cce7060897d70c7612` 使用 seed `10000..10049` 完成四策略各 50 局双运行；
- report、`to_dict()`、canonical JSON 和 SHA-256 两次相等，哈希为 `1d6506250def487c16d4da2c4fcf1aed2cdfd13231a6096347b768e0c8680a8f`；
- stdout 被工具层截断，未保留四策略全部分桶聚合，无法审计完整性、coverage 和字符成本门槛；
- 按预注册约束没有第三次运行、补采或调整参数；
- 唯一判定 `benchmark_invalid`，不得进入 J-D1c3c2c3。

J-D1c3c2c2a 恢复方向：

- 已使用全新 seed `11000..11049` 完成四策略各 50 局双运行；
- 两份 9218-byte canonical JSON 逐字节一致，SHA-256 为 `679f1f4b7f33fc821cdda4725681abbf86a3204c3b03775c0b2858ce2df9d37b`；
- 四策略共 5733 个样本，16 个范围全部 available/ready/exact insertion，零 omitted/mismatch/diagnostics；
- payload 最大 683 字符，固定章节开销精确为每样本 11 字符；
- 判定 `confidence_prompt_coverage_verified`；原 seed `10000..10049` 结果仍为 `benchmark_invalid`；
- 原审计摘要错误依赖 JSON 键迭代顺序，恢复解析器按策略名/rate 只读复核；后续不得把 canonical 键顺序当业务顺序。

J-D1c3c2c3a 设计方向：

- 已只新增 evaluation 动作消融模块与对应测试，未修改 runtime、engine、client、RAG、CLI 或配置；
- critical 合格样本按固定 SHA-256 优先级选择，only-pass、一次出完和 unavailable/omitted/mismatch 不调用 provider；
- off/on kwargs 只差 confidence payload，每桶 AB/BA 平衡，一侧异常仍调用另一侧；
- provider 结果按异常、malformed、no-action、类型、legal/prompt 域严格分类，不使用 fallback；
- seed `120..129` 四策略每桶 4 个样本双运行，report 完全相等，SHA-256 为 `ce3262ad0e8f3e3baf0e885ad75f3a11fcc57d5b035599fdce06fe9c7d7a9095`；
- 每轮 48 pair / 96 次假 provider 调用全部 valid，每桶 AB/BA 各 2；
- 判定 `confidence_action_ablation_harness_verified`，不宣称 confidence 改善动作。

J-D1c3c2c3b live pilot 方向：

- 已在 `e0065c6a3da70b3d4ded4b394817bfab3351c113` 上使用 `deepseek-v4-pro`、60 秒 timeout、零重试完成；
- seed `13000..13009` 四策略每桶 2 个样本，共 24 pair / 48 次真实请求；
- 48 个响应全部在 prompt candidates，24 pair 全部 both-valid，零异常和解析/合法性失败；
- same/changed 总计 13/11，off/on pass 均为 6，pressure 均为 0；
- 总耗时 1411.005 秒，审计文件均已仓库外持久化并哈希；
- 判定 `retain_for_action_quality_evaluation`；动作差异仅为描述性结果，不排除服务非确定性。

J-D1c3c2c3c1 实现与开发结果：

- 只新增 `evaluation/confidence_action_quality.py` 和对应测试，未修改 c3a、engine、runtime、DeepSeek client、RAG、CLI 或配置；
- c3a seed `120..129` canonical SHA-256 仍为 `ce3262ad0e8f3e3baf0e885ad75f3a11fcc57d5b035599fdce06fe9c7d7a9095`；
- 仅为固定优先级入选样本保留内存 clone，公开等价校验、分支执行和 RuleBased 续局均不访问 `game._state`；
- same action 单分支复用，changed action 双分支独立运行；终局和质量字典序按预注册公开契约执行；
- seed `140..149` 双运行完全一致，canonical SHA-256 为 `3a989255412180b293afcd9f99a8a32d6d399c891d829bd16d37e94b5f64eaa6`；
- 24 pair 全部 both-valid、quality-evaluable，全部 rollout 完成，零 diagnostics；
- 四策略 on-better/off-better/tie 为 1/1/4、1/0/5、0/0/6、1/0/5；
- 新模块 5 项、相关 81 项、全量 362 项测试通过；
- 判定 `confidence_action_quality_harness_verified`，不形成真实模型动作质量或胜率结论。

J-D1c3c2c3c2 正式结果：

- c3c1 已提交为 `ad85662a47f126991e8ebe0360dc0c6c4a2f1be6`；
- seed `15000..15009`、四策略、每桶 2、最多 48 次零重试请求；
- 外层执行器在 30 分钟中断，子进程随后终止，未恢复或重跑；
- ledger 连续 45 条，off/on=23/22，全部 returned；
- 没有完整 `report.json`，不计算 same/changed、rollout 或质量结果；
- 失败证据已在仓库外持久化并哈希；
- 判定 `quality_benchmark_invalid`。

J-D1c3c2c3c2a 正式结果：

- seed `16000..16009`，48/48 请求、24 pair、全部 rollout 和零 diagnostics 均完成；
- 四策略均 10/10/0，主动 pass 比例严格递增；
- 持久后台进程正常退出，完整 ledger/report/summary/completion 均已落盘并哈希；
- 正式 summary 错误依赖 canonical JSON 键顺序，`integrity_pass=false`；
- 原证据未改写，未重跑，未形成质量结论；
- 判定 `quality_recovery_invalid`。

J-D1c3c2c3c2b 恢复方向：

- 不联网、不读 key、不发送请求，不修改任何原审计文件；
- 在新仓库外目录运行只读验证器，先复核全部源文件 hashes；
- 以显式 `forced_only=0`、`strategic_pass_25=25`、`strategic_pass_50=50`、`strategic_pass_100=100` 映射校验策略，不依赖 mapping 迭代顺序；
- 独立重算 ledger、策略、分桶、pair、rollout、diagnostics、JSON 和隐私守恒；
- 原 summary 除键序检查外若存在任何其他失败，恢复审计立即 invalid；
- 两次只读验证必须生成完全相等的 canonical recovered summary；
- 完整性恢复后才按 c3c2 原预注册 overall 门槛形成质量判定，原 c3c2a invalid 不被覆盖。

J-D1c3c2c3c2b 结果：

- 原 summary 只有由 canonical JSON 键序误用导致的派生 `integrity_pass=false`；
- 显式策略映射、全部源 hashes、48 请求、24 pair、33 branches 和所有守恒独立复核通过；
- 双验证输出逐字节一致；
- overall same/changed=15/9，on/off better=0/0，tie=24，双方 team win 均为 10；
- 唯一判定 `no_observed_action_quality_gain`；
- 不进入完整 DeepSeek 对局评估，confidence 默认保持关闭。

### Step K：中局策略路由与残局决策

状态：K-A1 至 K-A3d2 已封板。K-A3c2 原唯一判定保持 `strategy_intent_prompt_coverage_benchmark_invalid`；K-A3c2b 独立恢复判定为 `strategy_intent_prompt_coverage_recovery_verified`。下一步为 K-A3d3a。

目标：

- 中局明确区分 `run_out`、`control`、`support_teammate`、`block_opponent`；
- 策略路由器先选择策略意图，RAG 再为意图检索经验；
- 近似明牌残局使用逐玩家信念状态；
- 危险对手、队友跑牌和牌权转移进入结构化决策。
- 路由显式记录当前桌面动作来自队友还是对手，避免无收益压队友；
- 对手完成一次出牌后剩余不超过 2 张时进入阻断优先级。

验收：

- 路由结果对固定 observation 可复现；
- RAG 不单独决定动作；
- 模型只能从传入候选动作中选择；
- 固定种子和轮换座位 A/B 评测可重复。

K-A1 方向：

- 新增独立 `agents/strategy_router.py` 与对应测试；
- 只消费调用方传入的统一 phase、公开 observation、legal actions 和既有 hand evaluation；
- 输出 frozen/slots、JSON 友好的路由上下文，不修改候选动作；
- 先固定 `run_out`、`block_opponent`、`support_teammate`、`control` 四种意图及 fail-closed unavailable 状态；
- opening 不参与路由，继续由现有公式开局处理；
- 不接 DeepSeek、RAG、剪枝、confidence 或动作选择；
- 固定 fixture 验证优先级、团队关系、桌面领牌关系、紧急手数、弱/强牌和 malformed 输入；
- 纳入 `record.txt` 第 2、16、20 轮的最小公开 fixture，但不读取原始日志文件作为运行时依赖；
- 通过只授权 K-A2 shadow 集成，不代表策略质量提升。

K-A2a 方向：

- 在 `DeepSeekAIAgent` 增加严格布尔、默认关闭的 shadow 开关和非展示审计字段；
- 每次决策先重置审计字段，本地快捷路径和公式命中不运行 router；
- 其余路径复用已计算的唯一 phase 与手牌评估，只调用 router 一次；
- shadow 结果只写入审计字段，不进入 prompt、RAG、剪枝、client kwargs、fallback 或 action 选择；
- off/on 必须对模型调用、prompt、返回动作和 decision source 完全兼容；
- 通过只授权 K-A2b1 离线路由分布载体，不授权策略消费。

K-A2a 验证结果：

- 严格布尔开关默认关闭，每次决策重置非展示审计字段；
- 本地快捷路径跳过 router，普通链路复用同一 phase、原始 legal actions 和已有手牌评估；
- router 结果或异常都不改变 prompt、RAG、剪枝、fallback、action 和 decision source；
- 定向 25 项、相关 100 项、全量 396 项通过；
- 唯一判定 `strategy_router_shadow_verified`。

K-A2b1 方向：

- 新建 evaluation-only 多策略路由分布载体，不修改 runtime；
- 复用 forced-only 与 25/50/100% strategic-pass 公开策略，每个 rate 使用独立对局；
- 按 midgame/endgame/near-open/critical 和四种 intent 聚合 available、unavailable、reason、桌面领牌关系与 diagnostics；
- 单独记录 opening、only-pass、一次出完和样本上限跳过，保持计数守恒；
- 报告不保留 seed、样本 ID、observation、action、玩家或手牌明细；
- 先运行小型双运行开发容量试验，用实际分布为 K-A2b2 锁定门槛；本步不判定策略质量。

K-A2b1 复核结果：

- seed `200..209` 双运行报告、`to_dict()` 和 canonical JSON 完全相等，SHA-256 为 `32e42e0e7dc56377811fc52aa5d387d0b0f16e45102a3f88bea1a8e86d755ccb`；
- 四策略均 10/10/0，无 unavailable、invalid、duplicate、sample-limit 或 diagnostics；
- 四策略的四阶段均有 available 样本，主动 pass 比例严格递增；
- 单模块 8 项、相关 58 项、全量 404 项通过；
- 但 available 的 wrong source、wrong phase、unknown reason 和 reason-intent mismatch 均会被接受，unavailable 也缺少对 source/phase/非空 diagnostics/中性字段的复核；
- 唯一判定 `strategy_router_distribution_harness_invalid`。

K-A2b1a 方向：

- 只修改 `evaluation/strategy_router_benchmark.py` 和对应测试；
- 复核 context 类型、固定 source、与 bucket 一致的 phase、status 与 diagnostics；
- available 只接受已知 reason，且 reason 必须与 intent 映射一致；
- unavailable 必须有非空规范 diagnostics，且不保留任何玩家、领牌、手牌强度或意图结论；
- malformed context 统一记为 `invalid_router_result`，不泄露其中的伪 diagnostics；
- 合法语料报告字段与 canonical SHA-256 必须精确不变；
- 通过后才授权 K-A2b2，仍不授权策略消费。

K-A2b1a 验证结果：

- context 类型、固定 source、预期 phase、严格 bool/tuple、reason-intent 映射和 available 语义均已集中复核；
- unavailable 必须完全中性，malformed context 只计一次 `invalid_router_result`；
- 单模块 11 项、相关 61 项、全量 407 项通过；
- seed `200..209` 双运行报告与开发 SHA-256 `32e42e0e7dc56377811fc52aa5d387d0b0f16e45102a3f88bea1a8e86d755ccb` 精确不变；
- 唯一判定 `strategy_router_distribution_hardening_verified`。

K-A2b2 方向：

- 不修改仓库文件，只用全新独立 seed 运行现有载体两次；
- 审计四策略的对局、采样、phase、intent、reason、relation 与全部守恒；
- 使用仓库外完整 JSON 与哈希证据，显式按策略名和 rate 复核，不依赖 JSON 键序；
- 只验证覆盖可重复且非退化，不比较动作质量，不授权策略消费。

K-A2b2 正式结果：

- seed `16000..16099`、四策略各 100 局，双运行 canonical SHA-256 均为 `e77e5632b4b71f4a12fc1b213be78b413c70486f60e06e3f5cd35c941aa2d40d`；
- 四策略全部完成，无 unavailable、invalid、skip、duplicate 或 diagnostics，全部守恒和 pass 梯度通过；
- overall/phase intent、relation 和 reason 覆盖全部通过；
- forced/25%/50% 的 endgame available 为 583/660/663，低于预注册 700；
- 273 项检查只有上述三项失败，唯一判定 `strategy_router_coverage_insufficient`。

K-A2b2a 方向：

- 不改实现、策略、phase、分桶、采样规则或覆盖门槛；
- 永久排除 seed `16000..16099`，使用全新 seed `17000..17199`；
- 每策略扩大到 200 局并完整双运行，继续使用仓库外 canonical JSON 审计；
- 只解决预注册绝对样本容量，不把扩容结果解释为动作质量。

K-A2b2a 正式结果：

- seed `17000..17199`、四策略各 200 局，双运行 canonical SHA-256 均为 `ee321d18a50f923e92bbcc7e99c7e90a0ee87ac8b57b35b95e091f988c670c0e`；
- 四策略全部完成，无 unavailable、invalid、duplicate、sample-limit 或 diagnostics；
- 结构完整性 97/97、覆盖 176/176、总计 273/273 通过；
- 单模块 11 项、相关 61 项、全量 407 项通过；
- 唯一判定 `strategy_router_coverage_verified`。

K-A3a 方向：

- 新增独立 `agents/strategy_intent_prompt.py` 和对应单元测试；
- 只消费已经 available 的 `StrategyIntentContext`，严格复核 source、phase、intent、reason 与公开字段一致性；
- 输出 frozen/slots、JSON 友好、有固定字符预算的 ready/omitted payload；
- 使用固定文案映射，不透传任意字符串，不输出隐藏事实或把 intent 描述为规则命令；
- 本步不修改 DeepSeek client、agent、RAG、evaluation 或动作选择；
- 通过后只授权 K-A3b 默认关闭的 prompt 消费接线。

K-A3a 初次复核：

- fixed text、reason-intent 映射、预算、frozen/slots 与 omitted 清空均已实现；
- 单模块 7 项、相关 43 项、全量 414 项通过；
- 但局部 reason 校验没有重放 K-A1 路由优先级，多个跨字段矛盾 context 仍返回 ready；
- hand strength 与 total score、control score 与 total score、minimum count 与 urgent IDs 也未完整守恒；
- 唯一判定 `strategy_intent_prompt_contract_invalid`，不得进入 K-A3b。

K-A3a1 方向：

- 只修改 formatter 与对应测试，payload 字段和合法文本快照保持不变；
- 先验证 count/urgency/score 的内部守恒，再按 K-A1 固定优先级推导唯一 expected reason；
- context 的 reason 和 intent 必须与 expected reason 精确一致，否则整体 omitted；
- 覆盖被更高优先级条件遮蔽的 weak/control/urgency reason 反例；
- 通过后才授权 K-A3b 默认关闭的消费接线。

K-A3a1 验证结果：

- 九类预注册伪造 context 全部 omitted；
- score/strength、minimum/urgent IDs、teammate/leader urgency 守恒已锁定；
- 唯一 expected reason 按 K-A1 原优先级推导；
- 合法十 reason、三 snapshot 与固定文本保持不变；
- 单模块 11 项、相关 47 项、全量 418 项通过；
- 唯一判定 `strategy_intent_prompt_contract_hardening_verified`。

K-A3b 方向：

- 在 `DeepSeekAIAgent` 增加严格布尔、默认关闭且依赖 router shadow 的 prompt 开关；
- 只有 ready payload 才作为新增类型化 keyword 传给 client；
- client 独立复核 payload 并在固定位置精确插入一次；
- off、shadow-only、omitted 和异常路径的 kwargs、prompt、动作与 fallback 必须保持等价；
- 本步不让 intent 选择 RAG、改变剪枝或默认启用。

K-A3b 验证结果：

- off/shadow-only/prompt 三态与严格依赖已实现；
- ready 才增加类型化 keyword，client 对固定四行文本做独立复核；
- 插入顺序为 confidence、strategy intent、scene tags；
- omitted/异常路径保持原模型和 fallback 等价；
- 定向 56 项、相关 88 项、全量 424 项通过；
- 唯一判定 `strategy_intent_prompt_wiring_verified`。

K-A3c1 方向：

- 新增 evaluation-only 多策略×多阶段 prompt pair collector；
- 只使用公开 observation、legal actions、统一 phase、hand evaluation、router 与 formatter；
- 构建 off/on structured prompt，不调用模型或网络；
- 聚合 ready/omitted、精确插入、payload/prompt delta 字符成本、diagnostics 与 pair digest；
- 先运行小型双运行开发容量试验，为 K-A3c2 正式覆盖验收锁定门槛。

K-A3c1 验证结果：

- seed `300..309` 双运行 canonical SHA-256 均为 `032ff0964a0fe4c377c612f27263e553abfe22ad759d14b5714ebf788d280a20`；
- 四策略均 10/10/0，16 个 phase bucket 全部 ready；
- 零 unavailable、invalid、omitted、duplicate、limit、mismatch 与 diagnostics；
- payload 74..90 字符，delta 83..99 字符，逐样本精确相差 9；
- 定向 6 项、相关 52 项、全量 430 项通过；
- 唯一判定 `strategy_intent_prompt_coverage_capacity_verified`。

K-A3c2 方向：

- 先提交 K-A3c1 检查点并要求工作区干净；
- 使用全新 seed、每策略 200 局完整运行两次；
- 保持实现、策略、phase、采样、字符预算和全部 pair 规则不变；
- 仓库外保存完整 canonical JSON、审计摘要和文件哈希；
- 通过只授权 K-A3d1 evaluation-only 动作消融载体。

K-A3c2 正式结果：

- seed `18000..18199`，四策略各 200 局，双运行 canonical SHA-256 均为 `35587b8d532dc9ba3fc8d82d6f6a690692362a31a908c066b2ad4783bfd1d148`；
- 16 个策略×阶段桶全部 ready、精确插入且达到样本门槛，所有 invalid/omitted/mismatch/diagnostics 为 0；
- 四个 near-open 桶均出现合法的 payload/delta 最大值 `91/100`，违反预注册上界 `89/98`；
- 唯一判定 `strategy_intent_prompt_coverage_benchmark_invalid`，不得事后修改门槛追认通过。

K-A3c2a 方向：

- 只修改 formatter 单元测试，不修改固定文本、runtime 或 benchmark；
- 穷举四阶段×十种 reason，锁定每个组合的精确字符数；
- 锁定理论包络：midgame `74..81 / 83..90`、endgame `74..81 / 83..90`、near-open `84..91 / 93..100`、critical `83..90 / 92..99`；
- 通过后才允许 K-A3c2b 使用未用过的新 seed 做正式恢复，不直接进入动作消融。

K-A3c2a 验证结果：

- 只修改 `tests/test_strategy_intent_prompt.py`，未修改 formatter、runtime、evaluation benchmark 或 docs；
- 40 个阶段×reason 组合全部通过真实 formatter，均为 ready、空 diagnostics，且 `char_count == len(text)`；
- payload 包络锁定为 midgame/endgame `74..81`、near-open `84..91`、critical `83..90`；
- 固定插入 delta 包络锁定为 `83..90`、`83..90`、`93..100`、`92..99`；
- 定向 12 项、相关 60 项、全量 431 项通过，唯一判定 `strategy_intent_prompt_envelope_contract_verified`。

K-A3c2b 方向：

- 先提交 K-A3c2a 检查点并确保工作区干净，不 stash、还原或混入现有 docs 改动；
- 使用未使用 seed `19000..19199`、四策略各 200 局，正式 benchmark 恰好运行两次；
- 使用 K-A3c2a 已封板包络，不修改 formatter、benchmark、采样或门槛；
- 报告先写入仓库外审计目录，再输出摘要，避免工具输出截断导致证据丢失；
- 通过只授权规划 K-A3d1 evaluation-only 动作消融，不默认启用 intent prompt。

K-A3c2b 验证结果：

- HEAD / K-A3c2a 检查点为 `a8cf1291de2fde62c6c7ed7ecfeaa878671f5490`，运行前后工作区干净；
- seed `19000..19199`、四策略各 200 局，正式 benchmark 恰好运行两次；
- 两份 canonical JSON 逐字节相同，SHA-256 均为 `a3f6b35f791435af22ccf3e877e5b5d571028d9dc05d36ce506e10c2a31ad66b`；
- 16 个 phase bucket 全部达到样本门槛，均为 sample=available=ready=exact insertion；
- 字符 min/max 全部落在 K-A3c2a 包络内，delta 的 sum/min/max 与 payload+9 精确一致；
- 零 duplicate、limit、unavailable、invalid、omitted、mismatch 和 diagnostics；
- 定向 12 项、相关 60 项、全量 431 项通过；
- 唯一判定 `strategy_intent_prompt_coverage_recovery_verified`，K-A3c2 原 invalid 不变。

K-A3d1 方向：

- 新增独立 `evaluation/strategy_intent_action_ablation.py` 与对应测试，不修改现有 confidence harness 或 runtime；
- 使用注入的 deterministic provider，off/on 共用同一公开局面和候选动作，on 仅增加类型化 strategy intent payload；
- 按四策略×四阶段以固定 SHA-256 优先级选样，平衡 AB/BA 调用顺序；
- 严格分类异常、malformed、no-action、非法类型、越过 legal/prompt 候选，并且不使用 fallback；
- 先以全本地 fake provider 双运行验证载体，不联网、不评价动作质量或胜率。

K-A3d1 验证结果：

- 仅新增 `evaluation/strategy_intent_action_ablation.py` 与对应测试，未修改 runtime 或既有 harness；
- 四策略×四阶段使用固定 SHA-256 优先级，每桶选择 4 对并平衡 AB/BA；
- off/on kwargs 唯一差异为 ready `strategy_intent_prompt`，七类 provider 结果 fail-closed 且无 fallback；
- seed `400..409` 双运行报告完全相同，canonical SHA-256 均为 `8ec3a766852237e07a1185c0d9de98da71a66fe5d6746b76e580fb4e439e2844`；
- 每轮 128 次 provider 调用，64 对全部 both-valid 且 changed，所有异常分类和 diagnostics 为 0；
- 定向 8 项、相关 74 项、全量 439 项通过；
- 唯一判定 `strategy_intent_action_ablation_harness_verified`。

K-A3d2 方向：

- 先把 K-A3d1 的两个新增文件形成独立实现检查点，不混入既有 docs 改动；
- 新增独立 `evaluation/strategy_intent_action_quality.py` 与对应测试，不修改 K-A3d1 公共契约；
- 在固定优先级入选时只做内存 `deepcopy(game)`，clone 前后以 `observe()/legal_actions()` 验证公开等价，不读取 `_state`；
- off/on both-valid 后从独立 clone 执行动作，再由独立 RuleBasedAI 推进到终局；same action 只 rollout 一次并复用；
- 比较顺序固定为队伍 win/draw/loss 分数、队伍两人名次和，再 tie；不以步数、pass 或 pressure 打破平局；
- 先用 deterministic fake provider 双运行验证全部分支和守恒，不联网，不把代理结果称为真实模型质量或胜率。

K-A3d2 验证结果：

- K-A3d1 已独立提交为 `b75dace33d399704e45909ce31c339a7a7e14226`，本步只新增质量模块和测试；
- seed `500..509` 双运行报告完全相同，canonical SHA-256 均为 `a8c907489b8d913e2b2e4838ffaa2b477285cf098328786b07dd6064b8a5e557`；
- 四策略×四阶段每桶 2 对，32 pair 全部 changed 且 quality-evaluable，64 branches 全部完成；
- 固定 RuleBased 续局代理为 on/off/tie=`5/11/16`，只描述假 provider 首/末候选差异，不代表 intent prompt 质量；
- K-A3d1 同参数采样与 digest 兼容，原开发 hash 保持不变；
- 定向 7 项、相关 80 项、全量 446 项通过；
- 唯一判定 `strategy_intent_action_quality_harness_verified`。

K-A3d3a 方向：

- K-A3d2 已独立提交为 `415c86dc5034ca85862f52e94d1406aa58042b98`；由项目所有者单独提交既有 docs，使真实运行前工作区干净；
- K-A3d3a 已连续两次因当前进程未显式提供 `DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`、`DEEPSEEK_API_KEY` 而判定 `precondition_failed`；首次在干净 HEAD `a450fd2367b53ba455e904e1361422f9f965eb58` 完成全部离线前置，第二次按快速门槛停止且未重复回归；
- 当前新进程已确认三项变量 present 且工作区干净；项目所有者选择 `https://api.deepseek.com` / `deepseek-v4-flash` 作为本次 K-A3d3b 锁定配置；
- 重试时先检查三项显式进程环境元数据；仍缺失则立即停止，不重复运行 7 / 80 / 446 项回归；三项齐备后才继续完整前置审计并请求授权；
- 不得把 `.env.example` 当作配置注入方式；它的未提交改动必须由项目所有者在不暴露内容的前提下自行处理，真实密钥不得进入该文件；
- 不联网、不创建 runner、不发送 probe，只复核回归、harness hash、非敏感 endpoint/model 元数据与 key 是否存在；
- 预注册 seed `600..609`、策略 `(0,50,100)`、每 phase 2 对，共 24 pair、最多 48 次请求；
- timeout 60 秒、零重试、持久后台上限 65 分钟；真实请求必须另行取得用户对明确 endpoint/model 的授权；
- 48 次请求必须全部使用 `deepseek-v4-flash`，不得回退或混入历史 `deepseek-v4-pro`；结果只作 flash 内部 off/on 配对解释，不与旧 pro 结果合并；

K-A3d3b 结果：

- 前置已通过并取得一次性授权，但唯一后台进程 PID `33612` 在任何 state/heartbeat/ledger 落盘前异常退出；
- 失败目录只保留 runner，SHA-256 为 `a390ce8bc98aa92592f046c425ec9d0fe7c2313c5727dbd48918f2350033ffbd`；
- ledger 为 0，没有模型响应、pair、rollout 或质量结果可解释；
- 未重跑、未补采、未启动第二进程，唯一判定 `strategy_intent_live_quality_benchmark_invalid`；
- 下一步 K-A3d3c1 只做仓库外离线启动审计与 bootstrap 加固，不联网；原 seed `600..609` 永久停用。

K-A3d3c1 方向：

- 首次尝试只读复核原 runner 后，因四份规划文档未提交而停止并判定 `strategy_intent_live_startup_hardening_invalid`；未创建 candidate、第二进程或网络请求；
- 先由项目所有者提交四份 docs，恢复干净工作区，再重试同一 K-A3d3c1；
- 将父启动状态提前到 spawn 前，将子状态提前到项目 import 前；
- 延迟 project imports，并让参数、目录、首次写入和 import 全部进入最外层保护；
- 通过 `--offline-self-check` 验证正常/失败状态链，request count 必须为 0；
- 不能从缺失证据猜测唯一根因，只能锁定 `startup_failure_before_state_write`；
- 通过后才允许以全新 seed `700..709` 规划 K-A3d3c2，并重新请求用户授权。

K-A3d3c1 验证结果：

- 原失败 runner bytes/hash 与 PID 退出状态保持不变，只能确认 `startup_failure_before_state_write`；
- 新父启动器与子 runner 位于仓库外，SHA-256 分别为 `6a186d7c...e5ca84a`、`776f4504...b01e445`；
- 正常 self-check 两次结构 hash 均为 `ede8bfc3...41e80ec`；
- 缺失参数、无效目录、import 失败和原子写入失败均有预期 exit/status 证据；
- request/network/client/suggest count 均为 0；
- 唯一判定 `strategy_intent_live_startup_hardening_verified`。

K-A3d3c2 方向：

- 先只读复核 K-A3d3c1 证据、环境元数据和新预算，停下请求新的明确授权；
- 使用全新 seed `700..709`，旧 `600..609` 与 K-A3d3b 授权永久停用；
- 授权后恰好运行一次，策略 `(0,50,100)`、每 phase 2 对、24 pair/48 请求；
- endpoint/model 继续锁定 `https://api.deepseek.com` / `deepseek-v4-flash`，60 秒、零重试、65 分钟；
- live runner 必须继承父 spawn 前与子 import 前状态链；任何完整性失败只产生 recovery invalid。

K-A3d3c2 结果：

- 唯一授权 live run 完成 48/48 请求，off/on 各 24，全部 returned、零重试、零请求失败；
- report 与 audit summary 已写入，但 manifest/completion 缺失，子进程 exit code=1；
- 根因已定位到 runner 第 244–245 行错误地从 audit 目录读取实际位于 candidate root 的 runner metadata；
- 父状态完整，子状态为 bootstrapping→imports_ready→startup_ready→running→completed→failed；
- 按预注册完整性优先规则，唯一判定 `strategy_intent_live_quality_recovery_invalid`，不得解释已生成 report；
- 未重跑、补采或启动第二进程，旧授权已用尽。

K-A3d3c3a 方向：

- 不再次联网，独立只读验证原 report、48 条 ledger、状态链和源码路径缺陷；
- 在全新恢复目录运行两次自包含 verifier，不信任原 summary verdict，不补写原 manifest/completion；
- 完整性失败只产生 readonly recovery invalid；完整性通过后才按原 changed/on-off/team-win 顺序给出描述性判定；
- 无论恢复结果如何，K-A3d3c2 原 invalid 永久保留。

K-A3d3c3a 结果：

- 独立 verifier 双运行逐字节一致，完整重算 48 个请求、24 pair、三策略四阶段和全部 branch/W-D-L/quality 守恒；
- 源证据前后文件集合和 SHA-256 不变，第 244–245 行 manifest 路径缺陷得到确认；
- changed pair=`7`，在预注册第一道 `changed>=8` 门槛失败；后续 on/off better=`2/1`、team wins=`8/6` 不得越级解释；
- 新只读恢复判定 `no_observed_strategy_intent_action_quality_gain`；K-A3d3c2 原 invalid 不变；
- strategy-intent prompt 继续默认关闭，本分支封板，不进入扩大质量评估。
- 完整性通过后才解释 RuleBased 续局代理；小样本只决定是否保留到扩大验收，不构成因果或胜率结论。

### Step L：Botzone 本地 AI 接入

状态：L4-A3c1 已封存；后续 live 因 finished-only 假完成判为 invalid。当前 runner 未区分历史 finished 与本进程同 match 的有效完成。下一执行任务 L4-A3d1 只做离线 finished provenance 加固，不 preflight、不 live。L4-A2c5b2a 暂缓。

目标：

- 由本机连接器通过 Botzone 官方本地 AI 长轮询接口参加 GuanDan 测试对局；
- adapter 负责平台协议、牌 ID、阶段和 action/claim 转换；
- RuleBasedAI 仍只读取转换后的 observation/legal actions 并返回合法 `action_id`；
- 用真实平台 smoke 和后续座位平衡小批量对局观察本地 AI 的实际对抗能力。

阶段：

1. Phase 0：已完成；claim、双配子、无贡 `deal→play`、首个玩家和账号入口已封板；runmatch 自动化仍为可选项；
2. Phase 1：已完成；纯数据模型、108 牌 ID codec、无贡 profile 与 action/claim 单测通过；
3. Phase 2：已完成；mock connector/session、事务加固、官方首个 play 和本地座位契约均通过；
4. Phase 3：已完成；adapter 主链与 L3-A1a observation/实体守恒均封板；
5. Phase 4 准备：L4-A1/L4-A1a/L4-A2a 已完成；凭据轮换与 preflight ready 已确认；
6. Phase 4 live：历史 L4-A2b 启动失败永久保留；后续人工前台运行已连接网关，但首个真实请求因协议 envelope 缺口失败；
7. Phase 4 协议恢复：L4-A3a 已完成，离线区分外层 Bot JSON 与内层 GuanDan stage，重放历史并包装 response；
8. Phase 4 新准入：L4-A3b 已封存实现，但 stdout gate 导致 preflight invalid；
9. Phase 4 输出恢复：L4-A3b1 已完成，direct main 与 binary PIPE 跨平台单行输出通过；
10. Phase 4 live：L4-A3c 已执行一次并 invalid；未生成 response/Header，授权已消耗；
11. Phase 4 请求诊断：L4-A3c1 已验证，固定安全错误类别且保持合法路径兼容；
12. Phase 4 诊断恢复：L4-A3c1 已封存；后续 live 只收到 finished，零请求假完成；
13. Phase 4 完成来源：L4-A3d1 离线区分 raw/qualified finished，并按同 match play Header ack 关联；
14. Phase 4 文件系统诊断：L4-A2c5b2a 暂缓，既有 invalid 不追认；
15. Phase 5：可选 DeepSeek，默认关闭且不属于基础验收。

关键门槛：本项目不实现贡还，只支持建桌时明确选择“需要进贡=否”的对局。L1 只证明协议模型；L2 必须证明 mock transport、pending response 事务、会话恢复以及官方首个 play 原文可解析，L3 才能接 RuleBasedAI。若收到 `tribute/return`，必须以 unsupported stage 安全失败，不能以空响应、pass 或随意牌绕过。`runmatch` 要等自动建桌流程单独验收后再启用。

## 6. 质量指标

### 正确性

- 非法动作率为 0；
- 主回归和全部 `unittest` 通过；
- 公开牌统计无负数、无重复扣减；
- 标为 `confirmed` 的推断精确率必须为 100%。

### 推断质量

- 外部剩余不超过 20 张时，真实点数进入对应玩家 Top-3 候选的比例作为主指标；
- 外部剩余不超过 12 张时，记录逐玩家点数准确率；
- 同时记录覆盖率、置信度和错误确认数；
- 不用单次对局主观判断代替数据。

### 策略质量

- 固定种子、双方策略交换座位；
- 记录胜 / 负 / 平、平均完赛名次、关键牌消耗；
- 公式开局、RAG、信念状态分别做消融对照；
- DeepSeek 评测记录调用次数、失败率和平均上下文长度。

## 7. 非目标

当前主引擎仍不实现：

- 多局升级赛与 Botzone 贡还模式；integration 仅实现无贡 profile，未经新任务确认不得把贡还写入主引擎；
- 强化学习、自博弈训练；
- MCTS 和蒙特卡洛搜索；
- 把隐藏牌推断写入规则引擎；
- 把 RAG 或模型输出当成规则真值。

## 8. 实施顺序

每一步遵循：

1. 更新规格和验收口径；
2. 添加失败测试；
3. 做最小实现；
4. 运行相关测试和全部回归；
5. 记录指标，不以提示词变长作为能力提升依据。

## 9. 新支线：无需 connector 的 Botzone DeepSeek 完整体 Bot

### 9.1 支线定位

该支线以 Botzone“上传 Bot”运行方式为目标，不再把本地 AI connector 作为上线前置：

- Botzone 平台直接运行上传的 Python 3.6.5 ZIP；
- ZIP 根目录使用 `__main__.py`；
- 本地 connector 代码与历史结论保留，用于协议研究和本机调试，但暂停为当前主线；
- 默认对局继续固定“需要进贡=否”，不实现 `tribute/return`；
- DeepSeek 只允许从本地生成的合法候选动作中选择，不得直接生成 Botzone 牌 ID 或绕过规则层。

当前基线为 `cf35a205131cfc9b94c28491e0a8b092abdc0d30`：

- `botzone_upload_py36/__main__.py`；
- `dist/guandan_rule_ai_py36.zip`；
- ZIP 为 4,031 bytes，SHA-256 为 `29e7ec827abf0ff6673bfeafab254cb9cc2174edc37bf1c802dcc15a346de351`；
- U0-A1 前全量测试基线为 545 项；当前 U0-A1 后基线为 556 项；
- 用户人工报告已在 Botzone 完整运行两局且未发现协议或出牌错误。

该人工结果只证明当前规则基线可运行。现有上传代码仍是 traditional JSON interaction、无贡、自然牌动作子集，不主动生成逢人配替代动作，也未迁移当前 `agents/` 的阶段、记牌、RAG、策略路由、confidence 或 DeepSeek 决策。

### 9.2 官方能力边界

已确认：

- Botzone 上传 Bot 不需要 connector；
- 多文件 Python 可打包为 ZIP，根目录必须有 `__main__.py`；
- 数据文件应通过用户存储上传，并从 `data` 路径读取；
- Python 运行时版本为 3.6.5，基础时限按平台页面与语言倍率执行；
- 长时运行通过固定 marker 保持进程，下一回合只收到当前 request，不再收到完整历史与 data/globaldata；Bot 必须自己维护状态；
- 长时运行用于减少冷启动，不等于放宽单回合决策时限；
- DeepSeek 官方 base URL 为 `https://api.deepseek.com`，目标模型为 `deepseek-v4-flash`。

尚未确认：

- Botzone 评测沙箱是否允许访问外部 HTTPS；
- 用户存储中的凭据文件在评测进程中的权限与可用性；
- `deepseek-v4-flash` 在 Botzone 单回合时限内的实际成功率和延迟；
- 平台发生进程重启时，长时运行内存状态的恢复频率与失败形态。

### 9.3 目标架构

```text
Botzone JSON input
  -> Python 3.6 protocol/replay
  -> complete no-tribute public state
  -> complete legal action enumeration
  -> opening/phase/card memory/strategy/RAG
  -> compact candidate list
  -> DeepSeek selects candidate action_id
  -> strict candidate/provenance validation
  -> RuleBased fallback on timeout/error/invalid output
  -> canonical {"response":[action,claim]}
```

安全边界：

- API key 只从 Botzone 用户存储读取，不进入源码、ZIP、debug、data/globaldata、异常或测试；
- 用户存储是平台文件能力，不宣称为专用 secrets manager；
- 使用 Python 3.6 标准库 `urllib`，不假设 OpenAI SDK 可用；
- 模型调用短超时、零重试；任何失败必须在时限内返回合法规则动作；
- RAG 语料可放用户存储，但不得把密钥与可公开语料混在同一文件；
- 上传 Bot 不导入本机 Python 3.11 项目模块，而是维护经过测试的 Python 3.6 兼容实现。

### 9.4 阶段计划

#### U0：出网、凭据与时限准入

- U0-A1：已完成。独立探测 ZIP 只做一次最小请求，实际动作始终使用规则基线；fake opener 离线契约、Python 3.6 grammar 和全量 556 项已通过。实现检查点 `085162972363e634fe224c9f1725063b3cd13686`。
- U0-A2：已完成一次人工新无贡对局。结果为 `probe_dns_or_connect_failed`；无 Botzone 超时，规则动作合法，对局完成，首个探测输出约 61 ms。
- U0 结论：`botzone_deepseek_egress_admission_blocked`。用户存储凭据契约通过，但 Botzone 评测环境未建立到 DeepSeek 的连接；不得进入实时 DeepSeek U1/U2/U3。

#### U1：完整无贡合法动作与公开状态迁移

- 把当前 engine 的无贡 play 规则迁移为 Python 3.6 兼容上传模块；
- 补齐逢人配、重复虚拟 claim、炸弹、顺子、连对、钢板、同花顺和王炸；
- Botzone 实体 ID 与本地 action provenance 完整映射；
- 以离线 fixture 对比 Python 3.11 engine 的合法动作集合。

验收：上传版候选必须是规则真值的等价集合或有明确、审计过的安全子集；DeepSeek 仍不参与动作。

#### U2：当前本地策略的 Python 3.6 迁移

- 迁移统一阶段、手牌评分、公式化开局、公开记牌、策略路由和必要剪枝；
- 保持只读公开请求/历史，不读取裁判隐藏状态；
- RuleBased fallback 成为上传 Bot 的稳定默认决策；
- 对当前 Python 3.11 主链建立 fixture/parity 测试。

#### U3：DeepSeek 候选选择

- 使用紧凑候选编号，不发送 Botzone 实体 ID 作为自由生成目标；
- 模型只能返回候选 ID；类型、范围、合法性和 provenance 任一失败都回退规则动作；
- 默认 `deepseek-v4-flash`、短超时、零重试；记录仅限聚合成功/超时/降级分类；
- 先 traditional mode，再评估长时运行，避免同时引入模型与会话状态变量。

#### U4：长时运行、RAG 与状态恢复

- 首回合正常输出后使用官方 keep-running marker；
- 后续只消费当前 request，并在内存维护 hand/history/phase/card belief；
- 进程重启后能从传统完整 envelope 重建；
- 规则库/经验库从用户存储只读加载，限制大小和 prompt 字符预算；
- 不在回合间后台计算，避免消耗下一回合 CPU 时间。

#### U5：Botzone 人工验收与对抗评测

- 先 smoke：完整一局、零非法动作、超时可降级；
- 再 A/B：规则基线与 DeepSeek 完整体分开创建版本，固定桌设置并轮换座位；
- 记录完成局数、超时/降级、非法输出、模型有效选择、胜负和名次；
- 没有足够样本前只声明“接入可用”，不声明胜率提升。

### 9.5 架构分流结果

项目所有者已明确选择 **B：恢复 connector，通过本机调用 DeepSeek**。

因此：

- 上传 Bot 路线冻结在 `botzone_deepseek_egress_admission_blocked`，不重复探测 Botzone 评测机出网；
- `guandan_rule_ai_py36.zip` 继续作为可运行的平台规则基线，不再承担实时 DeepSeek 完整体目标；
- Botzone 完整体恢复使用本机 Python 3.11 connector、现有 `engine/` 与 `agents/`；
- 贡还仍不在范围内，真实桌继续固定“需要进贡=否”；
- 下一阶段不复用任何历史 live 授权。

### 9.6 Connector DeepSeek 恢复阶段

#### L5-A1：离线接线与规则降级

- 将 runner 的硬编码 RuleBased 组合根扩展为默认 `rule`、显式 `deepseek`；
- DeepSeek agent 按 match/player 隔离并复用，finished 后清理；
- 只传公开 observation 与 canonical legal actions；
- 模型异常、超时、错误类型和非法 action ID 均由 adapter 最终降级到 RuleBased 合法动作；
- 使用 fake client/transport，真实网络计数为 0。

验收：`botzone_deepseek_connector_offline_wiring_verified`。

#### L5-A1a：启动与降级契约加固

- 恢复默认 RuleBased handler 的 `agent_failure` / `invalid_agent_action_id` 精确分类；
- 区分 DeepSeek 主 Agent 失败、规则 fallback 失败、fallback 非法 ID 与 provenance 破坏；
- 显式 deepseek 配置和本地 RAG 组合必须先于 Botzone transport 构造；
- `--preflight-only --agent deepseek` 只做本地组合验证，全部网络调用为 0。

验收：`botzone_deepseek_connector_hardening_verified`。

#### L5-A2a：真实环境零网络 preflight

- 使用全新仓库外 state 目录；
- 显式 `--agent deepseek --preflight-only`；
- 只验证真实进程环境中的配置形状、文件操作、RAG、client 与 Agent 本地构造；
- 30 秒内恰好执行一次，不重试；
- Botzone GET、DeepSeek request、DNS/socket/HTTP 与 connector cycle 均为 0。

验收：`botzone_deepseek_connector_live_preflight_ready`。

实际前置结果：实现、工作区、23/569 回归和四项脱敏配置元数据均通过，但当前权限不能在 `%LOCALAPPDATA%` 创建任务要求的仓库外 state 目录；子进程未启动、网络计数为 0，判定 `precondition_failed`。

#### L5-A2a1：系统临时目录恢复

- 不改代码、不重复回归；
- 使用标准系统临时目录下的全新随机仓库外 state 目录；
- 保持同一命令、30 秒上限、恰好一次和零网络门槛；
- 临时目录不可用则继续 precondition failed，不尝试其他路径或提权。

实际结果：系统临时目录资格通过；唯一 preflight 在约 190 ms 后 exit 0，输出固定 `preflight_ready`，stderr/state/残留进程为空，全部网络与模型请求计数为 0。判定 `botzone_deepseek_connector_live_preflight_ready`。

#### L5-A2b：真实单局 smoke

仅在 L5-A2a 通过、工作区干净且用户重新明确授权后执行：

- 零网络配置/preflight；
- 明确确认 Botzone connector 已连接后再人工创建全新无贡桌；
- 使用新的 state/audit、短请求预算和新的明确 live 授权；
- 先证明 deal/play/response/header/ack/finished 闭环，再记录 DeepSeek model/fallback 聚合计数。

不得把 L5-A2a 与真实联网合并，也不得在 smoke 前宣称动作质量或胜率提升。

首次启动在进程创建前被安全审查拒绝：授权已覆盖 endpoint/model/预算，但未明确覆盖向 DeepSeek 发送本家未公开手牌和决策上下文。connector/network count 为 0，临时 state 已清理，判定 `precondition_failed: sensitive_outbound_authorization_missing`。

#### L5-A2b1：敏感出站授权恢复

- 在授权文本中逐项列明本家手牌、公开历史/状态、合法候选动作、评估/记牌、场景标签和 RAG 片段；
- 明确这些数据会发送到 DeepSeek 并离开本机；
- 明确不发送 Botzone URL/key、match/session、实体 ID、其他玩家隐藏牌和 `.env` 内容；
- endpoint/model/100 GET/60 秒零重试/单进程/3600 秒/一局预算保持不变；
- 获得新授权后才允许创建新的 state/audit 并启动唯一进程。

实际结果：完整授权与全部快速门槛通过后，唯一 connector 成功连接 Botzone；但在用户确认新桌开始前收到一个请求，并以 `envelope_shape_invalid` fail-closed。exit 5、request=1、response/header/finished=0、transport failure=0，state 为空且无残留。判定 `botzone_deepseek_connector_no_tribute_smoke_invalid`。请求未进入 Agent 或 DeepSeek 动作选择。

#### L5-A2b2：外层信封安全子分类

- 保持公开父诊断 `envelope_shape_invalid`；
- 用固定低基数 detail 区分顶层类型、必需字段、未知字段、可选字段、requests/responses 容器、空 requests 和基数错误；
- 只在 connector/audit 中聚合 detail，不记录原始 envelope、字段值、match 或逐请求信息；
- 先完成离线测试与 schema 兼容性，再决定是否需要新的 live 授权。

实际结果：实现检查点 `37bdd0d`。八种 detail 已固定；公开父诊断保持 `envelope_shape_invalid`；connector/runner 只聚合 allowlist detail；audit 升至 v3，旧 diagnostics 语义不变。定向 24 项、全量 572 项和 diff check 通过，唯一判定 `botzone_envelope_shape_subdiagnostics_verified`。

#### L5-A2b3：v3 恢复准入

- 只复核检查点、24 项定向、配置元数据和残留进程；
- 使用全新系统临时 state 执行恰好一次零网络 deepseek preflight；
- 项目所有者必须确认所有历史本地 AI 测试桌已结束或关闭；
- 全部门槛通过后只提出 L5-A2b4 的新授权问题，不在同一步启动 live。

实际结果：endpoint/model 匹配，但当前 DeepSeek timeout/retries 不满足锁定的 60/0，启动前即 `precondition_failed: deepseek_budget_mismatch`。connector/network count 为 0，授权未消耗，工作区干净且无残留。

#### L5-A2b3a：预算配置恢复

- 项目所有者把用户环境变量设置为 `DEEPSEEK_TIMEOUT=60`、`DEEPSEEK_MAX_RETRIES=0`；
- 完全退出并重新启动 Codex，使新进程继承变量；
- 新进程只做一次布尔/匹配检查、24 项定向和唯一零网络 preflight；
- preflight 通过后只确认旧桌已清理并准备 L5-A2b4 授权，不直接 live。

实际结果：项目所有者设置用户变量并重启后，当前 Codex 执行宿主仍未继承 60/0；其余门槛和 24 项定向通过。未创建 state/preflight/connector，零网络，授权未消耗。判定 `precondition_failed: deepseek_budget_mismatch_after_restart`。

#### L5-A2b3b：子进程预算锁定

- 父进程 timeout/retries 不再作为门槛；
- 在同一 PowerShell 子环境显式注入 60/0；
- 先用现有 AppConfig 做一次固定输出、零网络预算探测；
- 再在同一子环境执行唯一零网络 preflight；
- 不修改用户/系统环境或 `.env`，不在同一步 live。

实际结果：当前新进程六项门槛与 24 项定向通过；唯一 preflight 约 171 ms、exit 0、固定 stdout、空 stderr/state、临时目录删除且无残留；显式 60/0 的 AppConfig 固定探测返回 `deepseek_budget_ready`。实际为严格数值门槛 → preflight → 补充 AppConfig 探测，未重跑 preflight，全部网络/模型请求为 0。判定 `botzone_deepseek_connector_v3_preflight_ready`。

#### L5-A2b3c：历史测试桌清理确认

- 只等待项目所有者确认所有历史本地 AI 测试桌已结束或关闭；
- 承诺下一次仅在 connector 已连接后创建一个新无贡桌，且没有第二个活动桌；
- 确认后只提出 L5-A2b4 授权问题，不在同一步 live。

实际结果：项目所有者确认全部旧桌已关闭，并明确授权 L5-A2b4。唯一 connector 显示已连接，但在新桌开始确认前收到一个缺少 Bot envelope 必需字段的 object；exit 5、request=1、response/header/finished=0、transport failure=0，detail=`envelope_required_fields_missing`。state 为空，无残留，未进入 Agent/DeepSeek。判定 `botzone_deepseek_connector_no_tribute_smoke_invalid`，授权已消耗。

#### L5-A2b5：必需字段缺失画像

- 保持父诊断和现有 detail 不变；
- 用固定 profile 区分缺 requests、缺 responses、空 object、inner-stage candidate、optional-only 和其他 object；
- 只聚合 allowlist profile，不记录 key/value、长度、hash 或原始请求；
- 先完成离线测试与 audit 兼容，不直接 live。

### 9.7 当前下一步

L5-A2b4 唯一 live 再次在新桌开始前 fail-closed，现已定位到 `envelope_required_fields_missing`。当前执行 L5-A2b5，只做零网络安全形状画像；不得重跑 live。
### L5-A4e9：direct persistent connector pilot

- 全新 seed `29001` 的 direct connector 在获得持续 session ID 前即退出；未进入页面连接或建桌，state 为空、v8 audit 不存在、无残留进程。
- 唯一判定为 `botzone_direct_persistent_connector_pilot_invalid`；seed 与根目录永久封存。
- 后续离线核验确认统一执行工具可正常托管长进程，且 D 盘仓库外 state preflight 在系统扩展权限下可返回 `preflight_ready`。当前最具体边界是 connector 本身需要获得仓库外写入及网络所需的系统权限，不能只在默认权限中直接启动。

### L5-A4f1：受权限监督的 direct connector pilot

- 使用全新 seed `30001`、seat 0、DeepSeek 与固定 run token；不使用 launcher、runmatch、后台 detached 进程或新增诊断载体。
- direct connector 命令本身以系统扩展权限和统一 TTY session 启动；拿到持续 session ID 后才使用已绑定 Browser 标签页等待连接并创建唯一人工无贡桌。
- 项目授权默认有效；仅最终网页建桌提交按平台要求做一次即时动作确认。
- 通过后只证明单局协议/模型观测闭环；失败则永久封存 seed/root，不重试。
### L5-A4f1 实际结果与 L5-A4f2

- Codex 托管的 `30001` pilot 未建立连接；后续确认用户终端曾混用 cmd/PowerShell 变量，不能据此继续归因 connector。
- 项目所有者改用 VS Code PowerShell、显式绝对目录和前台 connector，成功完成 `30002` 人工无贡 DeepSeek 局。v8/v4/token、27 组请求闭环、17 次模型 success、零 fallback 和正常终局均已只读核验，判定 `botzone_owner_operated_deepseek_manual_smoke_verified`。
- 下一步 L5-A4f2 不再由 Codex 托管长进程：项目所有者以前台 PowerShell 串行运行一个 rule/deepseek 同条件 pair，Codex 只负责固定命令、evidence 守恒和 existing benchmark 聚合。
### L5-A4f2 结果与自动化恢复

- game 1 RuleBased 本身完整成功：v8/v4 匹配、22/22/22 请求闭环、21 次规则决策、正常团队胜、零模型/fallback/协议/transport 异常。
- 项目所有者确认网页 seed 并非预注册 `31001`，因此该局不可计入 pair，game 2 不得启动；判定 `botzone_owner_operated_single_pair_capacity_invalid`，原 root/evidence 永久封存。
- 下一步 L5-A4f3 改为 Codex 自动运行单个 rule connector 并自动填写网页；提交前用 DOM readback 精确核对 seed/seat/无贡/级牌/对手槽，先验证自动化链路再恢复 pair。
### L5-A4f3 evidence 封存与 UI 顺序修正

- `32001` connector 在 Browser readback/提交前已完成一局：v8 audit 771 bytes / `6bde11f5...4e45e3`，33/33/33 请求闭环，v4 tombstone 115 bytes / `e2b1b430...f0a5`，二者 token 匹配。因目标桌尚未由 Codex 创建，evidence 只作为未知来源/旧队列完成记录封存，pilot 仍为 invalid。
- 项目所有者明确正确 UI：主页创建游戏桌 → 选择 GuanDan → 确认 → 载入上次配置 → 内存核对目标 Bot ID → 右下角设置 → 开始游戏。
- 下一步 L5-A4f4 先把网页准备到最终提交前并完成 readback，再启动 connector；连接后第二次 readback，通过后才开始游戏。真实 Bot ID 不写入 docs/audit/report。
### L5-A4f4 结果与点击防护

- 页面在最终提交前显示“游戏桌被房主关闭了”；connector 未收到请求，最终被中断。v8 audit 为 695 bytes / `a8785d80...8a24f`，exit 130、4 次 idle timeout、0 request/Agent/model，state 为空。判定 `botzone_codex_corrected_ui_rule_pilot_invalid`。
- 当前证据不能确认是否误点提前终止，只能确认目标桌未进入 local-AI 链路；不得把怀疑升级为根因。
- 下一步 L5-A4f5 使用全新 `34001`，严格限定提交前点击白名单；最终开始游戏后 Browser 完全只读，只轮询 connector 和读取页面状态。
### L5-A4f5 结果与 UI 契约发现

- 白名单内游戏选择确认被点击，但页面未进入建桌表单并仍停留主页；未启动 connector、未创建目录/桌、未联网或调用模型，判定 `botzone_codex_click_fenced_rule_pilot_invalid`，`34001` 永久禁用。
- 失败边界现收窄到游戏选择 modal 的选中状态、确认按钮作用域或确认后的页面状态转换。
- 下一步 L5-A4f6 不使用 live seed/connector，只以 Browser screenshot+DOM 发现 GuanDan 选项、selected proof、modal-scoped confirm 及建桌表单 readiness signal；到达表单后停止，不点击开始游戏。
### L5-A4f6 UI selector contract 结果

- 已验证页面状态为主页 → 游戏选择浮层 → 人工验证码 → GuanDan 建桌表单；浮层不是 accessibility dialog，GuanDan 由选择控件当前值证明 selected，动作按钮实际为唯一“创建”而非“确认”。
- 验证后建桌表单中的 `载入上次配置` 和 `开始游戏！` 各唯一可见；未点击开始、未启动 connector/网络/模型，判定 `botzone_guandan_table_ui_selector_contract_verified`。
- 下一步 L5-A4f7 直接复用当前保留表单，载入配置并两次 readback；表单准备完成后才启动 connector，连接后点击唯一 `开始游戏！`，进入对局后 Browser 完全只读。
### L5-A4f7 自动 RuleBased 基线通过

- 复用已验证表单、两次 readback、唯一开始点击与提交后 Browser 只读全部通过；connector 34/34/34 请求闭环、qualified finished 1、33 次 rule primary、零模型/fallback/transport failure，v8/v4/token 一致。
- 判定 `botzone_codex_verified_ui_rule_pilot_verified`；该结果只封板自动 UI/RuleBased 链路，不形成策略收益。
- 下一步 L5-A4f8 使用全新 `36001` 串行执行 rule→deepseek 同条件单对；每局独立 state/audit/token，任一局失败整对停止，最后只做 existing benchmark 描述性聚合。

### L5-A4f8 结果与 L5-A4g1 benchmark 契约修正

- `36001` 的 RuleBased 与 DeepSeek 两局均各自完成 v8/v4/token 闭环；RuleBased 为 `30/30/30` 且有 1 次 idle timeout，DeepSeek 为 `21/21/21` 且有 2 次 idle timeout，8 次模型结果均 success、fallback 为 0。
- 现有 benchmark 把非零 long-poll timeout 及其固定 diagnostic 一律拒绝；调用方又使用了完整四座位 schedule 聚合仅采样的 seat 0，导致其余 seat 被计为 incomplete。
- 因此单对正式判定保持 `botzone_codex_verified_ui_single_pair_capacity_invalid`，两局不重跑、不补采、不复用 seed/root。
- 下一步 L5-A4g1 只修改离线 benchmark 与测试：保留正式四座位 builder，新增显式 selected-seat builder，并只接受计数守恒、无真实 transport failure 的 idle timeout。
- L5-A4g1 不读取 live evidence；通过后另以 L5-A4g2 对封存证据做独立只读恢复，原 invalid 判定不得改写。

### L5-A4g1 实际结果与 L5-A4g2

- L5-A4g1 已封存为 `569d5431a83e98a2f32928ded7fcda8846e5a8f0`，提交范围精确为 benchmark 模块及其测试。
- 新增显式 selected-seat schedule；正式四座位 builder 与报告 schema 保持不变。
- long-poll idle timeout 仅在 timeout 数值与唯一固定 diagnostic 严格守恒、且没有真实 transport failure 时有效。
- 定向 13 项、全量 624 项和 `git diff --check` 通过；未读取 `36001` evidence，零网络。
- 下一步 L5-A4g2 对封存的 `36001` 两局做独立只读恢复聚合；原 L5-A4f8 invalid 判定永久保留。

### L5-A4g2 恢复结果与 L5-A4h1

- `36001` 单对只读恢复通过：requested/valid=`1/1`，其余 invalid/incomplete/duplicate 均为 0，diagnostics 为空，双运行字节一致且源 inventory 不变。
- RuleBased 与 DeepSeek 均为正常团队负、`score_0`，paired delta 为 0；DeepSeek 8 次 model success、零 fallback。
- 判定 `botzone_single_pair_capacity_recovery_verified`；原 L5-A4f8 invalid 继续保留，恢复结果不构成策略收益。
- 下一步 L5-A4h1 使用全新 `37001/37002`，按正式四座位 schedule 自动执行 8 对/16 局；同一任务先完成 manifest、隔离布局和双模式零网络准入，门槛通过后直接 live。

### L5-A4h1 结果与 L5-A4h2

- L5-A4h1 在离线布局阶段停止：manifest writer 没有满足并证明 replace 前的 `flush + os.fsync` 契约。
- 判定 `botzone_verified_ui_paired_capacity_invalid`；未运行 preflight、connector、Browser、Botzone 或 DeepSeek，仓库未修改。
- `37001/37002` 与原 root 永久封存，不修复或复用。
- L5-A4h2 使用全新 `38001/38002`；仓库外标准库 writer 必须按独占临时文件、write、flush、fsync、close、replace、回读逐字节校验的顺序完成 manifest。
- 原子门槛通过后在同一任务继续双模式 preflight 与 16 局 live，不再拆分新的准备步骤。

### L5-A4h2 结果与 L5-A4h3

- L5-A4h2 的布局、manifest 原子自检、16 个 state 探针及双模式 preflight 全部通过。
- 执行器在第 1 局前把大厅中其他玩家的进行中桌误判为当前账号冲突桌，判定 `botzone_verified_ui_paired_capacity_recovery_invalid`；connector、建桌和网络请求均为 0。
- `38001/38002` 与原 root 封存，不复用。
- L5-A4h3 使用 `39001/39002`，新增大厅归属门槛：其他玩家桌直接忽略；明确的本账号旧桌暂停等待清理；归属不确定时询问项目所有者是否继续创建，不得自行停止。
- 新离线准入通过后继续同一任务的 16 局容量执行。

### L5-A4h3 结果与 L5-A4h4

- L5-A4h3 第 1 局完整通过：28/28/28、qualified finished 1、零 transport failure、RuleBased/provenance 守恒。
- progress updater 在写入前发现预注册 schema 缺少预期字段，故批次判 `botzone_verified_ui_paired_capacity_lobby_recovery_invalid`；progress 未变，第 2 局未启动。
- `39001/39002` 与原 root 封存，不复用。
- L5-A4h4 使用 `40001/40002`，把 progress 固定为九字段不变 schema，并在 live 前于 scratch 中演练初始态、1–16 完成转换、全部失败态和 malformed 反例。
- 进度演练与原离线准入通过后，继续同一任务的 16 局容量执行。

### L5-A4h4 结果与 L5-A4h5

- L5-A4h4 在离线基线命令解析阶段停止；测试和任何项目函数均未实际启动，`40001/40002` root/artifact/network 均为 0。
- 判定 `botzone_verified_ui_paired_capacity_progress_recovery_invalid` 保留，但该结果揭示命令解析不应消耗一次实验批次。
- `40001/40002` 仍封存；L5-A4h5 使用 `41001/41002`。
- L5-A4h5 在正式 root/manifest 前增加可修正的 orchestration qualification：独立命令调用、临时脚本 py_compile、仓库 origin 校验和两次合成 dry-run。
- 只有正式 manifest 原子落盘后才开始不可重试的批次边界；此前纯解析/调用错误必须修正后重新资格验证，不产生 batch invalid。

### L5-A4h5 编排资格通过

- qualification 两次运行结果一致；仓库 module origin、8 对 schedule、manifest/progress 原子演练全部通过。
- 全过程零网络、零 connector/Agent/model，临时脚本与 scratch 已清理。
- `41001/41002` 正式 root 未创建或访问，故批次尚未开始，seeds 继续有效。
- 下一步 L5-A4h5a 不重复资格演练，直接执行独立基线命令、正式 manifest/progress、双模式 preflight和 16 局 live。

### L5-A4h5a 结果与 L5-A4h6

- 正式 writer 在 manifest 写入前因 `ScheduledPair` 字段假设不匹配而失败；外部请求为 0，但正式 root 已提前创建。
- 判定 `precondition_failed: formal_manifest_writer_failed_before_manifest`；`41001/41002` 与 root 封存。
- 根因边界是 qualification 与正式 metadata serializer 不同路径，以及 root 创建早于 payload 完成。
- L5-A4h6 使用 `42001/42002`，只允许一个共享 `build_manifest_payload()`；字段固定为 seed/local_seat/first_strategy/second_strategy。
- 完整 8 对/16 局 canonical payload 在内存验证并确定 hash 后才创建正式 root；同路径资格通过后继续原容量流程。

### L5-A4h6 正式批次起点与 L5-A4h6a

- `42001/42002` 的 manifest payload 已通过真实 `ScheduledPair` 四字段路径验证，且完整 canonical payload/hash 在 root 创建前完成。
- 正式 root 内 manifest、九字段初始 progress、16 个隔离 state 目录和 16 个 completion audit 目标已原子落盘并回读；8 对/16 局、rule/deepseek 8/8、AB/BA 4/4 与唯一 provenance token 全部守恒。
- 临时 initial writer 已清理；截至该边界 preflight、connector、网页桌和网络请求均为 0。manifest 现为不可重写的正式批次证据。
- 下一步 L5-A4h6a 先只读锁定 manifest/progress/layout，在 scratch 中资格验证统一 progress continuation helper，再对 rule/deepseek 各运行一次零网络 preflight。
- 双 preflight 通过后在同一任务直接按 manifest 串行执行 16 局；不再拆分准备任务或重复请求项目授权。

### L5-A4h6a 正式布局锁定与 helper 编译完成

- 正式 manifest/progress 已只读复核存在，16 个 state 目录均为空，16 个 completion audit 均不存在，且没有临时或未知 artifact。
- root 外唯一 continuation helper 已建立并通过编译；正式 root 尚未被 helper 写入，preflight、connector、网页桌和网络请求仍为 0。
- 下一执行只复用该 helper 做两次全新 scratch 资格演练，要求合法状态转换、malformed 拒绝、原子写入和结构 hash 逐字段一致。
- 资格通过后按 rule→deepseek 各运行一次零网络 preflight；成功只写低敏 preflight summary 并保持 progress 为 ready，live 16 局留到下一步。

### L5-A4h6a qualification 失败与 L5-A4h6b

- 两次 scratch 运行可重复，但现有演练未覆盖全部 invalid 转换和反例拒绝路径，判定 `precondition_failed: continuation_helper_qualification_failed`。
- rule/deepseek preflight、summary、正式 progress 写入及全部网络调用均未发生；manifest/progress/16 局布局保持不变，因此 `42001/42002` 正式批次仍有效。
- L5-A4h6b 只加固现有 qualification driver，不创建第二个 helper；必须覆盖 9 个 failure stage × 16 个 next game 的 144 个 invalid 转换和完整 malformed/终态/原子故障矩阵。
- 两次全新 scratch 资格结果逐字段一致后，才恢复 rule/deepseek 各一次零网络 preflight。

### L5-A4h6b 新对话交接加固

- 为避免新模型依赖隐含上下文，已锁定正式 manifest/progress 的 bytes/SHA-256、16 个空 state/0 audit inventory，以及 root 外 helper 的实际路径、基线 hash和九项 failure-stage allowlist。
- 当前 helper 仅覆盖 17 个合法转换，缺少 144 个 invalid 转换和反例矩阵；新任务允许在正式 root 外原地修复 helper并新增唯一 qualification driver，资格期可迭代修正，不消耗正式批次。
- 两次完整 qualification 通过后才执行 rule/deepseek 各一次零网络 preflight；成功保持 progress ready，只新增低敏 summary。

### L5-A4h6b 已通过，进入 L5-A4h7 live

- helper 已加固至 9156 bytes / `de67b2d0...92cbe`，driver 为 13390 bytes / `94c55ba9...fd5a5b`；两次 qualification 的 269/269 case、161 合法写入、108 拒绝路径全部通过。
- rule/deepseek preflight 各一次均 exit 0、唯一 ready、stderr 空，16 state 与 0 completion audit 不变，全部网络/connector/Agent/model 计数为 0。
- `preflight-summary.json` 已原子生成：2273 bytes / `32a9cf1a...cad9`；manifest/progress hash 不变，progress 仍为 initial ready。
- 下一步 L5-A4h7 直接按 manifest 串行执行 16 局；每局固定双 readback、持续 PTY connector、v8/v4/token 验收和 helper 原子 progress 推进，失败整批停止。

### L5-A4h7 结果与 L5-A4h8

- `42001/42002` 在 game 1 的 `ui_readback` 阶段永久 invalid：语义浏览器控制失联，Windows 视觉 fallback 无法可靠确认 URL；网页未提交，connector 0/0/0、exit 130，completed prefix=0。
- game 1 audit 为 695 bytes / `2bccc78a...01d76`，progress 已原子 invalid 为 285 bytes / `d6396eb7...5eb68`；manifest/preflight summary 不变，其余 15 局未触碰。
- 下一步 L5-A4h8 不复用旧 root/seeds。先在正式 root 创建前用单一 Chrome semantic controller 完成真实 URL/DOM 稳定资格，禁止回退 OCR/Windows 视觉。
- UI 资格可在零副作用状态重连修复；通过后同一任务创建全新 `43001/43002` 批次、双 preflight 并执行 16 局。

### L5-A4h8 Edge 流程澄清与 L5-A4h8a

- 项目所有者实际使用 Edge，并会在任务前完成登录、旧桌清理和首页准备；不再要求 Chrome URL/DOM 资格。
- L5-A4h8a 使用 Windows `computer-use` 对当前前台 Edge 做固定视觉循环：创建 GuanDan → 载入配置 → 设置 seed/seat → 启动 connector → 开始 → 等待结束 → 点击左上角 `Botzone 2026` 回首页。
- Edge 未前台、验证码或画面暂不可读只暂停请项目所有者处理，不消耗 seed、不判 batch invalid；普通点击默认授权。
- 旧 `42001/42002` 仍封存；新流程使用不存在的 `43001/43002` root，完成 artifact/preflight 后直接执行 16 局。

### L5-A4h8b Edge 扩展控制路径纠正

- 已安装的 `chrome:control-chrome` 组件契约明确支持 Microsoft Edge；正确绑定方式是 `agent.browsers.get("edge")`，插件目录名含 Chrome 不代表只能控制 Chrome。
- L5-A4h8a 把 Edge 错误切换到通用 Windows `computer-use`。下一执行改为 Edge 浏览器扩展的 URL/DOM/Playwright 控制，禁止回退截图坐标、OCR、内置 Browser、Chrome family 或通用 Windows 控制。
- Edge family 暂不可用时只暂停并检查 **Settings → Computer use** 与 Edge 扩展连接；在 root/connector/桌均未创建时不消耗 seed、不写 batch invalid。

### L5-A4h8b 结果与 L5-A4h9 生命周期隔离

- `43001/43002` 在 game 1 / `lobby_gate` 进入 `?msg=destroyed`；completed=0，配置写入、connector、Agent 和 model 调用均为 0，16 个 state/audit 目录无条目。manifest、preflight summary 和 invalid progress 已封存，root/seeds 不复用。
- Edge family 当前可绑定，双模式零网络 preflight 已通过；这些事实只能排除本次运行已进入 connector/model 链路，不能解释桌为何被房主关闭。
- 同类预提交症状曾在 `33001` 出现，因此不再直接安排第三个 16 局正式批次。下一步 L5-A4h9 是单桌 UI 生命周期诊断：先观察表单无操作稳定性，再逐个执行载入配置、seed 和 seat 写入；任何 destroyed 立即停止且不重试。
- L5-A4h9 不创建正式 root、不启动 connector、不点击开始、不修改代码。它的完成条件是把 destroyed 收窄到无操作等待或某个紧邻动作，或者证明未开始表单在全部诊断检查下稳定。之后才由规划 Codex决定是否进入单局 pilot。

### L5-A4h9 结果与 L5-A4h9a 新标签资格

- L5-A4h9 没有创建新诊断桌；读取到的 destroyed 是任务起点遗留状态，不能作为本次生命周期结果。locator 连续超时后停止，当前有效判定为 `precondition_failed: edge_locator_readback_unavailable_before_new_table`。
- 独立排障确认 Edge、扩展和 native-host 配置健康，且开放标签枚举可用；旧 destroyed 标签当前被另一个浏览器控制会话占用。此证据把下一步从“重装优先”改为“隔离旧会话和标签”。
- L5-A4h9a 由新执行任务创建唯一全新受控 Edge 标签，先在 Botzone 首页验证最小 locator。一次短等待后的重试仍失败则以 locator unavailable 结束且不建桌；通过后才继续原单桌逐动作诊断。
- 只有新标签内、新桌创建之后首次出现的 destroyed 才能计入诊断。旧 destroyed 标签永久保持只读，不再作为起点或完成证据。

### L5-A4h9a 废弃与 L5-A4h10 固定 workspace 清理

- 项目所有者接管 Edge 建桌和表单配置，Codex 不再继续 locator 恢复或自动创建网页桌。因此 L5-A4h9a 在执行前废弃，不视为失败或完成。
- 当前 `D:\VsCodeProject` 有 21 个本任务产生的 `Botzone*` 顶层目录。项目所有者授权永久删除全部内容，并接受原始 evidence 不再可恢复；历史低敏结果与 hash 已写入项目文档。
- L5-A4h10 只执行目录维护：删除前验证精确 allowlist、直属父目录和非 reparse 属性；永久删除 21 项后创建唯一空目录 `D:\VsCodeProject\BotzoneWorkspace`。
- 后续所有 Botzone state/audit/artifact 只使用固定 workspace，不新增 seed/pilot/pair/capacity 顶层目录。复用前的结果记录、清空和下一次 live 分属独立任务，避免边运行边删除 evidence。
- L5-A4h10 完成并由规划复核后，项目所有者手工建桌；届时再生成只负责 connector/evidence 的单局 pilot Prompt，不直接恢复 16 局容量。

### L5-A4h10 结果与 L5-A4h10a 可恢复清理

- L5-A4h10 的精确 inventory、路径、非链接和 Git 门槛均通过，但执行策略在实际运行前拦截永久递归删除；21 个目录和固定目标均未改变。
- 该结果是执行环境限制，不是 inventory drift，也不授权换用 `System.IO.Directory.Delete`、`cmd /c` 或其他永久删除绕过。
- L5-A4h10a 改用 Windows 回收站式可恢复清理。逐项成功后才创建空的固定 workspace；中途失败立即停止且不创建 workspace，已移动项保留在回收站可恢复。
- 若执行环境没有支持的回收站能力，后续不再让 Codex 尝试删除，由项目所有者在资源管理器中清理；清理完成后规划 Codex 只读复核。

### L5-A4h10a 结果与 L5-A4h11 人工建桌 RuleBased pilot

- 21 个旧 Botzone 顶层目录已全部移入回收站，固定空根 `D:\VsCodeProject\BotzoneWorkspace` 已建立；独立复核确认它是唯一 `Botzone*` 顶层目录、非链接且空。
- 下一步不恢复 Edge 自动化，也不直接执行 DeepSeek/配对/容量。L5-A4h11 使用全新 seed `44001`、seat 0、无需进贡、级牌 2，只运行一局 RuleBased。
- 执行 Codex 先在固定 workspace 建立 manifest/state/audit、完成一次 rule 零网络 preflight，再告诉项目所有者手工配置桌；收到“桌已配置”后启动持续 connector。
- connector 确认仍在运行后，Codex必须再次明确给出 seed/profile，并提示项目所有者核对本地 AI 已连接后点击一次开始。Codex 全程不操作 Edge。
- 单局通过 v8/v4/token、request/response/Header、finished 和 RuleBased 来源验收后，保留 workspace 现场交回规划；失败同样保留且不重试 seed。

### L5-A4h11 结果与 L5-A4h11a 准备资格恢复

- L5-A4h11 在首个 workspace artifact 前因未具体说明的 PowerShell 参数不兼容停止；workspace/table/preflight/connector/network 均为 0。
- 该边界早于 seed 或 live 消耗，故不接受 pilot invalid 判定；改记 `precondition_failed: workspace_preparation_command_incompatible`，继续使用 `44001`。
- L5-A4h11a 把命令兼容性放入正式 workspace 外的 scratch qualification：先报告 PowerShell/Python 版本，以与正式相同的 API 演练目录创建、32-hex token、原子 JSON 和清理。
- qualification 可在不触碰 workspace 的前提下修正并重跑；仍失败时必须给出精确命令、参数和低敏错误，不得再用笼统描述。通过后直接继续原 artifact/preflight/人工建桌/connector 流程。

### L5-A4h11a 结果与 L5-A4h11b preflight 恢复

- 准备 qualification 与正式 manifest 成功，manifest 固定为 348 bytes / `fd40f1a...a26f6`；formal preflight 执行一次后仅报告“严格验证失败”，缺少可诊断的捕获值。
- workspace 尚无 state/audit 文件或 summary，人工桌/connector/live 为 0；seed `44001` 未消耗，既有 manifest 成为不可重写边界。
- 仓库测试允许 stdout bytes 为 `preflight_ready` 加 LF 或 CRLF，并要求 stderr 空、归一化唯一行；对应 5 项定向通过。
- L5-A4h11b 先在 workspace 外用同一二进制契约诊断实际 CLI；诊断通过后只允许一次 formal recovery。任何失败必须报告 return code、stdout/stderr 长度、允许值匹配和具体断言，不能再次只给总括分类。
- formal recovery 与 summary 通过后才发出包含 `44001` 的人工配置提示；该提示是 seed/pilot 不可重试边界。

### 牌谱完成后的 partial workspace 清理恢复

- connector-observed 牌谱及 live-ready 加固已完成独立复审；主线不再恢复旧 L5-A4h11b formal recovery，而是先退役旧 manifest、准备一次新的简化人工 smoke。
- 首次 manifest 清理任务的 inventory/hash/链接/进程/Git 基线均匹配，但删除命令在文件操作前被执行环境策略拦截，实际删除为 0。该结果不是授权缺失，也不构成 live 或代码失败。
- 项目所有者已给予固定 `D:\VsCodeProject\BotzoneWorkspace` 的长期清理授权；以后在上一轮 evidence 已审计并写入文档后，不再逐次请求同一授权。授权不扩大到 workspace 之外。
- 精确非递归 `Remove-Item -LiteralPath ... -Force` 也已在 PowerShell `CreateProcess` 前被策略拦截，实际删除仍为 0；该结果进一步确认问题属于永久删除命令策略，而非路径、hash 或授权。
- 下一次改用此前清理 21 个目录时已成功的 Windows 回收站式可恢复操作，只移动已核对的单个 manifest，不清空回收站。完成后只保留空 `audit/` 与 `state/`，再由规划 Codex只读复核；不得在同一任务启动 live。

### fixed workspace 清理完成与普通 history smoke

- `pilot-manifest.json` 已通过 Windows `SendToRecycleBin` 精确移入回收站，没有永久删除；独立复核确认 fixed workspace 现在只含空 `audit/`、空 `state/`，且没有残留 connector。
- 清理阶段结束。下一任务使用新 seed `45001`、玩家1/seat 0、无需进贡、级牌2和 RuleBased，只运行一局人工建桌 connector smoke，并显式写 `history.txt`。
- 该任务是普通诊断运行：不生成 formal manifest/progress，不把 preflight/参数/目录错误升级成不可恢复失败；准备错误在开始游戏前原地修正。
- 项目所有者手工配置桌并停在开始前；唯一 connector 持续运行后，执行 Codex再次复述配置并提示项目所有者只点击一次开始。结束后保留 history/audit/state/streams 交回规划复审。

### seed 45001 history smoke 结果与展示语义修复

- 普通人工 RuleBased smoke 已完成：15/15/15 请求闭环、qualified finished 1、14 次 rule primary、零 model/fallback、exit 0、`history=ok`；工作区 evidence 原样保留。
- 牌谱记录53个已观察公开步骤和6个牌权段。本家在最后观测段出完27张牌后不再收到 play 请求，随后 connector 只收到 finished row，因此真实终局尾部与名次不可见；这解释了 `terminal_tail_may_be_unobserved`。
- 当前 `_render()` 因 `row is not None` 无条件输出最后“第N轮结束后的手牌”，把“收到终局通知”误写成“最后观测段已证明结束”。下一步只做显示语义和合成测试的最小修复，不改 session merge、动作、audit 或完整性推导规则。
- 修复后不重打该局；直接用现有 history 分析 RuleBased 的本家决策。终局尾部未知必须作为分析限制，不补造对手动作或排名。

### 后续人工交互模型

- 页面只读监督是减负的 best-effort 能力，不是新准入门槛；失败时任务保持等待，项目所有者一句“准备好了/配置完成”即可继续。
- 页面可读时必须核对 seed、seat、无贡和级牌；若明确看到错误值，拒绝把“已开始”当作目标配置。seed 不在 connector 协议中，无法靠赛后 audit/history补验。
- connector 持续运行并发出点击提示后，执行 Codex直接等待首个请求/history 变化并进入对局监测，不再要求项目所有者额外发送“已开始”。没有开始证据时继续等待，不提前结束任务。

### history 语义修复通过，转入首个策略诊断

- 规划独立复跑定向54项、全量643项和 diff check 均通过；终局尾部缺失不再被文本写成已证明牌权段结束。
- 新标题仅遗留右分隔符前缺少一个空格的机械格式问题；下一任务先同步修正源码与合成断言，不单独拆出新阶段。
- 随后只读解析现有 `45001` history 的14次本家 RuleBased 决策，结合 `agents/rule_based_ai.py` 当前排序键和当时可用公开信息，区分“明显由现策略决定”“仅凭不完整 history 无法判断”和“可形成合成回归场景”三类。
- 目标是选出一个影响最大、可稳定复现、属于 AI 策略而非 engine/connector 的缺陷候选；本轮只诊断和提出验收，不直接改算法，避免从单局结果过拟合。

### history 标题修正与首个 RuleBased 策略诊断完成

- history 最后观测段标题已统一为 `==== 最后一次观测后的手牌（该牌权段可能尚未结束） ====`，对应测试同步；规划 Codex 独立复跑16项 history、54项 connector 相关和全量643项均通过，`git diff --check` 通过。
- 真实 workspace 的 history/audit/state/streams 大小、hash 和时间保持不变；诊断未联网、未启动 live 或模型。
- 14次本家动作低敏分类为：自由出牌4、跟随队友0、跟随对手10；pass 4、普通牌型8、炸弹类2。
- 代码机制已确认：当前 RuleBased 完全忽略 observation，并在存在任一非 pass 时先排除 pass。合成的 `pass+bomb` 与 `pass+straight_flush` 跟随场景都会稳定选择炸弹类动作。
- 真实牌谱中的两手炸弹类跟牌只能证明“发生过”，不能重建当时全部合法替代、尾部压力或反事实收益，因此当前结论是可复现策略缺陷候选，不是实战错误定论。
- 下一步使用固定机会定义实现 evaluation-only 条件化保牌 candidate，并以同状态双分支 RuleBased rollout 比较团队结果和名次和。生产 RuleBased 在评测给出 retain 结论前保持不变。

### 条件化保牌首次 benchmark 无效，转入 schema 原地修复

- evaluation-only candidate 与成对 rollout 已新增，行为合成测试、主回归和全量649项通过；生产 RuleBased、engine 与 Botzone/runtime 未接线。
- 首次固定容量报告 `opportunity=0`，但原因不是条件罕见，而是 `_action_signature()` 将 legal/table 的完整 action schema 错用于 history row。合成 fixture 多带字段，掩盖了真实 public payload 不兼容。
- 规划 Codex 用真实 engine 公共 API 复现 seed `46000` step 8 的 `pass+bomb`，并以正确 history 最小语义只读扫描原200局得到686次机会。因此首次 `evidence_insufficient` 改判 `benchmark_invalid`，不形成策略质量结论。
- 下一步只拆分 schema validator、补真实 public API 集成回归，再用完全相同的固定 seed/容量双运行。这个修复属于评测载体纠错，不放宽候选、不追加 seed、不触碰 runtime。

### schema 修复通过，进入 opt-in 整局 runtime trial

- 修复后的真实 public API 回归、19项定向、39项主回归、652项全量与 diff check 均由规划 Codex 独立通过。
- 原 `46000..46199` benchmark 两次完全一致：200/200局、686次机会、617个 changed pairs、1234/1234分支完成、零 diagnostics；candidate/baseline/tie 为191/172/254，score 为635/619，名次和为3053/3079。
- canonical SHA-256 为 `b42fad72103574c8f4e6fc1a70af5c16eccec74cb0dc376bba09aba2e5446b81`，paired aggregate SHA-256 为 `b0b07279d0276cec2bd9e23e1e5324502c6d3557ee225b8451bb59a19a317929`；唯一判定 `retain_conditional_pressure_pass_for_runtime_trial`。
- one-step rollout 每次只改变一个决策，后续回到 baseline，尚未评估同一候选在整局中多次使用的累计效果。因此下一步先提取 opt-in Agent，并用新 `46200..46399` 做候选队伍在 team 13/team 24 交换的整局双运行；默认 RuleBased 和 Botzone/runtime 入口保持不变。

### opt-in 整局 runtime trial 通过，转入 Botzone 离线装配

- `agents/conditional_pressure_pass_ai.py` 已成为唯一候选实现，one-step evaluation 直接复用；默认 RuleBased、CLI、DeepSeek、Botzone connector 与 agent factory 尚未接入。
- 规划 Codex 独立复跑24项候选/trial、39项主回归和657项全量测试通过；旧 one-step 的两个完整 hash 不变。
- 新 `46200..46399` 双运行完全一致：200 seed pairs、400/400局、197 active pairs、1433次实际 pass；candidate/baseline W/D/L 为138/146/116与116/146/138，score 422/378，名次和1966/2034，pair better 73/53/74，零 diagnostics。
- canonical SHA-256 为 `9ea636f44104ecb436569679431c4aea7d95d045fcafc047c18f3bb00d958129`，trial SHA-256 为 `3d4ce5ff86320cd4f5d0ec28c1ac40c589b4df86670dec80c8f95594ceb71d10`；唯一实证判定 `retain_conditional_pressure_pass_for_botzone_opt_in_smoke`。
- 评测器仍有一个窄契约缺口：伪造的 pair/game 交叉完成状态与非法 digest 可被 `_valid_report()` 接纳。真实报告自身满足更严格守恒，因此不改判；下一步与 Botzone opt-in 离线 wiring 一并加固，完成后才安排 workspace 清理和 live。

### Botzone offline wiring 完成，validator 还需一次窄收口

- 显式 mode `conditional_pressure_pass` 已接入 factory、组合预检、CLI、launcher、runner、adapter、observability与现有 audit字段；条件化/正常 RuleBased source 分别为 `conditional_pressure_pass` 与 `conditional_rule_based`，默认 rule/deepseek保持原语义。
- 规划 Codex 独立复跑25项候选、47项Botzone相关、39项主回归和665项全量测试通过；两套固定报告再次得到原四个 hash和原 retain结论。
- pair/game交叉范围、strict count和digest已加固，但 `_valid_report()` 实际仍缺 candidate win=baseline loss、candidate loss=baseline win、双方 draw相等。合成 candidate 20/20/0、baseline 1/18/21 在各自边际/score合法时仍错误 retain。
- 同层还应一次补齐有效级牌集合、固定 diagnostic key、非空 requested pairs、active-pair/pass总数关系以及单方名次和每局3..7范围。它们都不改变真实200-pair报告。
- 当前 offline wiring 判为“路径完成、validator部分完成”，不是整体 invalid。下一任务只改 runtime-trial evaluation及其测试；通过后直接进入 workspace清理。

### validator 收口通过，进入旧 evidence 清理

- W/D/L逐项互补、13个有效级牌、六类固定diagnostic、非空容量、active/pass双向关系及每方名次和范围均已进入 `_valid_report()`；旧pair/game、strict-int、score、总名次和和digest约束保留。
- 规划Codex独立复跑validator单文件8项、条件化相关28项和全量668项通过；`git diff --check`通过。
- one-step与runtime trial各单次复核得到原四个完整SHA-256，两个retain判定不变。离线开发阶段无已知剩余阻塞。
- 固定workspace当前精确包含已审计seed `45001` 的5个文件：completion audit、history、一个state、stdout和空stderr；无connector。下一任务只把这5项移入回收站，保留空audit/state/streams目录，不运行live或分配新seed。

### seed 45001 evidence 已回收，进入条件化策略真实 opt-in smoke

- seed `45001` 的 completion audit、history、唯一 state、stdout 和 stderr 已逐项移入 Windows 回收站；未永久删除、未清空回收站。规划 Codex 独立确认固定 workspace 精确只剩空 `audit/`、`state/`、`streams/`，且无项目 connector。
- 下一步只运行一局普通人工 Botzone smoke：seed `47001`、玩家1/seat 0、无需进贡、级牌2，Agent 精确为 `conditional_pressure_pass`，显式写入 history/audit/state/streams；不建 manifest/progress，不启用 DeepSeek，不恢复 capacity。
- 页面由项目所有者手工配置；只读监督可用时核对四项配置，不可用时接受“准备好了/配置完成”。connector 就绪后提示只点击一次开始，并立即用首个请求/state/history 自动确认开始，任务保持等待直至终局或明确真实失败。
- 本局最多一桌，不以“条件化 pass 未触发”为失败或重开理由。全部 connector 门槛通过时，根据条件化 source 是否大于0分别判 `botzone_conditional_pressure_pass_opt_in_smoke_verified_with_activation` 或 `botzone_conditional_pressure_pass_opt_in_smoke_verified_without_activation`。
- 本局只验证真实 opt-in 装配、source守恒、pending/ack去重与history边界；无论输赢或是否激活，都不能单独证明长期真实胜率。结束后保留全部 evidence 供规划复审，清理另立任务。

### seed 47001 prestart 连接未建立，修正 live 顺序

- 项目所有者观察到本地AI页面始终为“未连接”，目标游戏没有开始；执行侧audit同时为2次timeout、0 request/response/Header/finished、0 Agent/model，state/history均不存在。这不是条件化策略样本。
- 两次socket timeout不等于页面连接成功。当前transport不区分连接阶段timeout与服务器长轮询等待timeout，因此页面“已连接”或项目所有者刷新后的明确确认才是人工live的连接准入证据。
- 本次stdout虽显示 `history=ok`，但recorder在尚未处理任何match时也会返回ok；0 request且无history文件时，该状态只能解释为“没有发生history写错误”，不能作为开始证据。
- 旧流程在连接准入前发出seed并准备桌，导致 `47001` 已使用且桌在等待中关闭。此后普通人工live改为：旧桌全关与workspace空 → preflight → 启动唯一connector → 页面确认已连接 → 才分配/提示seed → 项目所有者创建和配置唯一桌 → 核对后点击一次开始。
- 页面仍未连接时保持等待并诊断，不创建桌、不消耗seed；若最终停止，保留evidence。页面连接一旦通过，可在同一执行任务继续建桌，不需要再拆出独立连接测试，从而避免额外清理循环。
- 当前下一步只回收 `47001` 的completion audit与两份stream文件，保留三个空目录；不得在同一清理任务启动connector或分配下一seed。

### seed 47001 evidence 已回收，重新进入先连接的 opt-in live

- 三份prestart evidence已逐项移入Windows回收站；规划Codex独立确认workspace精确只剩空 `audit/state/streams`、无connector，Git基线不变。
- 下一任务不再单独拆“连接诊断”和“live”：在一个持续执行任务中先完成preflight与连接配置人工确认，启动最终connector并等待页面明确“已连接”；连接通过后同一进程继续接收随后创建的唯一目标桌。
- 页面连接通过前不提示预留seed、不创建桌。若需同步配置并重启connector，只能在0 request/0 state/无history/无桌条件下回收本次新建stream/audit并原地修正；seed保持未消耗。
- 页面连接一旦通过，执行Codex才提示固定配置并由项目所有者建桌。此后seed视为已使用；目标桌开始后不重试、不建第二桌，结束后保留evidence供规划复审。

### seed 47002 完成结果与算法主线恢复

- 修正后的先连接顺序生效：页面已连接证据早于seed提示和建桌；唯一connector/唯一桌完成17/17/17、qualified finished、normal result与v4/v8归属。
- 2次 `http_error` 违反原严格smoke的零transport failure门槛，所以不追认 `botzone_conditional_pressure_pass_opt_in_smoke_verified_*`。但它们没有阻止最终完成，不能把整局降格为无runtime证据。
- 16次本家决策全部为正常 `conditional_rule_based`，候选pass未激活。该局证明的是显式mode的正常真实路径，不是候选激活或质量。
- 当前不安排重复live“追激活”，也不让非阻塞的HTTP错误重新占据算法主线。若未来HTTP错误重复导致未完成或破坏ack守恒，再单独升级传输诊断。
- 13级牌、每级牌100对的后续容量计划已取消：当前算法/Botzone profile固定级牌2，跨级牌泛化不是项目目标。
- 默认RuleBased条件化保牌已完成：共享判定只读取公开payload并返回原始pass ID；冻结旧静态selector继续供DeepSeek fallback和历史evaluation使用；显式conditional模式保持兼容。
- 规划Codex独立复跑全量668项通过，`git diff --check`通过；实现已提交为 `150006a`。未运行新容量、Botzone、connector、网络或模型。
- 同队炸弹互耗规则已完成并提交为 `5daf326`：默认RuleBased复用同一严格schema/history/table校验，显式conditional模式仍只保留原有对手领牌语义，DeepSeek与历史evaluation的冻结基线未改。
- 规划Codex独立复跑全量671项通过。固定级牌2、无贡属于项目既定范围，不记为剩余风险。
- 危险对手剩余不超过2张时的模型pass绕过已修复并提交为 `fb3d791`：守卫只作用于模型成功pass，动作来自原始legal actions，model/source/fallback守恒通过。
- 规划Codex在显式禁用dotenv环境中独立复跑全量674项通过；当前范围内无已知剩余风险。
- 自由出牌小手牌短序列守卫已修复并提交为 `dc9638c`：仅在1–4张公开手牌、carrier多重集可精确覆盖且模型首手严格增加最少分组数时覆盖，新增source仍按模型成功计数。
- 规划Codex独立复跑相关31项、主规则39项和全量684项通过；当前范围内无已知剩余风险。
- 下一任务处理DeepSeek成功动作压住已控桌队友的高价值资源绕过，先覆盖队友小王后模型用大王压制；不运行Botzone、不做新容量、不触碰seed `47002` evidence。

### seed 47002 策略审计结束，转入最小决策证据补强

- 五份workspace evidence的bytes、SHA-256和时间在只读审计前后保持不变；Git HEAD为 `2c773fe`，工作树为空。
- 16次本家决策中14次可按公开语义重建；第1、6次缺少完整声明花色、实体副本或wildcard claim细节，无法唯一匹配当时的canonical action。
- 9个pass点均重建为仅pass合法。两个可精确比较残余分组的自由出牌点，冻结基线分别为5组与2组，均等于所有合法首手的最优值。
- 当前没有“当前机制稳定选错且某个原始合法ID公开可证明严格更优”的新fixture，因此不新增策略规则，也不打新桌追样本。
- connector在handler决策点已经同时拥有公开observation、原始canonical legal actions、最终selected ID与source；现有ack持久化只保留carrier/claim。下一任务为这组数据增加默认关闭、仓库外、ack后确认的结构化证据文件，并用重发/重启/finished合成测试证明不重复、不提前记录。

### 决策证据首次实现复核未通过

- 执行方报告的78项定向与697项全量由规划Codex独立复跑通过，`git diff --check`也通过；这证明现有覆盖成立，但不覆盖以下反例。
- fresh direct CLI面对已存在的trace文件仍调用 `build_foreground_runner`，只因后续合成异常才返回configuration error；不满足“预存在输出在runner前拒绝”。
- recorder写完match A后重建实例，再传入决策前缀完全相同的match B，状态仍为 `ok`。当前文件不含持久绑定身份，内容前缀不能证明同一match恢复。
- handler只对action字典做浅复制。合成Agent修改一个非选中action的嵌套 `wildcard_info` 后，trace与调用前 `project_decision()` canonical actions不同，且 `decision_trace_failed=False`。
- 当前代码保持未提交。下一任务不得推倒ack主体，只做输出前置门槛、持久低敏trace绑定及pre-call深拷贝隔离，并补最小回归。

### 决策证据纠错复核仍有两项验收缺口

- 首轮三个反例均已有对应实现与测试：fresh direct CLI会在runner/transport前拒绝已有trace；trace顶层和session持久化随机32位binding；handler在Agent调用前递归隔离observation与canonical actions。
- 规划Codex独立复跑Botzone定向85项、主规则39项、全量704项，均通过；`git diff --check`无whitespace error。这说明ACK、重启、finished、三种mode source与现有回归没有已知漂移。
- 新最小脚本确认 `decision_trace_payload()` 接受observation内 `legal_actions=[{"action_id":999}]`、顶层legal actions为原始pass动作的互相矛盾payload，并返回两份不相等的证据。持久化校验必须把二者逐字段相等提升为强不变量，而不能只由handler构造路径偶然保证。
- diff确认direct CLI把原 `_history_path()` 合并成要求absolute的 `_diagnostic_path()`；这使从仓库外cwd解析到仓库外文件的相对history路径由可用变为configuration error，违反本任务“不改变history兼容语义”的约束。decision trace自身仍应保持绝对外部路径要求。
- 当前代码继续保持未提交。下一任务只修复上述两项并补最小反例；通过后才由规划Codex建立实现检查点，再安排seed `47002` evidence回收与下一次单局采样。

### 决策证据实现最终通过

- shared payload/parser现强制observation内legal actions存在、为list且与顶层canonical actions逐字段逐顺序相等；构造和持久session篡改均fail closed。
- direct CLI恢复原history相对路径解析语义；decision trace继续要求绝对仓库外路径，并保留fresh已有输出、state/audit/history冲突与launcher门槛。
- 规划Codex独立最小脚本结果为：矛盾副本拒绝、相等副本接受、仓库外相对history进入runner、相对trace在runner前拒绝。
- 独立复跑Botzone定向88项、主规则39项、全量707项和staged diff检查均通过；11个实现/测试文件已提交为 `045fb75 feat: record acknowledged Botzone decisions`。
- 当前范围内无已知剩余风险。下一步严格分离为seed `47002`旧evidence回收任务；完成后再规划一局新decision-trace采样，不恢复百局/16局容量。

### seed 47002 evidence 已回收，进入单局 decision-trace 采样

- 清理执行前Git clean、唯一固定workspace、目录非链接、精确inventory、五项bytes/SHA-256和无connector门槛全部通过。
- seed `47002` 的audit、history、唯一state、stdout和stderr已逐项移入Windows回收站；未永久删除、未清空回收站。
- 规划Codex独立复核最终workspace精确只含空的普通目录 `audit/`、`state/`、`streams/`，`D:\VsCodeProject`下没有第二个 `Botzone*` 顶层目录，项目connector为0，Git仍clean。
- 随后的单局 `deepseek` decision-trace采样按该边界执行；seed `47003`只在页面确认已连接后提示，未执行容量评测、修改代码或清理现场。

### seed 47003 decision trace 形成首个可复现策略输入缺口

- connector以exit 0 / `finished_target`结束，11/11/11 request/response/Header、qualified finish=1、transport failure=0；history与decision trace均为`ok`，10条ACK决策和audit source聚合一致。
- 平台终局分类为`platform_error`，不能用于胜负判断；ACK、binding、selected-action和provenance验证仍允许逐决策诊断。
- 第9个决策在既有共享策略认为应保留队友控桌资源时，由DeepSeek选择特殊牌压制。进一步检查确认模型prompt没有提供table leader identity/relation；现有strategy-intent组件可从同一公开输入生成`support_teammate / teammate_controls_table`，但Botzone factory将其关闭。
- strategy-intent接线已提交为`454a422`并通过独立复审。受约束执行报告随后给出off=`special`、on=`pass`和`strategy_intent_target_decision_improved`；规划Codex独立复核trace仍为88,983 bytes / SHA-256 `4ba2ea88a13046f8f7907df6dd124175dceee3a88e9723be88c6581a28bc3512`且Git clean。
- 全10条trace的后续只读审计判定为`seed_47003_no_additional_high_confidence_candidate`；规划Codex独立复算分类一致且三个后置守卫触发数均为0。本局至此封板。下一步只对现有队友小王→大王合成fixture执行一次守卫前真实模型检查，不重开Botzone live、不修改代码。
- 原fixture随后被证明含有不能压小王的伪合法单张9；该次调用改判inconclusive。修复检查点`8db3154`已把目标候选收敛为pass与大王，并经规划Codex独立通过41/39/710项。下一步只对修正后的canonical fixture重新执行一次守卫前模型检查。
- 修正后canonical模型检查仍返回大王，判定`teammate_control_canonical_prompt_raw_model_not_ready`。当前泛化队友控桌reason与`endgame / endgame` RAG不足以表达特定资源代价；下一步只增加共享真值驱动的专用strategy-intent reason，不改RAG或扩大后置守卫。
- 专用reason已由`24fb362`完成并通过规划Codex独立83/39/712项验证。下一步只运行一次零重试、守卫前的canonical真实模型复放；实现本身不再待办。
- 新版专用reason的canonical真实模型复放返回原始合法pass，判定`teammate_big_joker_prompt_raw_model_improved`。`e30362f`已退役`teammate_control_block`主动覆盖；当前只待修正policy benchmark对legacy/活跃成功模型source的离线读取兼容。

### 2026-09-15 H3-A1 DeepSeek 中心策略系统获批

- 项目所有者确认项目优化目标不是扩大本地规则 AI，而是充分发挥 DeepSeek 在引擎合法动作空间内的掼蛋策略能力。本地层的职责是降低无效搜索：保证候选召回、计算公开结构事实、识别场景/目标、检索来源策略，并给出可验证的模型前推荐。
- 公式化开局源于开局直接交给模型时延迟高且结果不稳定，是当前的受限快速路径，不是长期独立决策中心。长期形态允许把高置信开局定式连同理由、替代候选和反例检查交给 DeepSeek；只在延迟约束和严格无歧义条件同时成立时保留本地直接动作。
- H3-A1 不再按单局中的 Q、4、10、对子或炸弹个案逐项打补丁，而以十个策略域一次性建立较完整目录：总体目标与冲突优先级；开局与自由领牌；手牌结构和拆牌成本；控制牌与回手资源；跟牌与牌权争夺；队友协同；危险对手阻断；炸弹和通配牌管理；残局规划；不确定信息与试探成本。
- 每条进入知识平面的策略至少表达可观察触发条件、策略目标、动作倾向、禁忌/反例和冲突优先级。作者、标题、出版信息、URL、来源等级与激活状态仅存于独立 provenance registry，以稳定 ID 关联；这些治理字段不得进入知识正文、检索评分、冲突扫描或模型 prompt。
- 同一批来源策略必须同步投影到四层：RAG 保存条件化原则与理由；router/decision chain 从公开 payload 识别场景和目标；prompt 展示结构事实、命中原则、候选差异及反例；公式只承载明确且高置信的开局定式。只扩充 RAG 而不补特征/路由，或只新增 prompt 文案而没有可测试机会判定，均不算完成。
- 模型前推荐采用“推荐动作或短名单 + 推荐理由 + 需要检查的反例”结构，目的是让 DeepSeek 验证聚焦的人类方案，而不是从大量同质候选重新推导整局。模型成功返回最终候选中的合法原始 ID 后必须保持该 ID 和 `model` source，不允许公式、selector、guard 或其他策略分支再次改写。
- 公式边界分三层：合法性/协议/唯一合法动作属于确定硬约束；严格开局条件下的高置信动作可作为可审计的本地快速路径；其余公式仅作为 DeepSeek 的模型前推荐。涉及队友意图、危险对手、炸弹/王的动态消耗、多路线残局或暗牌推断时，默认由 DeepSeek 裁决。
- H3-A1 的核心验收不是宣称每条经验绝对正确，而是验证关键候选可见、场景/目标正确、策略及反例进入模型输入、结构比较可追溯、模型动作保持自主，并能将偏差定位到候选、特征、路由、知识、prompt 或模型选择中的具体一层。
- 实施顺序固定为：先完成并独立复审 H3-A0a 最终候选硬预算/pair 召回；再用一个连贯 H3-A1 Coding 任务完成策略目录、来源内容、公开特征、router、RAG 与 prompt 投影及合成场景评测；最后用严格少于 10 次的预注册真实 DeepSeek 探针验证代表场景，是否 live 另行规划。
- H3-A0a 现已通过；`docs/NEXT_PROMPT.md` 已切换为 H3-A1。H3-A1 允许把已审计 C 级转载中的定性打法作为明确标识的软策略假设接入 RAG/prompt，但不得采用其未披露方法的统计数字、不得形成本地直接动作，也不得覆盖 B 级正文或引擎真值。书目/商品介绍仍保持 registry-only。

### H3-A1 纠错门槛（2026-09-15）

首次实现 `d20dba3` 不并入主线。进入真实模型诊断前必须在同一 Coding worktree 完成一次纠错提交，并由规划 Codex 重新复审组合 diff。纠错门槛为：

- 每个 active 经验条目必须有 loader→tagged retrieval→prompt 的可达证据；冲突扫描不得因“不能升级为暗牌事实”这类否定语境误杀记牌原则，同时仍拒绝真正的多局升级/贡还内容。
- 十个 `strategy_domain` 必须由公开局面派生并实际参与 RAG 与模型前输入，不能只作为 corpus 标签并集；有序目标、反例检查与可选 shortlist 分离，证据不足时可以不给 shortlist，但不能虚构本地决策。
- recommendation/candidate facts 只接受完整 canonical payload；所有枚举、ID、字符串、条数和字符预算严格 fail closed，调用方自由文本不得直接进入 prompt。
- 有界代表选择必须覆盖当前局面的关键关系，而不是任取原顺序前 12 项；四/五炸、natural single/pair、控制资源、wildcard、finisher 与 fragmentation 均须有关系型 fixture。
- B/C 来源映射不得升级证据等级；C 级炸弹等原则保持 `soft_hypothesis`，书目与统计内容不激活。
- 完成原 H3-A1 九组关系型 fixture、相关/主规则/全量回归和真实引擎多状态可达性离线探针后，才允许规划下一阶段严格少于 10 次的真实 DeepSeek 请求。
