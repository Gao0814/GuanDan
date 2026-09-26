# Coding Codex 执行 Prompt：中途停牌问题级工作包（M0）

## 目标与已证事实

项目主线仍为来源化掼蛋算法优化；当前先处理反复发生的个人试局可用性问题：**起初正常出牌，中途长时间不再出牌，最终 Botzone 显示“未知错误”**。本任务在一个 Coding 工作包内定位本项目可证实的停牌缺陷并修复；若现有证据不足，则使下一次同路径试局能低敏、及时地区分停顿边界。不要把此问题写成连接失败或开局从未出牌，也不要把新增观测本身宣称为故障已修复。M0 放行条件见 `docs/PLAN.md`；放行后执行排队的 `docs/OPENING_ALGORITHM_PROMPT.md`。

规划复核当前个人目录的归属标记和六份运行文件：均为普通非链接，大小及 SHA-256 与 `docs/PROJECT_STATUS.md` 原审计一致。v8 audit 为 7 cycles、6/6/6 request/response/Header、0 transport failure/timeout、1 次 qualified finished；5 次 DeepSeek attempt 均 success、0 fallback，5 条 ACK trace 连续、source 均 `model`，每个选中 ID 在当时原始合法动作中唯一；最终结果为 `platform_error`，没有正常胜负。history 已观测 17 步，最后一条为本家第 5 次动作，终局尾部可能未观测。**没有第六次本家决策，也没有逐阶段时间或平台错误细节**；不能从五次成功或 `platform_error` 推出停顿由模型超时、本地提交、其他席位或平台哪一方触发。

## 执行边界

先读根和适用范围的 `AGENTS.md`、项目 Skills 清单、`README.md`、`CLAUDE.md`、`docs/PROJECT_STATUS.md` 顶部、`docs/PLAN.md` 当前里程碑、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`，再读相关 connector/DeepSeek 客户端、个人启动器与测试，检查 Git status/diff/HEAD。只改此问题直接涉及的 `integrations/botzone/`、`agents/deepseek_client.py` 或必要 Agent、`scripts/` 与对应 tests。不要改 `engine/` 规则、RAG/开局策略、`.env`、URL/密钥或两个 workspace。只暂存并提交本轮自有改动。

`D:\VsCodeProject\GuanDanManualWorkspace` 本轮仅可只读：先核对精确根、归属标记、普通非链接属性、白名单和登记 hash；不符即停止证据读取并报告，不寻找替代路径。**不得启动会轮换它的个人脚本**，也不运行 connector、建桌、真实 DeepSeek、联网 preflight 或清理；不访问 Codex 固定 workspace。测试用合成配置和禁网 transport，禁止读取或输出凭据、连接 URL、match/run 标识、手牌、动作详情、prompt、模型自由文本、Header 内容和异常正文。若项目所有者提供本局页面错误原文/截图或停顿时长，可作为额外证据审阅；没有也继续本工作包。

## 一次性实现与验证

1. 沿当前生产链 `poll → parse → handler/Agent → DeepSeek SSE → response prepared → 下一次 poll 中的 Header ACK → finished` 检查可复现的阻塞、吞错、状态丢失和超时语义。注意代码目前的 `max_wall_seconds` 只在 `cycle()` 之间检查，而 DeepSeek transport 的 `timeout_seconds` 是单次网络读超时，尚无已证实的整次生成期限；这是待验证的潜在长等待机制，**不是本局根因判定**。使用可控时钟、慢/分段 SSE 和禁网 poll/handler 回放覆盖“前五次已 ACK，之后无新本家决策”的边界。只有找到确切本地缺陷时才在同包作最小修复并加回归；不得凭 `platform_error` 猜平台时限、改重试/模型参数、改合法动作或成功模型动作。
2. 为下一次**所有者个人**试局增加显式 opt-in 的低敏阶段观测，默认关闭，不影响 Codex connector。优先写现有个人 `streams/stdout.txt`，若要新文件必须先满足个人 workspace 白名单与 fresh/no-overwrite 规则；不能把阶段事件写入聚合 audit、ACK trace 或普通非 opt-in 日志。用固定枚举、单局内递增序号和单调相对耗时记录 `poll_enter/poll_exit`、新 play 请求到达、模型进入/完成、响应准备、Header 发出、**成功 poll 后确认 ACK**、finished/退出类别；区分“无下一请求”“模型进行中”“响应待 ACK”和“平台已结束”。记录阶段入口时立即 flush，使中途阻塞或进程退出后仍能看到最后边界；用真实个人启动器的合成子进程/禁网测试证明重定向后可见。字段只允许固定阶段名、序号、低基数 outcome 和有界时长，不能有任一标识符、牌、动作 ID、请求/响应、URL、prompt、reasoning、异常文本。记录失败不得改变动作或 ACK 事务。
3. 如定位到整次调用可能无限等待且可用代码/协议证据确定安全的取消与 fallback 语义，可在同包实现有配置依据的整次上限，并测正常、慢分段、取消、合法 fallback 与状态守恒；不能凭空设平台截止秒数，不能把单次读 timeout 当整次截止，也不能制造第二个同时轮询的 connector。若无法安全证明，就保留待定，仅用阶段证据定位下次真实停顿，不把该工作包伪称为已修复。
4. 运行相关 Botzone、DeepSeek 客户端与个人启动器测试、主规则回归、`python -m unittest discover -q`、`git diff --check`。报告：确定事实/根因假设分栏，确切修复或仍待定位的最后阶段，低敏输出例子，默认路径无变化、合法 ID/source/ACK 守恒，命令结果、提交及最终 Git status。**本 Coding 任务不启动下一局**。提交后交规划 Codex 复审；随后由项目所有者决定旧证据何时允许轮换及个人手工试局。一次偶然正常完局或只把错误推给外部，都不自动完成 M0。
