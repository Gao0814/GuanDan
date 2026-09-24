# Coding Codex 执行 Prompt

任务：一次性封住来源策略整合后的**跟牌四/五炸模型前关系缺口**，并复核两条 C 级经验未命中的实际语义影响。不要按 seed、具体点数或历史 action ID 加补丁，也不要另拆 H3-A 子阶段。先核对 Git status/diff/HEAD 与外部修改，阅读适用 `AGENTS.md`、检查 `.agents/skills/`，阅读 `docs/PROJECT_STATUS.md` 顶部最新复放结论、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、`docs/STRATEGY_SOURCE_AUDIT.md` 及相关生产代码和测试。只改本任务必要的 `agents/`、`rag/`、`tests/`，必要时改离线 `evaluation/`；不改引擎、Botzone、配置、规划文档或 `.env`。

1. 通用缺口：当前 `summarize_candidate_contrasts()` 在收集四/五炸前排除了所有跟牌事实，`strategy_intent_prompt` 也把 `bomb_residual` 视为只能自由领牌。旧局恰是跟牌：同点自然四炸与五炸都在完整合法动作及最终 5 项候选中；四炸留同点孤张，五炸清空点数组，软原则已到达但两侧关系句/反例缺席。只在**当前 canonical 跟牌候选同时确证同点自然四炸和五炸、残余结构可验证**时生成该关系，并让 router/RAG/推荐/两层候选保护/最终请求的验证与投影一致；自由领牌原行为不退化。不得推断对手暗牌，不强制模型出五炸，也不得新增成功模型后动作改写。
2. 以多个引擎构造的自由领牌和跟牌状态做正反测试：两侧实际合法时均在最终 `<=80` 候选、请求体含具体残余比较与可推翻条件；缺一侧、通配声明、畸形 payload 或残余事实不成立时不制造关系。用禁网 fake transport 证明实际请求候选与返回原始 ID 闭环，source=`model`；既有退役 source 只读兼容、不在生产主动产生。
3. 对历史开局单张与中局对子，不把“专项 C 条目未进默认 top-k=1”直接等同于策略输入缺失：规划复核确认两场的合法候选、具体关系及反例已在最终请求。逐项对照 `exp_soft_single_cost_probe_001`、`exp_soft_pair_probe_001` 的正文和实际 Request，判断是否仍有**独特、可行动、公开可证**的语义未被关系句表达。若没有，保持 RAG 不变并给出低敏证据；若有，只做有界且通用的检索/投影修正并补实际请求测试，不能机械提高全局 top-k、无条件强制所有 C 级条目命中、挤掉更重要证据或让 provenance 字段进入模型。此判断不需要对历史动作作优劣裁判。
4. 实现与测试完成后，再只读核对下表六份 seed `47004` evidence。固定 workspace 为 `D:\VsCodeProject\BotzoneWorkspace`；逐项核对精确相对路径、普通非链接类型、字节与 SHA-256，任一不符就停止正文读取，不枚举或找替代。全部匹配才在内存中对三处 ACK 局面做禁网最终 Request 后验检查，报告四/五炸关系是否补齐，以及单张/对子语义是否仍在；不持久化或输出手牌、逐动作牌面、原始 action ID、prompt/模型文本、凭据或 match/binding 标识。

| 相对路径 | 字节 | SHA-256 |
| --- | ---: | --- |
| `audit/completion-audit.json` | 781 | `018a95e4c6f286bb93f870d2c56baa6c05e6bde72b458f1a7dffdee61a0a88a4` |
| `decision-trace.json` | 261941 | `87607a11e7dc1acf41e74c86c34767012cd734130e891b7c2fc807e44618ee00` |
| `history.txt` | 11426 | `28864f2e44243085860e6bbbaa180b4fc7b663bc5825cc19416bb4387f23f7c8` |
| `state/6439aef518ba6343a0e4ba8c6a1294dc5fc70703f31588a048cc19f7435e4e47.json` | 115 | `6037548d58f35dceb751ecdf25216f83cdfee5cdde9848e1db99550ee95b4c55` |
| `streams/stdout.txt` | 76 | `4ad569f46ba5902d05b4780156b64f78b24802141f94c880b6afbd051ad9df1c` |
| `streams/stderr.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

真实 DeepSeek 请求/重试、Botzone/live/connector/browser/preflight、workspace 清理均为 0，不读取旧 H3 ledger 或系统 Temp。运行直接相关、主规则和 `python -m unittest discover -q`，检查完整 diff 与 `git diff --check`；仅按明确路径暂存本轮自有业务/测试文件并提交。报告通用正反例、三处旧观察的低敏后验、C 级语义判断、测试数、commit、最终 Git status 与保留外部修改，交规划 Codex 独立复审。旧局输入修正不等于真实模型策略质量或胜率提升。
