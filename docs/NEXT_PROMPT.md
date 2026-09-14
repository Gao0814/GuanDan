# 给执行 Codex 的下一任务 Prompt

使用项目 Skill `botzone-workspace-recycle`，继续上一轮按失败即停规则中止的 seed `47003` evidence 回收。本任务只处理当前仍存在的三个精确文件；完成后保留固定 workspace 与三个空目录。本任务不运行 preflight、connector、Botzone、浏览器或模型，不修改仓库文件，不创建 commit。

## 【已审计的部分完成事实】

- 上一任务已把 `audit\completion-audit.json`、`decision-trace.json`、`history.txt` 逐项移入 Windows 回收站；规划 Codex 已独立确认三条路径均不存在。
- 上一任务在第四项回收前因执行脚本误抄预期 hash 而停止；第四项本身未移动，其实际 115 bytes / SHA-256 与原任务值一致。第五、六项也未处理。
- 该失败已经结束上一清理任务。本恢复任务必须重新执行全部适用安全门槛，不能沿用进程或内存状态，也不得恢复、寻找或再次处理前三项。

## 【开始前与硬边界】

1. 完整阅读并遵守 `AGENTS.md`、`.agents/skills/botzone-workspace-recycle/SKILL.md`、`docs/CLEAN_HANDOFF.md` 和 `docs/PROJECT_STATUS.md`。
2. 记录 Git HEAD/status；工作树必须 clean，HEAD 必须包含 `f426693`。确认 `D:\VsCodeProject` 的直属 `Botzone*` 集合精确为普通非链接目录 `D:\VsCodeProject\BotzoneWorkspace`。
3. 确认 workspace root、保留目录和下列三个目标都是普通非链接对象；递归 inventory 必须精确为三个保留目录加三个 allowlist 文件，不得有其他对象。确认上一轮三个已回收路径仍不存在。
4. 确认没有可安全归因的项目 connector 在运行，但不得输出进程命令行或任何敏感参数。
5. 任一名称、类型、大小、SHA-256、目录集合、已回收路径、Git 状态或运行状态不符，执行零清理并报告差异。不得猜测新 hash、扩大 allowlist 或处理未知文件。

## 【本轮精确文件 allowlist】

按以下顺序逐个处理：

1. `D:\VsCodeProject\BotzoneWorkspace\state\8bec80eb3ec277378dc9e537c95f908b6268d91a453f09e916cd76f1dac62355.json` — 115 bytes — SHA-256 `0d896426c2e72aa2267034838d8efb3afb2b37f88cce52cc46a8f0e4f7e9b9e9`
2. `D:\VsCodeProject\BotzoneWorkspace\streams\stderr.txt` — 0 bytes — SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
3. `D:\VsCodeProject\BotzoneWorkspace\streams\stdout.txt` — 76 bytes — SHA-256 `7a8c855dfcbc5b6b7218991d2e2caeb7479bc2dc9ae87787434572af78d399dc`

必须继续不存在的旧路径：

- `D:\VsCodeProject\BotzoneWorkspace\audit\completion-audit.json`
- `D:\VsCodeProject\BotzoneWorkspace\decision-trace.json`
- `D:\VsCodeProject\BotzoneWorkspace\history.txt`

## 【回收方式】

- 只能通过 Windows 回收站 API（例如 `Microsoft.VisualBasic.FileIO.FileSystem::DeleteFile(..., SendToRecycleBin)`）按本轮 allowlist 顺序逐个回收文件。
- 执行脚本中的预期 hash 必须逐字复制本 Prompt 的完整值；实际 hash 与预期值比较通过后才可回收对应文件。
- 禁止永久删除、递归删除、通配符、目录删除、跨 shell 拼接路径、清空回收站或改用其他删除机制。
- 若某一文件校验或回收失败，立即停止并精确报告已完成和未处理目标；不得在同一任务修正、重试或切换方法。

## 【必须保留与最终状态】

- 保留普通非链接 workspace root：`D:\VsCodeProject\BotzoneWorkspace`。
- 保留三个普通非链接空目录：`audit`、`state`、`streams`。
- 成功后的递归 inventory 必须只含上述三个空目录，文件数为 0；`D:\VsCodeProject` 直属 `Botzone*` 集合仍只含固定 workspace。
- Git HEAD/status 必须与任务开始时一致；永久删除数为 0；不得产生仓库、workspace 或其他位置的新文件。

## 【完成报告】

报告前提是否全部通过、本轮三个目标的完整低敏路径/大小/hash、三个旧路径是否继续不存在、逐项回收结果、最终目录与文件计数、顶层 `Botzone*` 集合、connector/live/model/preflight/browser 是否均为 0、永久删除数、Git HEAD/status，以及是否存在任何未处理或外部修改。完成恢复清理后结束任务，不继续下一次 live。
