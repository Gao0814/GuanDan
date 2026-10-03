# Coding：修复连续试局中断及汇总编码误报

这是当前唯一Coding任务，只处理运行正确性，不恢复Git历史中的去评分/条件计划/RAG/性能优化。所有者20局策略基线仍是10-3.v1；修复提交须明确区分运行修复与算法变化，先交Planning复审再由所有者手动重启，不操作现场。

## 已确认事实与复现入口

起始规划HEAD b1f7ba55100730e794ff6915cf6d0847276d0ea1，实际执行先核对当前Git。业务同10-3.v1，工作区当时干净。根AGENTS与botzone-game-audit Skill适用；只读私有证据，不读.env、不写原件、不输出完整请求/手牌/原reason/异常正文/会话标识。真实POST必须0，不启停connector或操作网页。

本次运行：`D:\VsCodeProject\BotzoneWorkspace\runtime\v2\runs\run-20261003T065708Z-d95514897c9d5c6d`；固定games清单容量已30、18个目录，索引有效，没有本轮滚动删除。7个新完局为内部74–80，结果文件7行，树结构通过校验；内部81在第9次公开观察后中断，不能当完局或补造结果。局号只是私有定位，不倒填外部局名/seed。

1. 真正的退出为`diagnostic_failure`/5，audit有`handler_failure=1`。失败局目录`D:\VsCodeProject\BotzoneWorkspace\games\2026_10_3_16-39-38_000081`，最后timeline为public_observation→handler_failure→interrupted；只有8次decision_started/模型完成，未为失败观察开始新模型请求。Planning在内存加载本次唯一非tombstone会话，结合最后observations的done/pass_on构造原HandlerContext，调用`project_decision`复现`AdapterError: done_capacity_invalid`（当前play_adapter.py 688）。原本家手牌与最后观测一致。平台done=[0]，公开历史累计玩家0出了26张；此前两次观察累计19/21张，最后窗口里该玩家出5张。自家剩22张、累计出5张守恒。已确认的是公开计数与done冲突，尚未证明遗漏发生在协议范围、会话拼接还是其他层，不能直接把校验删除当修复。
2. streams/stdout.txt不是UTF-8，可完整按GBK解码；末尾固定footer实际为`game_results=ok game_results_recorded=7 game_evidence=ok exit=5`，stderr空。manual_batch按UTF-8读取stdout失败，随后误报game_results/game_evidence incomplete和evidence_write_failed。打开重定向目标为encoding=utf-8不控制子进程直接写入文件描述符时的编码。修复应从真实子进程/汇总契约定位，不将读输出失败冒充留证写失败，也不吞错造ok。

## 目标与必要边界

- 先只读分析上述公开观察序列、会话merge_history/replay及ACK关系，说明26/27差异是否能精确定位/恢复，再选择最小统一修复。缺动作时不得猜牌、补造历史、借真实暗牌修复，不能用动作点数/局号/seed/ID特判。若只能保留不完整公开历史，应明确降级其确证/容量推导，保证本家实体扣牌、真实桌面约束与合法候选；若安全处理必须突破现有重要边界，先报告，不静默放宽。
- 本家守恒、重复实体拒绝、done不再出牌、双下/终局边界、原canonical与原模型ID/source、pending→ACK均保留。区分确证的done与不完整历史计数，不把缺失的1张硬塞进任一牌域；尤其不能让M9从不完整信息出证明，M10不得读暗牌。引擎规则/成功模型取舍、prompt、RAG、预算及参数不改。
- 修复子进程stdout编码与汇总错误分类。使用最小可测试的现有入口；不打印子进程原输出、HTTP/SSE、凭据或异常正文，不引入通用无限重试。需要补充诊断时仅固定低敏类别。
- 上次已修复的悬空绑定63与本次原因不同；其源代码滚动绑定同步缺口不要顺带重构。本次保留全部运行/牌局原件，不执行prepare_game_evidence或写盘复现，不修私有历史。

## 验证与交付

复用test_botzone_session、play_adapter、manual_batch及直接受影响测试，只选有价值的方法，不跑默认全量。临时禁网探针只在内存，不保存原件副本。真实诊断本次0 POST，不能要求所有者重打一局来定位。

验收重点：原失败上下文在正确层被处理；同类换座位/合法历史窗口变化与真实非法实体/容量反例可区分；既有完整历史投影/canonical不变；缺历史不产生M9证明；原合法模型选择与ACK闭环保持；Windows子进程中文输出按统一契约被读出，真实handler故障仍报故障、独立留证故障仍准确分类，不能只修合成正常footer。定向覆盖即可，已有覆盖充分不另建测试堆。

按Coding职责修改/提交自有业务与tests，不修改Planning文档。报告已确认根因/未决信息、统一修复及反补丁检查、实际命令/结果、commit/Git状态、对已有7局证据与运行版本的影响。未实际重启不得说现场恢复；策略收益不在本任务。若原根因无法安全修复，交付准确诊断和已独立解决的编码问题，明确剩余阻塞，不制造合法牌谱。
