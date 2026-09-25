# Coding Codex 执行 Prompt：定位个人 Botzone 启动器与旧成功路径的连接差异

先读根 `AGENTS.md`、`docs/PROJECT_STATUS.md` 顶部、`docs/CLEAN_HANDOFF.md` 顶部、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、`README.md` 和个人启动器/对应测试。检查 Git status/diff/HEAD，不混入他人修改。项目所有者已明确确认：Botzone 本地 AI 页面 URL/密钥未改变，设置一次后无需反复提交，过去 Codex 曾在该账号成功连接。不得再以“重交页面配置”代替启动路径排查。

第二次个人启动的已审计 v8 audit：exit 6、`wall_limit_unfinished`、20 cycles 全部为 transport timeout，0 HTTP/网络错误、0 对局请求、0 模型请求、0 决策；运行后无残留 connector。第二次个人目录 `D:\VsCodeProject\GuanDanManualWorkspace` 是待保留的异常证据，**不得运行真实启动器、真实 preflight、connector、Botzone、DeepSeek 或浏览器；不得创建、轮换、清理或读取 Codex 固定 workspace**。不要读取、输出、散列或持久化真实 URL、密钥、`.env`、代理地址、Cookie、prompt、模型文本或牌面。前次成功运行的 connector 核心源代码从 `8fb5b40` 至当前 HEAD 未变；旧 seed `47005` Prompt 可由 `git show 384c903^:docs/NEXT_PROMPT.md` 查到，使用 `--max-cycles 80`、`--max-wall-seconds 1800`、默认请求 timeout 30 秒；个人脚本使用 100/600/30。此差异有解释力，但尚未证明是页面未连接的根因，不能简单延长时间后宣称修复。

本任务只做**禁网、合成配置的差异复现和最小必要纠错**：逐项比较旧成功命令与 `.cmd`→`.ps1`→Python 的实际参数、解释器、工作目录、URL/代理环境继承、预检与真实运行的差异。使用纯合成 URL、代理变量、fake transport 或 scratch 子进程，确保比较结果只输出布尔值、固定类别或计数，不回显任何真实私密配置。检查 Windows PowerShell 5.1 与 PowerShell 7 路径；测试前后检查无真实个人/Codex workspace 写入。重点验证 `.cmd` 包装器确实把调用者的 Botzone URL 和代理环境无损传给真实 Python 子进程、预检与运行使用同一值、运行参数不意外进入 `--preflight-only`。若发现可复现的启动器缺陷，做最小修复并加禁网回归；若只发现 600 秒墙钟上限或静默输出这类可观察性差异，明确其影响边界，可改进低敏状态提示，但不得伪称已解决连接。若无法离线定位根因，不做猜测性网络/策略改动，报告 `inconclusive` 与下一次受控真实连接 A/B 所需门槛。

修改范围限于个人启动器、README 与其离线测试；不改 `integrations/botzone` 协议、agents、engine、RAG、`.env`、规划 docs 或项目 Skills。复跑 PowerShell 7 与 5.1 的启动器测试、禁用 dotenv 的 `tests.test_botzone_runtime_config`、CLI `--help`、`git diff --check`。只暂存提交自己的文件，报告可复现根因或未定位边界、验证结果、commit、最终 Git status 和保留的外部修改。多牌型开局仍暂停；不得借此次任务启动第三次个人试局或覆盖第二次证据。
