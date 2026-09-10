# 给执行 Codex 的下一任务 Prompt

使用现有`teammate_control_block`单元测试中的队友“小王控桌、本家可用大王压制且pass合法”合成公开fixture，执行一次当前生产strategy-intent开启时的真实DeepSeek原始动作检查。必须在任何确定性后置策略守卫应用之前读取模型原始选择；本任务不修改代码，不运行Botzone。

项目所有者发送本Prompt即授权：通过项目现有配置向当前配置的DeepSeek模型发送这一份合成公开observation、原始legal actions、当前RAG与strategy-intent prompt，总计最多一次模型请求。不得扩大授权范围。

## 【开始前】

1. 阅读并遵守`AGENTS.md`，检查适用项目Skills；本任务不使用live或workspace-cleanup Skill。
2. 阅读`docs/CLEAN_HANDOFF.md`以及`agents/deepseek_ai.py`、`agents/conditional_pressure_pass_policy.py`、strategy router/prompt和对应测试。检查Git状态必须clean，确认HEAD包含`454a422`。
3. 从现有测试提取目标合成fixture的公开字段，不读取seed `47003`手牌或`.env`文件正文。DeepSeek配置只能经现有`AppConfig`/client装配使用，任何密钥或端点不得输出。

## 【目标与方法】

- fixture必须严格满足当前`teammate_big_joker_pass_id()`的全部公开前提：队友单张小王领牌、原始pass与大王压制均合法、模型若选大王不会立即出完、对手均未结束且余牌大于2、history/table一致。
- 使用当前生产设置生成`ready / support_teammate / teammate_controls_table`；若不是该状态，停止且不调用模型。
- 使用当前生产RAG、动作剪枝、模型、temperature和其他请求参数，client重试固定为0。
- 直接取得模型返回的原始action ID并验证它是原始legal actions中的严格整数ID。不得先经过`_preserve_teammate_big_joker()`、`DeepSeekAIAgent`成功动作后置守卫链或RuleBased替代。
- 外部模型请求上限严格为1。失败、非法结果或前置不满足时不得重试。

## 【隐私与禁止事项】

- 只报告原始动作类别：`pass`、`target_special`（以大王压队友小王）或`other_legal`，不得输出action ID、牌面、完整observation/legal actions、prompt、模型response/reasoning、API key、URL、Header、Cookie或其他配置正文。
- 不修改代码、tests、docs、配置或`D:\VsCodeProject\BotzoneWorkspace`；不创建报告文件或Git commit。
- 不运行Botzone、Edge、connector、preflight、live、容量评测或全量测试。

## 【唯一判定】

- 原始模型选择`pass`：`teammate_control_prompt_raw_model_pass`。这只支持下一步规划将`teammate_control_block`改为shadow或退役候选，不直接授权本任务修改生产代码。
- 原始模型选择`target_special`或其他合法非pass：`teammate_control_prompt_raw_model_not_ready`。下一步应诊断并补强模型上下文，不得用该结果扩展后置覆盖。
- 前置、请求或合法性失败：`teammate_control_prompt_raw_model_inconclusive`。

最终报告：唯一判定、intent状态、RAG低敏scene/action-context、模型调用状态、原始动作类别与合法性、实际外部请求数、Git HEAD/status；同时确认仓库与workspace未修改。不得输出敏感正文。
