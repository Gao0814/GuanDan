# Coding Codex 执行 Prompt：所有者自启的连续十局 Botzone 脚本

## 目标与操作边界

交付一个供项目所有者**亲自启动**的 Windows 脚本：启动一次后维持一个 DeepSeek connector 连续轮询；所有者在 Botzone 页面逐局手工建桌、配置和开始，脚本不逐局暂停或等待按键，默认最多记录 10 个已确认的四人无贡完局（含平台错误局），局数可调整。Codex 本任务只做禁网实现和验证，**不启动真实 connector、不操作 Botzone 页面、不发真实 DeepSeek 请求**。脚本交付后由所有者决定何时试测，试测结果再交规划 Codex 只读审计。此任务是现场测试工具支线，不改算法、动作选择、ACK 状态机或已停止的 M2 32 槽评测器。

先读适用 `AGENTS.md`、项目 Skills 清单、`README.md`、`CLAUDE.md`、`docs/PROJECT_STATUS.md` 顶部、`docs/PLAN.md` 顶部、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`，核对 Git status/diff/HEAD。重点读 `scripts/run_manual_botzone.cmd/.ps1`、`scripts/manual_botzone_workspace.psm1`、`integrations/botzone/__main__.py`、`runner.py`、`connector.py`、`history.py`、`decision_trace.py`、`result_observability.py`、`stage_trace.py`、`config.py` 及对应测试。项目单局 Botzone live Skill 是 Codex 监督现场时才适用；本任务不做现场执行，也不触发固定 workspace 回收 Skill。

## 同一工作包内实现

1. 在 `scripts/` 提供清楚的一条命令入口和可选局数参数（默认 `10`，正整数）。沿用仓库 Python/配置路径，启动**一个前台、持续运行**的 `--agent deepseek` connector；使用 `--stop-after-finished` 实现目标，给 `--max-cycles`/`--max-wall-seconds` 足以覆盖人工连续十局的可调上限，达到局数或所有者手动停止后退出并保留已产生的证据。不要自动建桌、控制浏览器、逐局询问或逐局重启 connector。保持既有 119 秒决策期限、120 秒牌桌校验口径；不要借脚本改动模型超时、fallback、合法动作或 ACK 事务。
2. 本任务的证据根目录固定为 `D:\VsCodeProject\BotzoneWorkspace`。只创建一个全新、不与已有名字冲突的批次子目录，所有 state/audit/streams 和新记录均在其中；不读取、移动、清空或覆盖根目录既有文件及其他批次，也不触碰 `D:\VsCodeProject\GuanDanManualWorkspace`。拒绝链接/路径越界和已占用输出；若准备或配置预检失败，保留现场旧证据并给固定低敏错误类别。当前任务不做旧证据回收。
3. 脚本子进程显式使用 `DEEPSEEK_MODEL=deepseek-flash`，由 `config.py` 读取；不改 `.env`、不回显模型请求、密钥、连接 URL、prompt 或响应正文。用零网络预检确认同一解释器、工作目录和必要配置可用，再启动连接器。启用现有 `--stage-trace`，让所有者遇到中途停牌时可保留末尾阶段事件；`platform_error` 只能按观察分类，不预断为模型超时。
4. 让 Codex 能审计十局的**最小充分结果**：每个已确认完局有稳定的批次内序号和低敏结果分类（胜、负、平台错误、无效结果等），并保留现有总 audit 的请求/响应/Header 计数、模型结果与终局聚合；ACK 边界由 stage trace 的 `response_acknowledged` 观察，不能把 Header 数当作 ACK 数。结果不得包含 match ID、URL、密钥或自由文本。现有 `history.txt` 与 `decision-trace.json` writer 都只绑定单局；不能把它们直接指向同一文件记录十局。可以有界实现逐局隔离的可选文件，也可以在此批次关闭它们并明确告知审计范围；**完整逐局牌谱/trace 扩建不是交付门槛**。记录失败不得悄悄改变动作或 ACK，且最终报告要能区分记录不完整与正常完局。

## 禁网验收与交付

- 用 fake transport/进程调用验证至少三局连续序列（胜、负、`platform_error` 或同等异常分类）、默认与自定义局数、达到目标自动退出、所有者手动停止保留已有结果、idle poll 不计成一局、旧证据不覆盖、无逐局暂停、模型名在子进程统一为 `deepseek-flash`。若改动 connector 记录边界，验证多局交错或重复终局不会双计，并保持 ACK 后记录契约；不引入正式实验的 manifest、逐字节资格或任一普通准备错误整批作废门槛。
- 给所有者一条实际可复制的启动命令、如何调整局数、何处查看本批次目录，以及页面显示已连接后由其手工逐局操作的简短说明。不要在交付前要求所有者开局或提供私密配置值。
- 运行直接相关测试、主规则回归和受影响的全量测试；`git diff --check`。只提交本轮自有的脚本、必要的 Botzone 低敏记录实现与 tests；不改 `engine/`、算法策略、`.env`、封板标签/bundle、规划 docs 或旧 evidence。报告禁网测试、真实 Botzone/DeepSeek 请求数（本任务均为 `0`）、commit、最终 Git status 与实际限制。
