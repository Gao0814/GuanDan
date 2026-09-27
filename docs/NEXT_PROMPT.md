# Coding Codex 执行 Prompt：先修批次入口的进程匹配，再由所有者验证

## 事实与目标

所有者两次启动 `scripts/run_manual_botzone_batch.cmd`，均在连接前收到 `connector_already_running`，页面没有“已连接”。报错后规划只读检查未见匹配的 Botzone 进程，因此无法证明报错瞬间的进程身份。已确认现有 `-m integrations.botzone\b` 正则既匹配真正的 connector，也匹配 `-m integrations.botzone.manual_batch`；这是一条值得直接修复的误判路径，不要求先查明历史两次报错的唯一根因。

本任务先用最小改动使进程探测准确区分当前批次启动器、其他批次启动器与真正的 connector，保留防止第二个 connector 同时轮询的保护。修复后由所有者亲自启动脚本并在 Botzone 页面检查连接；若有效，记录为这条假设得到现场支持；若仍失败，再根据新错误继续定位，不把本轮修改声称为旧报错的既定根因。

## 实现与验证

先读 `AGENTS.md`、相关代码/测试及 `docs/PROJECT_STATUS.md` 顶部，查 Git status/diff/HEAD。重点修改 `integrations/botzone/manual_batch.py` 的进程匹配，按完整模块名或等价边界识别 connector，避免仅因模块名前缀就把启动器算作 connector。不要无条件关闭进程保护、自动杀进程或启动第二个真实 connector。保留 `.cmd` 的窗口等待、`--no-pause`、退出码、默认 10 局、旧证据隔离、`deepseek-flash` 和现有动作/ACK 逻辑。

用少量针对性禁网测试直接覆盖：`-m integrations.botzone.manual_batch` 不被当作真正 connector；`-m integrations.botzone` 会被拦；无冲突时能进入既有预检/启动路径。必要时覆盖另一批次同时启动的情况。不要为证明历史根因先增加一套 PID/父子进程日志；若修复后仍出现占用类别，再补低敏诊断。运行相关测试、适用主回归和 `git diff --check`；不要运行真实 Botzone、connector、联网预检或 DeepSeek 请求。

只提交本轮自身业务代码与 tests，不改规划 docs、`.env`、两个 workspace 旧证据或封板。报告改了什么、禁网测试结果、仍未知的现场根因、commit 和最终 Git status。给所有者直接可用的启动说明；现场是否“已连接”留给所有者验证。
