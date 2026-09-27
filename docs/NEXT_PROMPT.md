# Coding Codex 执行 Prompt：修复 Windows venv 启动链自拦截

## 已证实事实

`fe507d5` 已将真正 connector 与批次启动器的模块名分开；所有者重试仍未连接，截图现在显示 `batch_error category=batch_launcher_already_running exit=2`。规划只读核查发现，本机 `.venv\Scripts\python.exe` 启动时会出现父、子两个 `python.exe` 进程。`manual_batch.py` 的探测只排除 `os.getpid()`；在不运行 Botzone 的安全复现中，用同一 `.venv` Python 进程和形如 `-m integrations.botzone.manual_batch` 的命令行参数调用 `_connector_probe_argv(os.getpid())`，得到 `batch_launcher_running`。因此**当前启动链会误报另一个批次启动器**，与截图类别吻合。历史两次旧类别的确切进程身份仍未知，不需要先解决。

## 本轮修复

先读 `AGENTS.md`、相关代码/测试、`docs/PROJECT_STATUS.md` 顶部并查 Git status/diff/HEAD。仅在 `integrations/botzone/manual_batch.py` 的进程占用检查及直接相关测试中修复：识别并排除属于**本次启动**的 Windows venv Python 父子包装进程；独立的另一个批次启动器继续返回 `batch_launcher_already_running`，真正的 `-m integrations.botzone` connector 继续返回 `connector_already_running`。不要删除整项占用检查、自动杀进程、改变 Botzone 连接配置或扩建日志。保留 `.cmd` 窗口行为、默认 10 局、旧证据隔离和现有动作/ACK 逻辑。

用禁网进程级测试复现修前 `batch_launcher_running`、修后 `connector_absent`，并验证独立启动器与真正 connector 仍被拦截；可复用上述安全 `-c` 加额外命令行参数方式，**不得调用真实 `manual_batch` 主入口**。补跑相关单元测试和适用主规则回归，执行 `git diff --check`。测试不要启动真实 connector、Botzone、联网 preflight、浏览器或 DeepSeek 请求。

只提交本轮自己的业务代码/tests，不改规划 docs、`.env`、两个 workspace 旧证据或封板。报告复现及修后结果、测试、commit 和最终 Git status。完成后由所有者亲自启动现有脚本并确认页面“已连接”；Coding 不代为执行现场。
