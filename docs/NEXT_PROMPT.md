# Coding Prompt：个人 Botzone 启动器收敛为同一 connector 的目录选择

项目所有者明确要求：Codex 原有 Botzone 执行方式和固定 `D:\VsCodeProject\BotzoneWorkspace` 不变；个人双击 `scripts/run_manual_botzone.cmd` 时，仅选用独立的 `D:\VsCodeProject\GuanDanManualWorkspace` 保存证据。两者共用现有 `python -m integrations.botzone`、同一私密 URL/密钥配置与网络连接实现，不开发第二套 connector，不要求所有者重复提交未变的页面配置。先读根 `AGENTS.md`、`docs/PROJECT_STATUS.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、README、启动器及其测试；检查 Git status、diff、HEAD，仅提交自己修改的文件。

请最小修改个人启动器、对应离线测试和 README：

1. 以此前已成功进入 Botzone 请求流程的 Codex 直接调用为运行参数基线（历史执行 Prompt 见 `8fb5b40:docs/NEXT_PROMPT.md`）：`--agent deepseek`、80 cycles、1800 秒墙钟、默认 30 秒请求超时、单次完成后停止、相同的 audit/history/trace 语义和仅在 connector 进程中设零模型重试。个人路径只替换 `state`、audit、history、trace、stdout/stderr 的目标，不改 URL、密钥、代理、传输或 Agent 选择。旧成功进程的 Python 解释器及环境未留可比证据；不得声称已证实二者相同。若需要保留解释器发现逻辑，预检和真实运行仍须使用同一个解释器及同一继承环境。
2. `.cmd` 应继续是所有者唯一的双击入口，但包装层只负责个人 workspace 的安全检查/轮换、路径选择及启动同一 connector。不得使 Codex 默认路径进入个人目录，也不得清理或覆盖 Codex workspace。保留个人证据的归属、普通非链接、白名单、无并发 connector 和出问题后暂停下一次启动等保护。
3. 修复双击窗口在 connector 退出后无法查看结果的可观察性：显示固定低敏退出码/停止类别，并使人工双击场景能读到结果；自动化测试不应因此挂起。不得显示 URL、密钥、token、手牌、prompt 或模型自由文本。零网络预检通过仍不得写成“已连接”。
4. 用 fake Python/transport 和 scratch workspace 覆盖 Codex 调用与个人入口除证据路径外的参数等价、解释器/环境传递、无并发、轮换安全、退出可观察性及不泄密。运行 PowerShell 5.1/7 启动器测试、Botzone 配置定向测试及必要回归；检查 diff。不得读取 `.env`、启动真实 connector、访问 Botzone/DeepSeek、运行 live 或触碰两个真实 workspace。若无法做到严格参数等价，明确报告实际差异，不要用延长墙钟上限宣称已经修复此前 20 次 transport timeout。

完成后提交范围内的代码、测试和 README，并报告 commit、Git status、验证及保留修改。此任务只收敛启动方式；真实页面是否显示“已连接”须由所有者在提交后单独试运行确认。若仍未连接，保留个人 workspace，后续再做受控连接对照；不得在本任务声称网络根因已定位。
