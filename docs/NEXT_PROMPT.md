# Coding Codex 执行 Prompt

任务：只针对已复现的同点数自然四/五炸选择，改进**模型前**公开取舍表达。来源策略整合与跟牌关系修复已经让旧固定局面的两侧候选、残余关系、反例及软经验进入实际 DeepSeek Request；随后一次真实请求仍原始选择了“四炸留同点孤张”。这只证明该固定状态的选择没有自动转成五炸，不证明四炸在所有局面都错误。开局单张、中局对子两场只记录为 `other`，不能据此推定旧动作重现；本任务不修改它们。

先按 `AGENTS.md` 检查适用 Skill、Git status/diff/HEAD，确认包含 `1b6d59d` 且无需要保留的外部改动；阅读 `docs/PROJECT_STATUS.md` 顶部、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`，以及 `agents/action_structure.py`、`agents/deepseek_client.py`、`agents/strategy_intent_prompt.py`、炸弹相关经验 corpus/provenance 和直接测试。仅 Coding Codex 可改本任务所需业务代码/测试，规划 docs 不要改。

目标是通用、有条件地说明：四炸与五炸都是合法原始动作；五炸多耗一张但清空该点数组、避免同点残余孤张且本手炸弹更强。四炸所“节省”的第五张只有在公开手牌结构、后续组合、牌权或协同上有可说明的价值时才是有效收益；不能把留下孤张本身笼统称为资源优势。若公开候选与出后结构能证明第五张无其他可识别的组合收益，模型前建议应明确倾向五炸，同时列出可推翻条件（例如立即出完、保留可验证的更高价值结构、公开紧急性或牌权安排）。若证据不足，就保留中性对照，不编造暗牌或确定收益。检查并协调关系 prompt 与相关 C 级软经验，避免两处措辞相互抵消。只从 `observe()` 与完整 canonical `legal_actions()` 推导，不针对 seed `47004`、具体点数、动作 ID 或历史响应写特例；不修改 `engine/`。

保持 DeepSeek 对最终合法候选的裁决：四/五炸两侧都保留在有界最终请求中，最终候选 `<=80`，推荐 ID/请求体闭环，模型返回的原始合法 ID 原样保留且 source=`model`；禁止 post-model 策略覆盖、过滤四炸、固定本地直出或新增 decision source。若现有公开结构不足以可靠判断“第五张无其他组合收益”，先用最小共享公开结构摘要表达可证事实；不能证明时 fail closed，而不是把推测写成确定结论。不要扩大到开局单张、对子、RuleBased 续局代理或新策略阶段。

用引擎构造自由领牌与跟牌的正反例，覆盖同点自然四/五炸同时合法、四炸确实留同点孤张、五炸确实清空、第五张另有可识别结构价值、缺一侧候选或残余前提不成立；在真实 `DeepSeekClient` 禁网 transport 路径核对实际 Request 中的候选两侧、明确取舍及反例，并用 fake 成功返回分别验证原始 ID 与 `model` source 守恒。先跑定向，再跑主规则和全量测试，`git diff --check`；如环境导致全量结果不可审计，明确报告而不要声称通过。

本任务真实 DeepSeek 请求/重试、Botzone/live/connector/browser/preflight 均为 0。不要读取 `.env`、旧 H3 ledger、Botzone workspace/seed evidence 或系统 Temp，不创建仓库外 artifact。只提交自己修改的业务/测试/知识文件，报告提交、测试、最终 Git status 和保留外部修改。不要宣称 prompt 修改已改善真实模型选择或胜率；完成后交规划 Codex 复审，由规划层决定下一次整局验证，不继续拆分探针。
