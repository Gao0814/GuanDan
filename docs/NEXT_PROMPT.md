# 执行 Codex Prompt：已审计 Botzone workspace 的独立回收

本任务只为下一次人工单局准备空的固定 workspace；**不运行** preflight、connector、Botzone/live、浏览器、DeepSeek 或任何网络请求，不分配 seed，不修改仓库文件或创建 commit。先阅读仓库 `AGENTS.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md` 顶部以及 `.agents/skills/botzone-workspace-recycle/SKILL.md`，严格按该 Skill 执行；检查 Git status、diff、HEAD，确认工作树 clean 且 HEAD 包含 `f67faf6`，保留任何既有修改。本任务已由规划 Codex 对上一局六份 evidence 作审计并写入状态文档；AGENTS.md 的长期授权仅覆盖下述精确文件。

固定 workspace：`D:\VsCodeProject\BotzoneWorkspace`。先只读确认 `D:\VsCodeProject` 直属、名称以 `Botzone` 开头的目录精确只有普通非链接的 `BotzoneWorkspace`；workspace 根目录和 `audit`、`state`、`streams` 均为普通非链接目录。递归 inventory 必须**恰好**是这三个目录与下列六个普通非链接文件，没有其他文件、子目录或链接。逐项核对完整大小和 SHA-256，不能只核前缀，不能解析或输出证据正文、搜索替代路径、猜测哈希或接受新文件：

1. `audit/completion-audit.json` — 781 bytes — `018a95e4c6f286bb93f870d2c56baa6c05e6bde72b458f1a7dffdee61a0a88a4`
2. `decision-trace.json` — 261941 bytes — `87607a11e7dc1acf41e74c86c34767012cd734130e891b7c2fc807e44618ee00`
3. `history.txt` — 11426 bytes — `28864f2e44243085860e6bbbaa180b4fc7b663bc5825cc19416bb4387f23f7c8`
4. `state/6439aef518ba6343a0e4ba8c6a1294dc5fc70703f31588a048cc19f7435e4e47.json` — 115 bytes — `6037548d58f35dceb751ecdf25216f83cdfee5cdde9848e1db99550ee95b4c55`
5. `streams/stdout.txt` — 76 bytes — `4ad569f46ba5902d05b4780156b64f78b24802141f94c880b6afbd051ad9df1c`
6. `streams/stderr.txt` — 0 bytes — `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

另以不输出命令行或凭据的方式确认无可归属的在运行项目 connector。任何 Git、类型、路径、目录集合、大小、hash、connector 或 inventory 门槛不符，**零清理、立即停止并报告**；不得自行修订预期值或处理未知对象。

全部前提通过后，才按上述顺序逐文件使用 Windows 回收站 API（例如 `Microsoft.VisualBasic.FileIO.FileSystem::DeleteFile(..., SendToRecycleBin)`）回收；每项处理前再次确认其精确路径和身份。不得永久删除、递归删除、移除目录、清空回收站、跨 shell 拼接路径或切换删除机制。任一回收失败即停，报告已处理与未处理项，不重试或扩大目标。

最后只读确认六条原路径均不存在，固定根和 `audit`、`state`、`streams` 仍为普通非链接且空目录，整个 workspace 文件数为 0，直属 `Botzone*` 集合未漂移；Git HEAD/status 不变。报告各项低敏结果、永久删除数、是否留下外部修改，并结束此清理任务；**不要接着启动单局**。若成功，交规划 Codex 复审空 workspace 后再单独安排 live。
