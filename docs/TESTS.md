# 当前测试与验证说明

具体执行约定以根AGENTS.md“测试要求”为准。本文件只列现役能力入口，不累计历史任务的命令、测试数量或全量门槛。

## 选择范围

默认验证修改模块；规则、接口或共享计算改变其他调用链时，补少量直接受影响的方法/文件。现有覆盖充分就不新增测试；纯文档做链接/diff检查。一次性性能/诊断可从stdin执行，不进入默认discover。

全量命令`python -m unittest discover -q`保留可选，只有所有者明确要求，或已确认广泛影响无法定向覆盖时才选择并说明理由；未跑全量本身不影响验收。成功的Coding检查在Planning复审不机械重跑。

## 现役测试入口示例

以下按本次影响选择，不是固定全部执行列表：

|能力|代表文件|
|---|---|
|规则/牌型/轮转与终局|test_patterns.py、test_rules.py、test_game_flow.py、test_botzone_rule_alignment.py|
|公开观察/canonical/adapter|test_botzone_adapter_observation.py、test_botzone_play_adapter.py、test_botzone_action_provenance.py|
|公开牌池与容量|test_card_belief.py、test_card_constraints.py、test_card_allocations.py、test_card_tracker.py|
|候选/结构/资源/模型返回|test_action_structure.py、test_recommendation_candidate_closure.py、test_suit_resource_projection.py、test_public_rule_response_summary.py|
|M9与M10|test_m9_public_endgame_opportunities.py、test_bounded_continuation.py|
|RAG与模型输入|test_rag_provenance.py、test_rag_step_h.py、test_deepseek_prompt_step_h.py|
|Botzone运行/期限/留证|test_botzone_deepseek_agent_runtime.py、test_botzone_decision_deadline.py、test_botzone_manual_batch.py、test_botzone_request_diagnostics.py|
|CLI|test_cli_debug_output.py|

测试在仓库根运行，例如：

```powershell
./.venv/Scripts/python.exe -m unittest tests.test_bounded_continuation.BoundedContinuationTests.test_incomplete_and_budgeted_blocks_return_no_partial_comparison -q
```

离线验证设置`PYTHON_DOTENV_DISABLED=1`，使用fake transport/示例配置，不读真实.env或发请求。报告实际命令、结果及支持的证据层级。

## 长期覆盖与回收

稳定规则、公开信息守恒、接口、预算回退和真实决策链边界应保留。已退役独立评测入口及只验证该工具的测试，可核对引用闭包后由Coding回收；被现役测试复用的fixture不能直接删除。不能通过删失败测试掩盖问题。测试文件数量不等于验证质量。

真实DeepSeek选择、多局实战与胜率比较不是单元测试的推论；对固定级牌2无贡单局范围，不附加跨级牌/贡还/升级泛化门槛。
