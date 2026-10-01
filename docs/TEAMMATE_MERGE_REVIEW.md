# 队友融合版独立复审与使用说明（2026-10-01）

## 产物与验收

A_merged 位于 `D:\VsCodeProject\GuanDanMerged_10-1`，分支 `codex/merge-teammate`，业务提交 `fbdfa7eec91c3501b43da68b6326616075351afd`，五文件通过规划独立复审。原目录 `D:\VsCodeProject\GuanDan` 的业务仍为10-1.v1，队友输入 `D:\VsCodeProject\掼蛋程序` 未修改。原始版tag指向 `8d6a2579ea4eca0917d8a0ce49aaf8c8545c22fc`，独立bundle、zip及恢复说明保留在D:\VsCodeProject；规划文档更新不改变该冻结版本。

本轮是适配队友能力，并未确认原项目存在新的败局根因。两个项目座位、实体编码和接口不同，不能用同名文件覆盖完成融合。来源文件与指纹、未验证的队友声明见[TEAMMATE_MERGE_PLAN.md](TEAMMATE_MERGE_PLAN.md)。

## 实际融合内容

- 新增 `agents/teammate_fusion.py`：把队友局面经验改成条件性比较，涵盖队友传递、队友控桌、公开紧迫对手与控制资源、队友确为头游时争双下。建议只引用最终展示的原始合法ID，DeepSeek仍负责取舍。
- 本局公开事实统计：每家非pass次数、pass次数、实出张数、每次非pass均值、实际炸类及前12个公开动作步的炸类事件。炸类包括炸弹/同花顺/王炸；不按累计同点牌猜炸弹，不把pass计入均值分母，不生成跨局风格、暗牌或未来概率。
- `agents/card_tracker.py` 抽取既有公开历史校验供复用，旧pass证据机制保留；队友领牌者由验证后的历史取得，不能依赖桌面动作不存在的player_id字段。退出玩家不占行动位置，已完赛不自动当头游。
- `agents/deepseek_client.py` 与 `integrations/botzone/agent_runtime.py` 默认接入真实Request，增加独立融合开关；`tests/test_teammate_fusion.py` 保留五项稳定机制测试。

共用一个最多900字符的提示块、最多432步历史、局部50ms及既有DecisionDeadline预算；超预算或历史无效整块省略。保留现有80展示上限、M9/M10、规则真值与成功模型原始ID。没有新增依赖。双模型竞速、reasoning参数、对手持久画像/身份抓取、另一套引擎、8–12候选截断、原始日志和贡还/升级没有移植；不能据队友README声称性能或胜率已经得到复现。

## 验证证据

Coding使用原项目`.venv/Scripts/python.exe`，设置`PYTHON_DOTENV_DISABLED=1`和`PYTHONIOENCODING=utf-8`，真实模型/Botzone请求0。

- `python -m unittest tests.test_teammate_fusion -q`：5项通过，覆盖统计、炸类、重复token、无效历史/预算、座位/头游、默认Request与模型原ID。
- 直接受影响的默认M10 Request及Botzone runtime：18项通过；融合与共享pass/接风/M9早返/M10预算选测9项通过；最后变动的两个方法2项通过。以上集合有重叠，不相加制造测试数量。
- `git diff --check`及提交范围核对通过；业务提交仅上述五文件，工作树干净。
- 两个完整合法状态seed7/step32、seed13/step76，各21次外部perf_counter计时，新增计算中位1.354/2.183ms、最大1.636/2.396ms。仅代表这些样本，不是整体现场延迟承诺。

Coding的受影响选测命令（前缀为上述解释器，目录为融合项目）：

```powershell
python -m unittest tests.test_bounded_continuation.BoundedContinuationTests.test_default_factory_request_closes_original_ids_and_model_keeps_other_choice tests.test_botzone_deepseek_agent_runtime -q
python -m unittest tests.test_teammate_fusion tests.test_m5_public_inference_endgame.M5PublicPassEvidenceTests.test_pass_is_soft_candidate_specific_and_later_public_play_confirms_only_what_it_proves tests.test_m5_public_inference_endgame.M5PublicEndgameTests.test_partner_pass_resets_to_active_leader_and_search_matches_engine tests.test_m9_public_endgame_opportunities.M9PublicEndgameOpportunityTests.test_first_complete_proof_returns_before_later_root_actions tests.test_bounded_continuation.BoundedContinuationTests.test_incomplete_and_budgeted_blocks_return_no_partial_comparison -q
python -m unittest tests.test_teammate_fusion.TeammateFusionTests.test_invalid_or_incomplete_history_and_deadline_omit_whole_block tests.test_teammate_fusion.TeammateFusionTests.test_seats_first_finisher_and_finished_seats -q
```

规划独立检查没有机械重跑Coding清单或全量：

1. 原始版先保存seed83/step40、seed127/step48、seed13/step74与94的请求SHA摘要和候选/选择，再在融合版关闭开关逐项核对，四例完全一致；开启后去掉新增块也与关闭正文一致，候选、最终原ID/source=model不变，输入payload不变，引用均在最终展示内。
2. 根据公开history独立计数，与四例融合统计逐字段一致；用冻结10-1.v1的原始card_tracker比较旧/新pass evidence，25/29/42/52条证据完全一致。头游与非头游条件区分正确。
3. 对最终已提交版本额外执行seed13/step76真实default factory禁网fake请求：桌面无player_id仍正确识别队友P2领牌；389字符提示进入Request，引用在2个展示候选内；关闭后除提示块外正文一致，候选、选中ID及model来源保持。检查脚本只在内存使用payload/request，没有保存正文。
4. 完整源码diff确认没有生产seed/牌点/固定ID白名单、成功模型后置改牌或第二套规则；三个炸类名称是领域枚举。

验收结论：实现、统计与决策边界成立，当前范围内无已知剩余风险。有限经验能否改善真实模型取舍及实战胜率尚无证据，不把新增提示、fake模型或单元测试等同于收益。

## 使用与后续四版本比较

在融合目录运行既有入口；DeepSeek路径默认开启融合。代码调用可用 `build_agent_factory(..., teammate_fusion_enabled=False)` 或 `DeepSeekClient(..., teammate_fusion_enabled=False)` 关闭辅助，以便同状态比较。现有CLI没有新增开关参数，不要把该Python选项当CLI参数使用。

独立副本未复制`.env`或虚拟环境，真实运行前由所有者在融合目录自行配置私有凭据，并准备解释器/既有requirements依赖。现有README中的入口、模型配置和人工建桌流程继续适用；Codex本轮没有启动connector、访问现场目录或复制私有配置。原始与融合connector不能对同一端点同时轮询。

当前已具备A_original（10-1.v1）和A_merged，B_original是队友交付目录；B_merged尚需队友在其工程内完成反向融合。没有启动四版本胜率评测。待双方冻结版本及可运行入口明确后，再统一模型配置、共同裁判、座位/种子和规则胜平负/平台积分口径；当前没有下一项Coding任务，已执行NEXT_PROMPT撤下，不能从历史段落猜任务。
