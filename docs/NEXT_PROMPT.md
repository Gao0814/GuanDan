# Coding Codex 执行 Prompt

任务：仅对已保留的 seed `47004` 单局证据做一次**只读、禁网、内存中**的三处历史观察复放。通用来源策略整合 `bc3c083`、`2b9c24f` 已通过规划 Codex 离线复审；本任务不修改业务代码、测试、RAG、文档或配置，不创建仓库内外 artifact，也不重跑真实模型或 Botzone。先读取适用 `AGENTS.md`，检查 `.agents/skills/`，核对 Git status/diff/HEAD，阅读 `docs/PROJECT_STATUS.md` 顶部新结论、seed `47004` inventory、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md` 及 trace/候选/prompt 相关代码。保留所有外部修改。

固定 workspace 为 `D:\VsCodeProject\BotzoneWorkspace`。在读取任何 evidence 正文前，只对下列**精确相对路径**逐项核对普通非链接文件、字节数、SHA-256；不得枚举 `state`、猜测或查找替代路径：

| 相对路径 | 字节 | SHA-256 |
| --- | ---: | --- |
| `audit/completion-audit.json` | 781 | `018a95e4c6f286bb93f870d2c56baa6c05e6bde72b458f1a7dffdee61a0a88a4` |
| `decision-trace.json` | 261941 | `87607a11e7dc1acf41e74c86c34767012cd734130e891b7c2fc807e44618ee00` |
| `history.txt` | 11426 | `28864f2e44243085860e6bbbaa180b4fc7b663bc5825cc19416bb4387f23f7c8` |
| `state/6439aef518ba6343a0e4ba8c6a1294dc5fc70703f31588a048cc19f7435e4e47.json` | 115 | `6037548d58f35dceb751ecdf25216f83cdfee5cdde9848e1db99550ee95b4c55` |
| `streams/stdout.txt` | 76 | `4ad569f46ba5902d05b4780156b64f78b24802141f94c880b6afbd051ad9df1c` |
| `streams/stderr.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

任一精确目标不匹配则立即停止正文读取，报告失败门槛，不寻找替代证据。六项全通过后，仅在内存中核对 trace ACK、原始公开 observation 和当时完整 canonical legal actions 的基本守恒，再使用当前生产算法及禁网 fake transport 构造最终候选、RAG/策略意图/推荐和实际最终 Request；不得把历史实际动作当作新模型会选的动作。定位并复放三处旧观察：同点数四/五炸及残余孤张、较高普通单张开局与低成本单张、自然对子/同点单张清理。逐场只报告低敏结论：当前本地公式是否直出、两侧关键候选是否进入最终 `<=80` 集合、相关来源软原则/具体关系/反例是否进入实际 Request，以及若缺失的责任层。若 trace 不足以唯一定位场景，明确 `inconclusive`；不要猜手牌或补现场点数特判。

真实 DeepSeek 请求/重试、Botzone/live/connector/browser/preflight、workspace 清理与仓库修改均为 0；不读取 `.env`、旧 H3 ledger 或系统 Temp。不得输出或持久化历史手牌、逐动作牌面、原始 action ID、prompt 正文、模型文本、URL、token、凭据或 match/binding 标识。执行前后检查 Git status 与 `git diff --check`，报告六项门槛、三处低敏判定、零副作用和最终 Git status；无修改不创建 commit。交规划 Codex 复审后再决定是否需要集中真实模型验证。
