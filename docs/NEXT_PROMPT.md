# Coding Codex 执行 Prompt：120 秒个人桌的整次 DeepSeek 决策期限

> 当前阶段：M0 中途停牌可用性。项目主线仍为掼蛋算法优化；本任务先使现场请求在有限时长内交付合法动作，以便随后算法试测可解释。这是一个包含实现与禁网验收的 Coding 工作包。

## 开始前

阅读适用的 `AGENTS.md` 与项目 Skills 清单、`README.md`、`CLAUDE.md`、`docs/PROJECT_STATUS.md` 顶部、`docs/PLAN.md` 顶部、`docs/CLEAN_HANDOFF.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`；检查 Git status、diff、HEAD。阅读 Botzone DeepSeek factory、agent fallback、SSE transport、connector 响应/ACK、runner、stage trace、个人启动器及相关测试。Coding 只改任务直接相关的源代码、tests、必要的启动说明，并只提交本轮自有修改；规划文档由规划 Codex 维护。

不启动个人脚本、真实 connector、Botzone 对局或真实 DeepSeek 请求；不读取/修改 `.env`，不输出密钥、连接 URL 或模型自由文本；不访问或轮换 `D:\VsCodeProject\GuanDanManualWorkspace` 与 `D:\VsCodeProject\BotzoneWorkspace`。两份异常证据已归档于 `D:\VsCodeProject\GuanDanManualEvidenceArchive\20260926-153323-midgame-stall` 和 `D:\VsCodeProject\GuanDanManualEvidenceArchive\20260926-154450-teammate-lead-platform-error`；本 Prompt 的低敏摘要已足够，无需再读原始牌谱。

## 事实、假设与目标

- `f5fb88a` 只加阶段观测。第一份异常证据最后停在 `model_enter`，没有本次 `model_complete` 或准备响应；前两次模型调用约 17.8/56.5 秒成功。这定位了本地最后可见边界，**不能确定**是服务端思考、持续 SSE、单次阻塞读、进程终止或平台时限所致。
- 第二份队友首出异常证据中，已观察模型调用全部成功；11/11/11 请求/响应/Header、10 次本家决策并获 ACK，最长模型约 70.6 秒，最终仍 `platform_error`。用户报告页面本家倒计时结束未出牌；本地证据无法证明该超时轮已送达 connector。不要宣称本次期限改动会修复所有 `platform_error`。
- 所有者又报告两局开局未出牌，现将个人 Botzone 桌延时设为 **120 秒**。当前 `DEEPSEEK_TIMEOUT` 是 `urllib.urlopen(..., timeout=...)` 的网络读取超时；SSE 分段读取可累计超过它，runner 墙钟只在 cycle 间检查。设 `DEEPSEEK_TIMEOUT=120` 不保证 120 秒内出牌。

在 Botzone DeepSeek 路径实现**单调时钟计量的整次决策期限**：从收到 play 请求或进入决策的明确边界计时，为解析、合法回退、准备响应及 ACK 留出余量。对所有者已配置的 120 秒个人桌，个人启动路径给出明确、保守的默认总预算，建议不超过 90 秒；该值可配置、可预检，并与单次读取超时严格区分。期限内 DeepSeek 仍是主要决策者；到期或 transport 卡住时走既有 canonical 合法动作回退，及时准备**唯一**响应。不得借机对成功模型动作作策略改牌，不改引擎规则或协议动作语义。

## 实现边界

1. 先确认模型生成、重试、SSE 消费、Agent 选择和 connector pending/ACK 的实际调用边界。总期限须约束连接建立、单个阻塞读、分段 SSE 和重试；预算耗尽不得再重试。不能只在每行读取后检查时间。到期后网络资源或后台工作须有界关闭或隔离，不得让迟到模型 ID 覆盖回退、写出第二份 Header，或随回合积累无界请求。普通 CLI 默认行为和其他桌计时如需保持原样，应将预算限定在明确 opt-in 的 Botzone/个人路径；不要把 120 秒假设硬编码进通用 DeepSeek 客户端默认值。
2. 期限触发要形成低基数 timeout/fallback 结果；回退 ID 必须来自当前 `legal_actions()` 原始 canonical 集。source、audit、decision trace、阶段事件与既有 ACK 事务守恒。Header 交给 poll 不等于 ACK，pending 动作不得作为已确认决策落盘。页面倒计时结束但本地未收到 play 请求的边界保持未定，不伪造动作。
3. 个人启动器实际启用并显示本次**决策总预算**及需匹配的 Botzone 120 秒桌设置。预检拒绝零、负值、非数、达到桌面计时或安全余量不足的值。保持普通 CLI stage trace 默认关闭、个人路径显式开启；不改 `.env` 或持久化私密配置。若 `DEEPSEEK_TIMEOUT` 超过总预算，实际等待仍必须由总期限约束，或在启动时 fail closed。保持个人目录回收前的归属、普通非链接、allowlist、无 connector 核验。

## 禁网验收与交付

- 用 fake clock、可控 transport 或必要的短时本地阻塞，验证正常约 70 秒的分段 SSE 在预算内成功并原样选择模型合法 ID；小于 30 秒间隔但累计越过总期限的 SSE；无换行阻塞读；连接建立卡住；重试跨期限；到期后才返回合法模型 ID。每种超时边界都在预算内交付一次 canonical 合法 fallback，且无迟到覆盖、第二动作、无界 worker 或错误 ACK。测试要验证时间边界，而非只断言传了 timeout 参数。
- 以禁网实际 `build_agent_factory("deepseek")`、个人启动参数和 connector 事务验证：模型成功保留 `model` source，限时回退 source/计数/阶段事件低敏且一致；Header、pending、poll 返回、ACK 与 trace 原始候选守恒；preflight-only 不发阶段事件、不开始模型调用。复跑相关 Botzone/DeepSeek 单测、PowerShell 7 与 Windows PowerShell 5.1 个人启动器测试、主规则回归、`python -m unittest discover -q` 和 `git diff --check`。
- 报告预算起点、阻塞读取时期限如何生效、资源如何停止或隔离、相对 120 秒桌保留的响应/ACK 余量、个人启动默认参数、测试与局限、提交和最终 Git status。合成测试不能证明所有 `platform_error` 消失。Coding 不启动下一局；规划复审后由所有者亲自试测，异常先保留证据。

M0 放行及恢复 M1/M2 的条件见 `docs/PLAN.md` 顶部；来源化开局、多牌型候选、条件化 B/C RAG 与 DeepSeek 优化 Prompt 保存在 `docs/OPENING_ALGORITHM_PROMPT.md`。
