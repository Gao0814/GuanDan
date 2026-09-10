# 给 Coding Codex 的下一任务 Prompt

你负责执行一次人工Botzone单局 `deepseek` 决策证据采样。你同时负责命令执行、持续监测和与项目所有者交互，但本任务不修改仓库代码、测试、配置或文档，不创建Git commit，不进行多局或容量实验。

## 【项目长期约束】

开始前完整读取并遵守仓库根目录及适用范围内的 `AGENTS.md`，并阅读 `docs/CLEAN_HANDOFF.md`。以当前仓库、Git状态和实际只读验证为准，不把历史报告自动当作现场事实。

本项目当前Botzone固定profile是四人、单局、级牌 `2`、无需进贡。跨级牌、贡还、多局升级和百局/16局capacity不属于本任务。网页建桌、填写配置和点击开始均由项目所有者手工完成；你只做best-effort只读监督，不能替项目所有者点击或输入。

## 【当前项目状态】

- 已验收的acknowledged decision trace实现检查点为 `045fb75 feat: record acknowledged Botzone decisions`；规划Codex独立运行Botzone定向88项、主规则39项、全量707项通过。
- decision trace默认关闭；显式启用后只在Header ack后保存本家当时的完整公开observation、逐字段一致的原始canonical legal actions、最终原始action ID/action与低基数source。
- seed `47002`旧evidence已经审计并移入Windows回收站。2026-09-10规划Codex独立复核：`D:\VsCodeProject`下唯一 `Botzone*` 顶层目录是普通非链接目录 `D:\VsCodeProject\BotzoneWorkspace`；其递归内容精确为三个空的普通非链接目录 `audit/`、`state/`、`streams/`；项目connector进程为0；Git clean。
- 下一局预留seed为 `47003`，但在页面明确确认本地AI“已连接”之前，不得向项目所有者提示该seed，也不得让项目所有者创建目标桌。seed从你首次把它发给项目所有者时才视为已使用。

## 【本次任务目标】

运行唯一一局 `deepseek` 人工Botzone对局，同时生成并保留：

```text
D:\VsCodeProject\BotzoneWorkspace\audit\completion-audit.json
D:\VsCodeProject\BotzoneWorkspace\history.txt
D:\VsCodeProject\BotzoneWorkspace\decision-trace.json
D:\VsCodeProject\BotzoneWorkspace\state\<唯一session或finished tombstone>.json
D:\VsCodeProject\BotzoneWorkspace\streams\stdout.txt
D:\VsCodeProject\BotzoneWorkspace\streams\stderr.txt
```

本局用于取得可重建的真实决策点，不用于证明DeepSeek胜率、与RuleBased比较或追求某个守卫必须触发。只运行一桌；无论输赢、source分布或条件守卫是否触发，都不得为追样本创建第二桌。

## 【执行前检查范围】

在任何写入、preflight或connector启动前：

1. 记录当前HEAD并确认 `git status --short` 为空；若不为空，停止且不修改任何内容。
2. 确认 `D:\VsCodeProject` 下以 `Botzone` 开头的直属目录集合精确为 `BotzoneWorkspace`。
3. 确认workspace根及 `audit/`、`state/`、`streams/` 均为普通非链接目录，递归inventory精确只有这三个空目录。
4. 确认没有正在运行且可安全归属于本项目Botzone connector的进程；不得输出进程命令行、URL、token或敏感参数。
5. 只读确认当前CLI支持 `--agent deepseek`、`--history-file`、`--decision-trace-file`、`--run-token`、`--audit-file` 和 `--preflight-only`。不要重复运行单元测试。

若纯本地命令解析、路径、随机token生成、PowerShell参数或捕获方式有错误，在workspace尚未写入、connector未启动、页面未建桌且seed未提示的情况下，它只是可原地修正的qualification问题；允许在系统临时scratch中修正并重试，不得直接结束任务或把它升级为正式实验失败。

## 【固定运行配置】

- Agent：精确为 `deepseek`。
- 本家：玩家1 / seat 0。
- 当前级牌：`2`。
- 需要进贡：`否`。
- 单局seed：`47003`，只能在页面连接准入通过后向项目所有者提示一次。
- state目录：`D:\VsCodeProject\BotzoneWorkspace\state`。
- audit：`D:\VsCodeProject\BotzoneWorkspace\audit\completion-audit.json`。
- history：`D:\VsCodeProject\BotzoneWorkspace\history.txt`。
- decision trace：`D:\VsCodeProject\BotzoneWorkspace\decision-trace.json`。
- stdout/stderr：固定 `streams` 目录下的两个文件。
- `timeout-seconds=120`、`max-cycles=100`、`max-wall-seconds=3600`、`stop-after-finished=1`。
- 为本局生成一个新的随机32位小写十六进制run token，只传入进程；不得在对话、日志摘要或报告中输出token。

不要人工读取或输出 `.env`、连接URL、API key、Cookie或Header；允许项目现有配置加载路径在preflight/live中正常使用这些配置。

## 【执行顺序】

1. 先用项目 `.venv\Scripts\python.exe` 执行一次 `--agent deepseek --preflight-only` 的零网络组合预检。要求exit 0、stdout唯一有效行 `preflight_ready`、stderr为空、state仍为空。preflight失败时先按固定低敏分类诊断；如果是无外部副作用的编排错误，允许原地修正。不得调用DeepSeek模型或Botzone poll来完成preflight。
2. 用 `integrations.botzone.live_launcher` 和上述固定参数启动唯一、持续的前台connector，取得可继续等待/轮询的进程session。不得仅启动一个会被工具提前终止的临时子进程。
3. connector启动后，要求项目所有者刷新/检查Botzone本地AI页面。若你能可靠读取已打开的Edge页面，只做只读核对；不能可靠读取时，等待项目所有者明确回复“已连接”。connector进程存活、idle timeout或尚无state都不能替代页面“已连接”证据。
4. 页面仍显示“未连接”时，保持connector运行并协助诊断连接；不要提示seed、不要让项目所有者建桌、不要提前结束任务。若必须停止connector修正连接配置，只能在0 request、0 state、无history/trace、未提示seed、未建桌的条件下停止并清理由本次启动产生的空audit/streams，然后原地重启；这不是live失败。
5. 页面确认“已连接”后，才向项目所有者明确发送并复述：seed `47003`、玩家1、级牌 `2`、需要进贡 `否`、Agent为 `deepseek`。请项目所有者手工创建唯一桌、完成配置并停在点击开始前。发送该消息后seed视为已使用，不得复用。
6. 对配置进行best-effort只读核对。若页面明确显示seed、seat、级牌或贡牌配置不匹配，指出具体字段并拒绝接受“已开始”，等待项目所有者修正。若页面无法可靠读取，接受项目所有者明确的“配置完成/准备好了”作为fallback，不得因监督失败终止任务。
7. 配置确认后，再次复述四项配置并明确提示项目所有者只点击一次“开始游戏！”。随后立即监测connector进程、首个request、state、history和decision trace；一旦这些证据表明对局已经开始，不再要求项目所有者额外回复“已开始”。
8. 对局进行中持续等待并做低敏监督。每隔不超过60秒给项目所有者简短状态；不要输出本家手牌、完整observation/legal actions、URL、token、模型文本或trace正文。不要因为暂时没有新请求、页面只读失败或项目所有者没有回复就直接结束。
9. 等待唯一对局到qualified finished、明确不可恢复的connector退出/协议失败，或3600秒上限。结束后不得清理、改写、移动或回收任何evidence，不得启动第二个connector或第二桌。

## 【重要不变量】

- live期间仓库冻结；发现代码缺陷只保留evidence并报告，不能现场改代码后继续同一局。
- 同时最多一个项目connector和一个目标桌。
- Agent只能从原始canonical legal actions返回合法action ID；不得绕过engine或手工替换动作。
- pending未ack的本家动作不得进入decision trace；重发、重启、重复ack/replay不得形成重复decision。
- history和decision trace是私有仓库外evidence。普通输出与audit不得包含本家手牌、完整observation/legal actions、trace绑定ID、match ID、URL、token、Header、Cookie、密钥、prompt、模型响应/reasoning、异常正文或自由文本。
- 固定级牌2、无贡、单局是已接受范围，不得列为剩余风险。
- 可恢复的非致命 `http_error` 若未阻止最终完成或破坏request/response/Header及ack守恒，只记录为传输观察，不得把整局证据自动作废或重开。

## 【完成后验证】

对局结束后仅做低敏一致性检查，不输出私有文件正文：

1. connector已退出且无残留项目connector；记录exit code与停止原因。
2. audit能解析，`agent_mode=deepseek`，run归属与唯一state/tombstone一致；request、response、Header、finished、transport、model/source/fallback计数满足现有schema守恒。
3. `history.txt` 存在、状态为 `history=ok`、UTF-8/LF，包含标题、本家座位/级牌、已观察步骤和终局区；如尾部不完整，保留 `terminal_tail_may_be_unobserved`，不得声称完整裁判牌谱。
4. `decision-trace.json` 存在、状态为 `decision_trace=ok`；只报告schema/version、decision数量、source聚合、与audit决策数是否一致，以及顺序号/action ID/selected action映射是否逐项有效。不得输出binding或任何决策正文。
5. 五类目标evidence路径均保留；报告每个文件的相对路径、bytes和SHA-256，但state文件名与任何敏感值应脱敏。
6. Git HEAD与 `git status --short` 前后一致且为空；未修改仓库。

如果对局正常完成且上述证据守恒，固定判定为：

```text
botzone_deepseek_decision_trace_sample_completed
```

如果已开始但未正常完成，使用最接近实际边界的低敏判定，保留全部evidence并停止；不要重试。若页面一直未连接且seed从未提示，报告pre-seed连接阻塞并继续等待项目所有者指示，不得声称seed已消耗或创建目标桌。

## 【完成标准】

- 最多一局、一个connector、一个目标桌；
- 页面已连接后才提示并使用seed `47003`；
- 对局完成时history与decision trace均为 `ok`，audit/state/streams归属与计数守恒；
- 未运行容量评测、未修改仓库、未清理现场；
- 一局结果只作为后续策略诊断证据，不直接升级为胜率结论。

## 【执行后的报告要求】

最终报告必须包含：

1. 固定低敏判定与是否完成对局；
2. preflight、页面连接准入、seed提示、配置核对和开始监测的实际顺序；
3. connector启动次数、最大并发数、cycles及request/response/Header/finished/transport聚合；
4. Agent/model attempts/outcomes、fallback和全部低基数decision source计数；
5. history与decision trace状态、decision数量及其与audit的守恒结果；
6. evidence相对路径、bytes和SHA-256，不输出私有正文或敏感标识；
7. Git前后状态、残留connector、是否修改仓库、是否启动第二桌；
8. 当前范围内真实存在的剩余风险；固定级牌2、无贡、单局不得写成风险。

不要在本任务内分析整局并修改算法。把完整evidence原样保留，交回项目规划Codex做独立复审和下一步规划。
