# 规划 Codex 执行 Prompt：下一次个人试局后复审中途停牌（M0）

## 触发条件与目标

仅在项目所有者**明确允许旧个人证据轮换**、亲自使用现有个人启动器完成一局，并报告新局结束或异常后执行。本 Prompt 不授权 Codex 启动个人脚本、连接 Botzone、建桌、清理或轮换证据。所有者尚未决定时保持 `D:\VsCodeProject\GuanDanManualWorkspace` 原样，等待决定，不拿旧局重复当作新阶段证据。

任务是在 M0 同一问题级阶段复审新局是否再次出现“先正常出牌，中途长时间不出牌，最后未知错误”，利用 `f5fb88a` 新增的低敏阶段事件定位本地可观察边界，并决定：继续 M0 的哪项具体修复/诊断，或已满足放行条件。旧局五次 ACK 和 `platform_error` 只证明当时已完成的动作与终局分类，不证明模型超时。模型整次生成无总期限是潜在机制，不是既定根因。

## 开始前

读取适用 `AGENTS.md`、项目 Skills 清单、`docs/PROJECT_STATUS.md` 顶部、`docs/PLAN.md` M0、`docs/CLEAN_HANDOFF.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`，检查 Git status/diff/HEAD。规划 Codex 只做只读证据复审与必要 docs 更新，不改业务代码或 tests；本任务不访问或清理 `D:\VsCodeProject\BotzoneWorkspace`。个人目录先核对精确根、归属标记、普通非链接属性、白名单、无运行中 connector；不符即停止读取并报告。只读取本次低敏阶段、audit 和必要的 ACK/终局一致性字段，不打印或持久化手牌、动作详情、模型文本、prompt、标识符、凭据、连接 URL、Header、异常正文。若异常，保留整局证据，禁止再次启动个人脚本。

## 复审步骤

1. 记录所有者描述的先出牌、停顿起点/大致时长、页面“未知错误”或正常终局；可接受所有者提供的截图或原文，但不要从 `platform_error` 倒推页面细节。核对本次 evidence 的低敏大小/hash、stage-trace 格式与递增序号、单调相对时间、audit/finished/ACK trace 计数与原始合法 ID/source 守恒。终局 history 只能按其实际完整性标志使用。
2. 将最后一个已确认本家动作后的事件按时间线排列。`model_enter` 后没有 `model_complete` 只能说明模型调用在最后观测点尚未完成；`response_waiting_ack` 后没有 `poll_returned` 说明下一次 poll 尚未返回；有 `poll_returned` 而没有 `response_acknowledged` 则检查本地确认边界。`poll_exit=idle` 表示一次成功 poll 没有新请求。`response_header_emitted` 只代表本地将 Header 交给 poll，不代表平台 ACK。任何缺失事件都应同时核对进程退出、日志写入上限/失败和终局记录，不能单凭最后一行认定远端根因。
3. 若再次停牌，列出已证实最后边界与尚待区分的假设；只有出现可复现的本地缺陷或足够确定的协议/时限依据，才在同一 M0 阶段派最小 Coding 修复与回归，不猜测平台时限、不盲改超时/重试/动作。若是正常完局，核对整局阶段证据与 ACK 守恒，记为一次验证，不单凭这一局放行。
4. 根因未知时，M0 放行至少需要**两次分开的正常完整个人试局**，每次有可用阶段证据且无同类停顿，并由规划复审确认试测链路足以支持算法试测。第一局复审完成后，只有项目所有者再次决定允许轮换其证据，才进行第二局。若后续查明并修复确定本地根因，则按 `docs/PLAN.md` 的修复后正常完局门槛复审。M0 放行后直接执行 `docs/OPENING_ALGORITHM_PROMPT.md` 的 M1 算法任务，之后做 M2 效果复审。

## 输出

在 `docs/PROJECT_STATUS.md` 和 `docs/PLAN.md` 更新已证实事实、未证实假设、M0 判定与下一动作；必要时同步 `docs/CLEAN_HANDOFF.md` 和本 Prompt。只提交本轮自有规划文档并报告 commit、最终 Git status、实际验证命令与当前范围内剩余风险。若缺少新局或所有者尚未允许旧证据轮换，只记录等待状态，不执行任何会覆盖个人目录的操作。
