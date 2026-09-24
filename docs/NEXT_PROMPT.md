# 执行 Codex Prompt：一次人工 Botzone DeepSeek 单局

项目所有者已明确授权**仅此一次**人工 Botzone DeepSeek 单局，包括该局可能达到 10 次或更多的真实模型请求；不授权第二桌、额外独立模型探针、批量评测或网页自动建桌。先完整阅读根 `AGENTS.md`、适用的 `.agents/skills/botzone-manual-live/SKILL.md`、`docs/CLEAN_HANDOFF.md` 与 `docs/PROJECT_STATUS.md` 顶部，并只读确认当前 `integrations/botzone/__main__.py` 参数及 audit/trace schema。检查 Git status/diff/HEAD；必须是可解释的 clean 工作树且包含 `f67faf6`，不改仓库代码、tests、RAG、docs 或配置，不创建 commit。

本次固定 profile：四人，级牌 `2`，无需进贡，玩家 1 / seat 0，agent=`deepseek`；建桌 seed=`47005`。**不要在页面确认“已连接”之前向项目所有者发送含 seed 的建桌配置。**该 seed 从执行 Codex 首次发给项目所有者时起视为已使用，不可重用。网页建桌、配置和点击开始均由项目所有者手动完成；Codex 仅作 best-effort 只读检查，不点击或提交页面。

唯一工作根目录为 `D:\VsCodeProject\BotzoneWorkspace`。起始 inventory 必须精确为普通非链接根目录及空的普通非链接 `audit`、`state`、`streams` 三目录，文件数 0；`D:\VsCodeProject` 直属 `Botzone*` 集合只能是 `BotzoneWorkspace`。确认无可归属的项目 connector，目标 `audit/completion-audit.json`、`decision-trace.json`、`history.txt`、`streams/stdout.txt`、`streams/stderr.txt` 均不存在。任何未知文件、链接、目录或无法解释的进程使任务暂停，不能在 live 任务中清理旧 evidence。

准备阶段先在内存或独立系统临时位置核对 shell、参数、路径、32 位小写十六进制 run token 与输出捕获方式；不要创建其他顶层 `Botzone*` 目录。使用项目解释器执行同一 agent/state 配置的**零网络** `python -m integrations.botzone --preflight-only`，以返回 `preflight_ready` 为就绪依据；不得手动读取或输出 `.env`、URL、key、Cookie、Header 或 token。仅在本次 connector 进程中设置 `DEEPSEEK_MAX_RETRIES=0`，不要更改持久配置。外部建桌、真实请求和 seed 告知均尚未发生时，shell/路径/preflight 编排错误可原地诊断修正，不当作一次失败对局。

就绪后以受监控的唯一前台 session 启动 `python -m integrations.botzone`：`--agent deepseek`、`--state-dir D:\VsCodeProject\BotzoneWorkspace\state`、`--max-cycles 80`、`--max-wall-seconds 1800`、`--stop-after-finished 1`、`--audit-file D:\VsCodeProject\BotzoneWorkspace\audit\completion-audit.json`、`--history-file D:\VsCodeProject\BotzoneWorkspace\history.txt`、`--decision-trace-file D:\VsCodeProject\BotzoneWorkspace\decision-trace.json`、`--run-token` 为本次新生成的有效值。只在固定 `streams` 目录捕获 stdout/stderr，不在普通日志输出手牌、动作明细、prompt、模型响应或敏感连接信息。不要使用第二个 connector，也不要为凑足策略场景延长或重开对局。

持续确认 connector 存活与 Botzone 本地 AI 页面确实显示“已连接”；进程存活或长轮询 timeout 不是连接证明。页面不可可靠读取时可接受项目所有者的明确连接确认。**确认已连接后**才告诉项目所有者 seed `47005`、玩家 1/seat 0、四人、级牌 `2`、无需进贡、`deepseek`，请其建一桌并停在开始前；可靠读回若有不一致，指出字段并等待修正，否则接受其明确就绪确认。随后复述配置，邀请其只点击一次开始。开始后立即监测首个请求、state、history、trace/audit 指标；一旦证明确已进入对局，不再索要第二次“已开始”回复。活跃期间至少每分钟给低敏进度。

达到一个 qualified finish、不可恢复的开局后故障或 1800 秒墙钟上限即停止，**不得开第二桌**。非致命 transport 事件如未破坏完成和 ACK 守恒，只如实记录，不自动重赛。发现代码缺陷则保留证据，交回规划 Codex 另立任务；live 中不得修改仓库或清理 workspace。

结束后按当前 schema 审核 connector exit 与残留进程、audit 的 agent/provenance、request/response/Header/finish/transport/decision/model/source/fallback 守恒、history 和 ACK trace 状态、连续唯一 ACK 与所选 canonical action ID 绑定、pending 状态及 finished tombstone（若生成）与 audit provenance 一致性。只报告低敏聚合与保留 evidence 的精确路径、大小、SHA-256，不输出正文、手牌、动作详情、prompt、模型自由文本、URL、密钥或 token。区分平台结局有效性与决策证据有效性；单局胜负不证明策略质量或胜率。确认 Git HEAD/status 未变，所有 evidence 留在固定 workspace，报告任何真实模型请求/重试/fallback 数及实际停止原因，然后结束任务等待规划复审。
