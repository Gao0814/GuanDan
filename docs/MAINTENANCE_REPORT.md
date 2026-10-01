# 去重与回收记录（2026-10-01）

## 当前判断与范围

所有者要求直接在GuanDan继续、回收不再需要的内容，10-1.v1保留可恢复。此前独立融合统计/提示与已有记牌和资源输入重复，没有独立收益证据；合并接线验收不能当增量能力验收。Coding业务bf712a956f9ca173b018739c56a978dab1592129已通过独立复审，在cao原目录交付。只补现有局面段的头游争二游双下目标，复用队伍/完赛公开事实，既有规则RAG同步双下/三游终局；原引擎、记牌器、M9/M10、候选与成功模型ID保持。没有移入teammate_fusion模块、开关、第二套历史遍历或重复行为统计。

当前方向修正：走错在于把来源不同的重新汇总当成新能力；对照原card_belief/card_tracker及实际Request中已有的座位/控桌/紧迫性即可更早发现重复。

## 外部已回收

均使用Microsoft.VisualBasic.FileIO的SendToRecycleBin，精确核对普通属性、归属和子项；没有清空回收站。

|D:\VsCodeProject下路径|依据|
|---|---|
|GuanDanMerged_10-1|无未提交内容/私有.env/.venv；16edb6b及fbdfa7e已fetch保存到原仓库codex/merge-teammate，125914906字节副本不再使用|
|GuanDan_10-1.v1.zip|与保留的完整bundle重叠，1424101字节|
|GuanDan_9-26_v0.bundle与_RESTORE.txt|旧提交c5a8bb9是10-1.v1祖先，保留bundle含完整历史，36289184+735字节|
|GuanDan_merge_8d6a257_20261001.zip及.sha256|已交付的一次性源码交换产物，可从冻结版本重新导出，322043+102字节|
|.guandan-exclusive-open-scope-4595d6c4d3c64c0c9090f30cdc45829b|空的旧临时目录，无引用或内容|
|GuanDanH3A2Audit|7份已审计旧阶段低敏账本，36113字节；文件名/哈希均与旧PROJECT_STATUS审计记录相符|
|GuanDanManualEvidenceArchive|4份已审计个人试局的旧归档，共27文件959410字节，白名单/非链接/无运行Python已核对；仅回收，不读取私有正文|

在用BotzoneWorkspace、GuanDanManualWorkspace、队友掼蛋程序与GuanDan.code-workspace保留；原私有.env/.venv/logs不动。Git不能恢复未纳入版本管理的现场证据，已回收旧归档需从回收站找回。

## 文档收敛

PROJECT_STATUS、PLAN、CLEAN_HANDOFF、TESTS、BOTZONE_INTEGRATION_PLAN、CODING_BOUNDARY、BELIEF_STATE、STRATEGY_SOURCE_AUDIT收敛为当前事实、有效边界和入口，原完整文件先送回收站，历史另在a1ea0e6及以前提交保留。OPENING_ALGORITHM_PROMPT、LIVE_GAME_REVIEW、TEAMMATE_MERGE_PLAN/REVIEW为已执行任务/旧复盘/副本说明，回收其文件，不新建常驻历史文档目录。规则裁判摘录、不变量、来源登记、M10及规则性能复审保留必要证据。

## 恢复点

10-1.v1仍指向8d6a2579ea4eca0917d8a0ce49aaf8c8545c22fc。保留D:\VsCodeProject\GuanDan_10-1.v1.bundle，36867873字节、SHA256=05ecf621c1c5d9046d8eb12d264ae9e198ede6034302bcd444606399d9ac3084；git bundle verify确认完整历史、无外部前置依赖，此前实际独立克隆恢复通过。恢复说明/SHA已同步为单一bundle，不再指向回收的zip。

回收站内容与Git提交提供不同恢复能力；本轮不执行历史重写或直接reset，不改变10-1.v1。当前没有真实收益结论或四版本胜率结果。

## 业务回收与必要覆盖

Coding回收37个tracked文件853777字节及26个精确缓存928122字节，合计1781899字节，均进入Windows回收站。没有永久删除或清空回收站。

- archive_legacy的10个已退役历史文件，无主线入口引用，包含旧多人/比赛层及专属测试。
- 以下13个evaluation模块与各自tests/test_<同名>.py成对退役，当前只服务旧proxy/冻结M2/阶段ablation/benchmark，无现役业务依赖：action_quality_calibration、action_quality_proxy、action_quality_sensitivity、confidence_action_ablation、confidence_action_quality、confidence_prompt_benchmark、h3_a9_quality_queue、m2_expanded_same_state_eval、m2_same_state_model_eval、strategy_intent_action_ablation、strategy_intent_action_quality、strategy_intent_prompt_benchmark、strategy_router_benchmark。
- record.txt是已完成旧审计输入，没有运行依赖，未读正文。

精确tracked路径可用`git show --name-status bf712a9`恢复；包含缓存的逐路径回收metadata在系统临时目录GuanDan-retired-20261001-inventory.json，完整低敏执行报告为GuanDan-coding-maintenance-bf712a9.json。当前仓库不再新增常驻诊断脚本或历史报告目录。

h3_model_probe_fixtures和short_endgame_scenarios仍被现役开局/关系/残局测试复用，因此保留。terminal、共同Botzone比较、conditional-pressure及通用belief/rank/marginal工具保留。双下测试去掉退役proxy专属校准case，仍验证完整108张实体局面、两队视角、未知个人名次、保守终局与规则平；没有删除揭示未解决问题的有效断言。

## 实际验证与独立复审

Coding用原.venv解释器，PYTHON_DOTENV_DISABLED=1、PYTHONIOENCODING=utf-8，三条定向命令分别3/5/2项通过（最后两项复核最终改动，有重叠不相加）：

- `python -m unittest tests.test_suit_resource_projection.SuitResourceProjectionTests.test_teammate_head_double_down_context_reaches_request_without_changing_model_choice tests.test_double_down_evaluation -q`：3项通过，2.935秒。
- `python -m unittest tests.test_rag_step_h.TestRAGStepH.test_front_matter_tags_are_parsed_from_markdown tests.test_rag_step_h.TestRAGStepH.test_rag_context_does_not_mutate_legal_actions tests.test_strategy_relationship_contrasts.StrategyRelationshipContrastTests.test_medium_opening_group_relation_activates_matching_b_principle_in_final_request tests.test_m9_public_endgame_opportunities.M9PublicEndgameOpportunityTests.test_first_complete_proof_returns_before_later_root_actions tests.test_bounded_continuation.BoundedContinuationTests.test_default_factory_request_closes_original_ids_and_model_keeps_other_choice -q`：5项通过，2.317秒。
- `python -m unittest tests.test_suit_resource_projection.SuitResourceProjectionTests.test_teammate_head_double_down_context_reaches_request_without_changing_model_choice tests.test_rag_step_h.TestRAGStepH.test_front_matter_tags_are_parsed_from_markdown -q`：2项通过，1.224秒。

规划没有重跑Coding清单或全量，额外检查：

1. 从完整seed13发牌旋转座位/两队并以P2起始推进74步，得到队友P4头游；加载10-1.v1原始DeepSeekClient与当前factory禁网fake对照，正文只增正确双下目标句，4个展示ID/最终ID/source=model不变。另seed127/step48无头游，7个展示ID、正文及最终ID/source完全一致。观察/canonical保持原样，payload和请求只在内存使用。
2. 剩余183个Python文件内存compile和项目AST导入闭包通过，37个退役tracked路径均不存在；两个现役入口`python -m cli.run_4ai_debug --help`及`python -m integrations.botzone --help`通过。
3. 本地Markdown文件链接检查通过；Git对照确认engine、原card_belief/card_tracker、bounded_continuation及integrations与10-1.v1一致；完整业务diff没有生产seed/牌点/ID旁路或模型后置覆盖。
4. 独立bundle再次verify通过，保留的SHA及10-1.v1引用未改变。

验收结论：当前范围内无已知剩余风险。未运行全量或真实模型/现场请求；未跑全量不是验收障碍，当前没有真实胜率收益结论。完成的NEXT_PROMPT已回收，不生成没有真实任务的下一份Prompt。

文档收敛核对：a1ea0e6的docs为21文件/1331896字节；本轮当前为17文件，约109215字节（本统计句加入前）。规则与必要机制证据保留，减少来自已完成阶段重复过程。
