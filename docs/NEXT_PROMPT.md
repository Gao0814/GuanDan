# 给执行 Codex 的下一任务 Prompt

使用项目 Skill `botzone-workspace-recycle`，把已经完成审计并写入项目状态的 seed `47003` evidence 从固定 workspace 逐文件移入 Windows 回收站，为后续最新 HEAD 的单局 DeepSeek 采样准备空 workspace。本任务只清理，不运行 preflight、connector、Botzone、浏览器或模型，不修改仓库文件，不创建 commit。

## 【开始前与硬边界】

1. 完整阅读并遵守 `AGENTS.md`、`.agents/skills/botzone-workspace-recycle/SKILL.md`、`docs/CLEAN_HANDOFF.md` 和 `docs/PROJECT_STATUS.md`。
2. 记录 Git HEAD/status；工作树必须 clean。确认 `D:\VsCodeProject` 的直属 `Botzone*` 集合精确为普通非链接目录 `D:\VsCodeProject\BotzoneWorkspace`。
3. 确认 workspace root、保留目录和下列六个目标都是普通非链接对象，递归 inventory 与 allowlist 精确相等；确认没有可安全归因的项目 connector 在运行，但不得输出进程命令行或任何敏感参数。
4. 任一名称、类型、大小、SHA-256、目录集合、Git 状态或运行状态不符，执行零清理并报告差异。不得猜测新 hash、扩大 allowlist 或处理未知文件。

## 【精确文件 allowlist】

按以下顺序逐个处理：

1. `D:\VsCodeProject\BotzoneWorkspace\audit\completion-audit.json` — 787 bytes — SHA-256 `a9376fa5d0a4aaaf7383cbdffd62964689105a93ea9da3e7522f68d598caf4cc`
2. `D:\VsCodeProject\BotzoneWorkspace\decision-trace.json` — 88983 bytes — SHA-256 `4ba2ea88a13046f8f7907df6dd124175dceee3a88e9723be88c6581a28bc3512`
3. `D:\VsCodeProject\BotzoneWorkspace\history.txt` — 7108 bytes — SHA-256 `b41585b48b43ae34bcd4a85984d6efb45c3dbed2fc9df737ced285f568a5e884`
4. `D:\VsCodeProject\BotzoneWorkspace\state\8bec80eb3ec277378dc9e537c95f908b6268d91a453f09e916cd76f1dac62355.json` — 115 bytes — SHA-256 `0d896426c2e72aa2267034838d8efb3afb2b37f88cce52cc46a8f0e4f7e9b9e9`
5. `D:\VsCodeProject\BotzoneWorkspace\streams\stderr.txt` — 0 bytes — SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
6. `D:\VsCodeProject\BotzoneWorkspace\streams\stdout.txt` — 76 bytes — SHA-256 `7a8c855dfcbc5b6b7218991d2e2caeb7479bc2dc9ae87787434572af78d399dc`

## 【回收方式】

- 只能通过 Windows 回收站 API（例如 `Microsoft.VisualBasic.FileIO.FileSystem::DeleteFile(..., SendToRecycleBin)`）按 allowlist 顺序逐个回收文件。
- 禁止永久删除、递归删除、通配符、目录删除、跨 shell 拼接路径、清空回收站或改用其他删除机制。
- 若某一文件回收失败，立即停止，精确报告已完成和未处理目标；不得继续或切换方法。

## 【必须保留与最终状态】

- 保留普通非链接 workspace root：`D:\VsCodeProject\BotzoneWorkspace`。
- 保留三个普通非链接空目录：`audit`、`state`、`streams`。
- 成功后的递归 inventory 必须只含上述三个空目录，文件数为 0；`D:\VsCodeProject` 直属 `Botzone*` 集合仍只含固定 workspace。
- Git HEAD/status 必须与任务开始时一致；永久删除数为 0；不得产生仓库、workspace 或其他位置的新文件。

## 【完成报告】

报告前提是否全部通过、六个目标的低敏路径/大小/hash、逐项回收结果、最终目录与文件计数、顶层 `Botzone*` 集合、connector/live/model/preflight/browser 是否均为 0、永久删除数、Git HEAD/status，以及是否存在任何未处理或外部修改。完成清理后结束任务，不继续下一次 live。
