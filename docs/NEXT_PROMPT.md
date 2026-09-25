# Coding Codex 执行 Prompt：修复个人 Botzone 单命令入口的 Windows PowerShell 兼容性

先读取根 `AGENTS.md`、`docs/PROJECT_STATUS.md` 顶部、`docs/CLEAN_HANDOFF.md` 顶部、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`，核对当前 Git status/diff/HEAD。只处理 `7b432ff` 个人 Botzone 启动器的入口兼容问题；多牌型开局仍暂停。普通个人自测不属于 `.agents/skills/botzone-manual-live/SKILL.md` 的 Codex 监督 live 范围，也不得清理 Codex 固定 workspace。

规划复审已复现：PowerShell 7 的 `tests/test_manual_botzone_launcher.ps1` 为 13 组/43 断言通过，Botzone 配置测试 5 项和 CLI `--help` 通过；但本机 Windows PowerShell 5.1 的 `LocalMachine=AllSigned` 拒绝 README 所示直接执行 `.\scripts\run_manual_botzone.ps1`。以 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tests\test_manual_botzone_launcher.ps1` 运行时，12 组通过，最后的入口解析断言失败；5.1 对 `scripts/run_manual_botzone.ps1` 的 `ParseFile` 报第 87 行缺少 `Catch/Finally`、第 103 行多余 `}`。同一文件先按 UTF-8 正确解码再由 5.1 `ParseInput`，错误为零。该问题会让用户在常见 PS 环境中无法启动一次试局，不能用 PowerShell 7 的结果代替验收。

交付一个真正可从 Windows PowerShell 5.1 用**单条命令**调用的个人入口。建议增加极薄的 `scripts/run_manual_botzone.cmd`，它仅调用仓库内固定的 `.ps1`，用仅作用于本次子进程的执行策略覆盖本机 `AllSigned`，透传退出码；同时把 `.ps1` 保存为 Windows PowerShell 5.1 能从文件正确解析的编码（例如 UTF-8 BOM）或采用等效兼容方案。README 的所有者一条命令改为实际可运行的入口，并简要说明企业组策略若禁止进程级覆盖时应停止，不建议全局放宽策略。不得通过下载、签名伪造、全局/CurrentUser 策略修改或隐藏执行失败来绕过限制。

只改入口、README 和对应离线测试的最小范围。保持现有个人路径 `D:\VsCodeProject\GuanDanManualWorkspace`、Codex 路径隔离、归属/白名单/回收站门槛、先预检后连接、前台单 connector、真实证据与私密配置边界不变。不要修改业务策略、引擎、Botzone 协议、`.env`、项目 Skills 或规划文档。跨版本测试至少覆盖 PowerShell 7 与 Windows PowerShell 5.1 文件解析、实际单命令入口的进程级策略行为及退出码传递；测试只能使用 scratch/fake 或安全静态核对，绝不调用真实 launcher 流程、真实 preflight、connector、Botzone、DeepSeek、网络，也不创建或访问个人/Codex workspace。若本机策略无法模拟某种路径，明确标注未验证，不得宣称真实连接已成功。

复跑现有 PowerShell 13 组/43 断言（可扩展）、禁用 dotenv 的 `tests.test_botzone_runtime_config`、CLI `--help`、`git diff --check`。只暂存/提交自己修改的脚本、README 和测试；报告复现与修复后的两版 PowerShell 结果、唯一推荐用户命令、commit、最终 Git status 和保留的外部修改。个人目录当前不存在，不要在本任务创建或轮换它。修复提交后等待规划 Codex 独立复审，再安排所有者首次自测。
