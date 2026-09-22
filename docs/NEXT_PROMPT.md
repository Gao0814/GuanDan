# Coding Codex 执行 Prompt

任务：H3-A4q1a——仅封住离线资格工具的实际请求体绑定缺口，不发起真实模型请求。`b229371`已让八场RAG正例ready、空/错配RAG fail closed；规划Codex复审发现，禁网客户端在`_build_structured_prompt()`里先记录`final_prompt`，而真正放进请求正文的是该方法的返回值。注入仅改变返回值、保留记录值的反例后，实际请求缺`【模型前建议】`，资格仍误报ready。

## 边界

1. 阅读适用`AGENTS.md`、检查`.agents/skills/`，阅读`README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`及相关代码/测试。先检查Git status、diff、HEAD，完整审阅`b229371a70817c80992dee33a4bec136bdb6b84f`。保留外部修改。
2. 只改`evaluation/h3_model_probe_fixtures.py`及`tests/test_h3_model_probe_fixtures.py`中必要部分。不得改生产DeepSeek、RAG、引擎、Botzone、配置、规划docs或其它文件；如遇生产路径反例，提供低敏最小复现并交回规划Codex。
3. 真实DeepSeek请求/重试、网络、Botzone、live、connector、browser、preflight均为0。不读`.env`、旧`h3-a2r.jsonl`/`h3-a4.jsonl`、`D:\VsCodeProject\BotzoneWorkspace`、seed`47004` evidence或系统Temp文件，不新建仓库外artifact。牌面、action ID、prompt、请求正文、模型文本、URL、token及异常正文不得输出或持久化。

## 最小纠错

1. 在现有禁网transport里只以内存方式捕获其真正收到的`Request`正文，严格解码固定JSON envelope并取得实际user prompt；资格门槛必须核对它与客户端记录的`final_prompt`一致、必需marker确实在请求体里，且transport恰好调用一次。解析错误、缺消息、格式漂移或计数不守恒一律固定阶段fail closed。不要在日志或测试失败消息里输出请求正文。
2. 确认资格使用的最终候选与实际请求prompt里展示的候选一致，至少防止已有`displayed_actions`/`final_actions`记录与最终发送内容分离；保持原始ID、签名、80项预算及source=`model`校验。优先复用生产客户端当前构造结果，不另写第二套策略剪枝器。
3. 新增最小反例：子类先调用`super()._build_structured_prompt()`记录正常`final_prompt`，随后只在返回值中删除`【模型前建议】`，使实际请求体不含该marker；资格必须不ready。另测坏JSON envelope或缺user message、transport零次/重复调用，以及候选记录漂移均不能ready。八场固定正例和现有空/错配RAG、软假设反例继续通过。测试使用注入transport，不访问网络或dotenv。

## 验收

- 运行`tests.test_h3_model_probe_fixtures tests.test_strategy_relationship_contrasts tests.test_recommendation_candidate_closure tests.test_h3_a1_projection tests.test_strategy_recommendation tests.test_action_structure`、主规则回归和`python -m unittest discover -q`；捕获可审计汇总，检查`git diff --check`。
- 只暂存并提交这两个自有文件，报告提交hash、八场固定资格/反例、测试计数、最终Git status及保留外部修改。真实模型调用0；不得宣称H3-A4真实诊断完成或策略质量改善。
