# Coding Codex 执行 Prompt：所有者自操作 Botzone 十局批次脚本

> 项目所有者已明确改优先级：当前先交付可由他自己启动的连续试局脚本，之后 Codex 审计。M2 扩大评估在第 1 槽后停止，本任务**不继续真实 DeepSeek 评测、不发送真实模型请求、不启动 Botzone connector 或建桌**。评测器禁网 `offline-m2` 只是占位名，不能据此声称两版真实模型不同。所有者要求这次实际 Botzone 试测的模型明确为 `deepseek-flash`。

## 使用方式与范围

所有者启动一次脚本，待 Botzone 本地 AI 页面显示“已连接”后，自己在网页逐局建桌并开始；脚本保持**唯一 connector 连续轮询**，不逐局等待按键、不替所有者操作网页。默认最多记录 `10` 个合格完成局，提供有界正整数参数改数量；达到目标后自动退出，用户主动停止或异常时保留已产生证据。固定四人、级牌 `2`、无贡单局。桌面回合时限与 119 秒整次决策期限沿用当前已验证配置，改动不得重置或削弱合法 fallback、ACK 事务、模型成功 ID 原样保留。十局是普通人工采样，不宣称胜率对照或正式预注册实验。

先读适用 `AGENTS.md`、项目 Skills 清单、`README.md`、`CLAUDE.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`，检查 Git status/diff/HEAD；阅读现有 `scripts/run_manual_botzone.ps1`、`scripts/manual_botzone_workspace.psm1`、对应 PowerShell 测试，以及 Botzone CLI、runner、history、decision trace、audit 和 preflight 的代码/测试。`botzone-manual-live` Skill 只管理 Codex 托管的单局，此任务为所有者自操作批次，不要把单局建桌交互硬套进脚本。只改实现本任务必要的 `scripts/`、`integrations/botzone/`、`config.py`、`.env.example`、README 和 tests；规划 docs 由规划 Codex维护。不得读取、修改或打印真实 `.env`、凭据、连接 URL、Header、prompt 或模型自由文本；不碰封板 tag/bundle、个人 `GuanDanManualWorkspace`。

## 固定 workspace 与留证

目标根目录仅为 `D:\VsCodeProject\BotzoneWorkspace`。它目前包含以前的 `audit/`、`state/`、`streams/`、`history.txt`、`decision-trace.json` 及 connection probe；**全部原样保留**。新脚本先验证根目录为精确普通非链接目录且无已运行的项目 connector，再在根下创建唯一、不可覆盖的新批次子目录。批次内的 state、audit、stdout/stderr、逐局 history 和逐局 ACK 后 decision trace 都是新文件；不得清空根、通配删除、自动回收旧证据或复用个人单局启动器的“启动时回收”逻辑。启动前可做零网络配置/路径预检；预检失败无外部副作用时允许原地修正后再启动。脚本应有便于双击运行的入口与 `--no-pause` 非交互用法，但运行中不逐局暂停。

现有 CLI 的 `--stop-after-finished` 能设为 10，但 history 和 decision trace 目前各绑定**一个 match**，不能简单传入同一文件跑十局。为一个持续运行的 connector 增加有界的批次逐局文件写入能力，并保持现有单局文件参数/契约兼容。每局使用非敏感顺序号或等价的不可覆盖命名，不将 match ID、run token、URL、凭据或模型文本写入 trace 文件名或正文；trace 仍只落 ACK 后已确认动作，含原始 canonical 合法动作与低基数 source，不落 pending。逐局完成结果、请求/响应/Header/ACK 守恒和文件归属须能由 Codex 事后独立核对；可同时保留一个批次聚合 audit，但不能只留下不可逐局归属的合计。异常局也应尽量保存已确认动作及固定阶段记录，不能将 `platform_error` 当作普通输赢。若某局证据不可归属，明确标为不完整，不臆造缺失动作。

## 模型与运行控制

新脚本的 connector 子进程明确设置 `DEEPSEEK_MODEL=deepseek-flash`，由 `config.py` 常规读取，并在零网络预检中验证实际组装的模型就是该值；不得只写一条显示文本假称已统一。`config.py` 当前缺省 `deepseek-chat`、`.env.example` 是旧别名 `deepseek-v4-flash`，将这两个**非私密默认/示例**统一为 `deepseek-flash`，并更新依赖默认值的测试；不改真实 `.env`。进程外部环境即使指定其他模型，这个专用脚本仍需显式锁定 `deepseek-flash` 或在预检中拒绝启动。不要把 M2 禁网占位名 `offline-m2` 改成真实模型来掩盖其 Request 绑定缺口；未来成对评估要另修该校验。

脚本启动一个前台 connector，`--agent deepseek`、唯一 run token、stage trace 和 119 秒决策预算沿用现有边界；`--stop-after-finished` 用本次上限。不新增自动重试策略。给 10 局足够但有界的 cycle/墙钟预算，可配置并在脚本帮助中说明；达到上限、传输/协议失败、用户中断或完成目标都以固定低敏类别退出并保留证据。不得在退出后自动重启第二个 connector 追满 10 局。

## 禁网验收与交付

- 用 fake connector/transport 和临时普通目录测试 1 局、默认 10 局、改上限、连续两个不同 match、异常中止与主动停止；证明单 connector 无逐局交互、目标计数、逐局文件独立、旧文件不被覆盖、无第二 connector、无自动回收。单局现有 CLI 与个人启动器回归不变。
- 验证默认 Botzone DeepSeek factory 在合成配置下实际选用 `deepseek-flash`；原始合法 ID、ACK 后 trace、审计/终局分类和低敏约束通过。PowerShell 7 与 Windows PowerShell 5.1 均运行相关脚本测试；跑 Botzone 定向、主规则回归及适用全量 `unittest`，检查 `git diff --check`。测试全部禁网，不运行真实 connector、真实 DeepSeek、Botzone、browser 或依赖私有配置的现场 preflight。
- 交付清楚的启动命令、可改局数参数、何时在页面开始、停止方式、结果目录与 Codex 审计所需的**低敏文件清单**。报告修改、测试、已知限制、commit 和最终 Git status；只提交本轮自有业务/测试/说明文件。**不要替项目所有者开始十局，也不要清理固定 workspace 旧证据。**
