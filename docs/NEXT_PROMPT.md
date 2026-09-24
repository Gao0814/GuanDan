# Coding Codex 执行 Prompt

任务：对来源策略整合后的三个固定历史公开状态做**一次集中真实 DeepSeek 原始选择诊断**。这不是新 Botzone 对局、胜率评测或生产代码修复。开始核对 Git status/diff/HEAD，确认包含 `1b6d59d` 且无待处理外部修改；读取适用 `AGENTS.md`、检查 `.agents/skills/`，阅读 `docs/PROJECT_STATUS.md` 顶部结论、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、trace 解析及 DeepSeek/候选/策略输入相关代码。仓库文件一律不修改、不创建 commit；不读取旧 H3 ledger 或系统 Temp，不运行 Botzone/live/connector/browser/preflight，不清理 workspace。

预注册真实请求上限为 **3 次**：跟牌四/五炸、开局低成本/较高自然单张、中局自然对子/同点单张，按此固定顺序各一次，重试 0。项目所有者对单项诊断严格少于 10 次真实请求已有长期授权；不得把“最多 3 次”扩大为重跑、换 prompt、换 fixture 或额外模型调用。只使用当前生产 `DeepSeekAIAgent`/`DeepSeekClient`、当前配置模型与真实 transport；`DEEPSEEK_MAX_RETRIES=0` 仅限本进程。密钥从既有配置读取，不输出、硬编码或持久化。模型 reasoning/响应自由文本、prompt、手牌、逐动作牌面及原始 action ID 只可在内存中处理，不输出或保存。

先逐项只读核对固定 workspace `D:\VsCodeProject\BotzoneWorkspace` 下六个**精确相对路径**的普通非链接类型、字节数和 SHA-256。任一不符就停止，不读取正文、枚举 state 或找替代：

| 相对路径 | 字节 | SHA-256 |
| --- | ---: | --- |
| `audit/completion-audit.json` | 781 | `018a95e4c6f286bb93f870d2c56baa6c05e6bde72b458f1a7dffdee61a0a88a4` |
| `decision-trace.json` | 261941 | `87607a11e7dc1acf41e74c86c34767012cd734130e891b7c2fc807e44618ee00` |
| `history.txt` | 11426 | `28864f2e44243085860e6bbbaa180b4fc7b663bc5825cc19416bb4387f23f7c8` |
| `state/6439aef518ba6343a0e4ba8c6a1294dc5fc70703f31588a048cc19f7435e4e47.json` | 115 | `6037548d58f35dceb751ecdf25216f83cdfee5cdde9848e1db99550ee95b4c55` |
| `streams/stdout.txt` | 76 | `4ad569f46ba5902d05b4780156b64f78b24802141f94c880b6afbd051ad9df1c` |
| `streams/stderr.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

六项通过后，才在内存中读取 ACK trace，以公开 observation 和当时完整 canonical actions 唯一定位三场。**三场离线资格必须全部 ready 才发出首个真实请求**：24 条 ACK 顺序与合法 ID 守恒；当前版本三场最终候选分别为 5/47/13、各不超过 80 且签名唯一；对应两侧原始合法候选均在实际最终 Request；四/五炸有残余关系、软原则和反例，单张/对子有对应关系、可推翻条件及公开结构信息；实际 Request 与记录的最终候选集合一致。专项 C 级单张/对子条目不必强求进入默认 top-1，只验收其可行动语义已到达。使用禁网 transport 先验证请求体绑定和 fake 合法 ID/source 保真；定向运行 `tests.test_strategy_relationship_contrasts`，不需因仓库零改动重跑全量。任一资格失败则真实请求保持 0，报告失败层级，不临时修代码或换状态。

资格通过后才按预注册顺序发出真实请求。每次调用前写 `request_started`，完成后写 `request_result`；若 provider/transport/解析/ID/source 守恒出现异常，立即停止，不能重试或补发。仅记录低敏动作类别：炸弹为 `five_clears_rank` / `four_leaves_singleton` / `other`，单张为 `lower_safe_single` / `higher_single` / `other`，对子为 `natural_pair` / `same_rank_single` / `other`。成功结果必须是实际最终候选中的原始合法 ID、source=`model`；类别不代表好坏，不把历史动作或 RuleBased 选择当正确答案。

为避免终端输出丢失，创建一份新的低敏账本 `D:\VsCodeProject\GuanDanH3A2Audit\source-three-scene-20260924.jsonl`，仅追加本轮事件；若该精确文件已存在就停止，不覆盖或改名重试。仅允许 header、三条资格、`qualification_complete`、每请求一对 started/result、summary 事件，字段只含 HEAD、场景固定代号、候选数、资格布尔/失败阶段、provider 固定结果类别、上述动作类别、技术守恒布尔和计数。不得含手牌、牌面、原始 ID、prompt、模型文本、URL/token/凭据、match/binding 标识或异常正文。结束时重读校验事件顺序/配对/计数，报告账本字节数与 SHA-256。该账本是客户端侧记录，不是独立网络计数证明。

最终报告三场技术资格、实际请求/重试/provider 计数、逐场低敏动作类别、候选/source/返回值守恒、账本校验、Git HEAD/status 和所有保留外部修改。执行前后检查 `git diff --check`；不提交仓库文件。无论模型选了哪类动作，都不据三次单点选择宣称最优打法、普遍改进或胜率；交规划 Codex 复审后再决定是否还有需要修正的具体输入层问题。
