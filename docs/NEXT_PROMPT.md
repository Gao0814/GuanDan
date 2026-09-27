# Coding Codex 执行 Prompt：定位并修复批次入口反复进程占用拦截

## 当前事实与目标

所有者运行 `scripts/run_manual_botzone_batch.cmd` 两次，均在 Botzone 显示“已连接”前得到 `batch_error category=connector_already_running exit=2`；第二次刷新页面也无连接。规划在第二次报错后立即只读扫描，当前没有匹配的 Botzone Python/py 进程；同一 `.venv` Python 调用现有探测函数返回 `connector_absent`。这是**事后**状态，不能证明报错瞬间无进程。现有 guard 的 `-m integrations.botzone` 前缀正则可能把 `-m integrations.botzone.manual_batch` 启动器也归为 connector；是否为本次根因尚未证实。

交付一个真正能让所有者启动单个前台 connector、空闲及局间持续等待的批次入口。保留真实已有 connector 的防并发保护；不要用关闭 guard、静默重试或修改 Botzone 页面来掩盖故障。所有真实 connector 启停和 Botzone 页面操作仍由所有者完成。本 Coding 任务只做禁网代码与测试，不运行真实 connector、联网预检、DeepSeek 请求或浏览器。

## 工作范围

先读 `AGENTS.md`、项目 Skills 清单、`README.md`、`CLAUDE.md`、`docs/PROJECT_STATUS.md` 顶部、`docs/PLAN.md` 顶部、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`；查 Git status/diff/HEAD。重点检查 `manual_batch.py` 的 `_connector_probe_argv`、进程匹配与调用时机，两个 `.cmd` 入口、`runner.py` 的 idle/退出行为和相关测试。不要把本次启动前拒绝写成历史的中途停牌或 DeepSeek 超时。

1. 禁网构造可重复的 Windows 进程探测场景：当前批次启动器及其父子启动链、另一个批次启动器、真正的 `python -m integrations.botzone` connector、无关 Python 进程。明确哪些命中现有 guard，避免仅用 mock 写一个永远返回预期字符串的测试。进程命令行只在内存中用于分类；输出/文件不得包含原始命令行、连接 URL、token、密钥或环境变量。
2. 启动被拒绝时输出足以定位的固定低敏类别及匹配进程 PID/角色（例如真实 connector、另一个批次启动器或未知），不输出可变异常正文。若发现本批次自身启动链被误判，最小修复；若发现真正的并发 connector，继续拒绝并说明由所有者处理。不要自动终止任何进程。若原两次现场报错仍无法从旧证据还原具体 PID，如实标注未知。
3. 保持 `905b246` 的窗口等待、`--no-pause` 和退出码，默认 10 局可改、固定 workspace 每批全新子目录、`deepseek-flash`、119 秒期限、stage trace、逐局低敏结果、ACK 与算法现状。禁网验证一次前台 connector 在 idle、两局之间持续轮询，达到目标或明确中止才结束；真实故障和上限仍按原有类别报告。

## 验收与提交

测试须覆盖真正的 Windows 进程匹配/分类逻辑与脚本入口，不仅覆盖 fake 返回值；包括自启动链不误拦、真实 connector 会拦、无匹配者能继续零网络预检、重复报告时可定位 PID/角色、窗口可见结果/退出码及 `--no-pause`。运行相关测试、主规则回归、适用全量测试、`git diff --check`。不得用真实 Botzone/DeepSeek 来完成测试。

只提交本轮自身业务代码和 tests；不要修改规划 docs、`.env`、封板、旧 workspace evidence。报告已证实的根因与仍未知之处、验证、真实请求数（应为 0）、commit 与最终 Git status。完成后给所有者直接可执行的启动方式及若仍失败应保留的固定低敏输出；现场“已连接”只能由所有者后续确认。
