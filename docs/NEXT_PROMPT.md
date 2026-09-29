# 连续人工试局：连接器生命周期与跨启动局面恢复

先读 `AGENTS.md`、适用项目 Skills、`docs/CLEAN_HANDOFF.md`、`docs/PLAN.md` 顶部、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`；核对 Git status/HEAD、Botzone connector、runner、session、manual batch 及现有测试。只提交本任务业务代码/tests。所有者正在自行操作真实 Botzone；不得启停其页面或 connector，不修改、轮换或清理 `D:\VsCodeProject\BotzoneWorkspace` 中的现场文件，不读取 `.env` 或输出连接 URL/凭据。必要的第 28–33 局 evidence 只读检查。

## 已确认的故障链与边界

最新检查的六个**逐局留证目录**为第 28–33 局，不据此推断平台实际只运行了六局。所有者给出的 Botzone 页面截图显示最近四个“已完成”结果对应第 28、29、30、32 局，按平台结果为本队 1 胜 3 负；第 31、33 局显示“中止”。其中第 29、30、32 局有 connector 的四人终局确认，本家分别负、负、胜，52 次本家动作均获 ACK；第 28 局虽在页面有结果，首手 `model_enter` 后旧运行中断，本家无 ACK，后来新运行只收到四人终局，故逐局留证标 `finished_unconfirmed`，不能把该结果算作完整算法对局。第 31 局同样在首手模型等待后中断，无 ACK；第 33 局一手模型动作获 ACK，随后平台 `aborted`。两次旧运行的 stage trace 无正常退出标记且 audit 为空；旧进程为何结束未知，不得归因为模型超时、用户关窗或网络故障。

第 31 局时间段的新运行 `run-20260929T155339Z-153eba47b32a805b` 在首个 play 请求报告 `play_without_state`，runner 以 `diagnostic_failure` 退出；失败请求的 match 身份未记录，不能把它精确绑定第 31 局。当前每次启动创建新 state 目录及 run token，跨启动的旧局不会自然拥有可用会话状态；这是已验证的**新进程无法接续已有局且单局缺状态导致全局停机**机制。第 29、30 局运行中有 60 次约 30 秒的长轮询 timeout，均立即继续，没有记录 transport failure；正常长轮询 timeout 不等于断网。当前 `ConnectorRunner` 在 `cycle()` 内同步等待模型，模型等待期间没有下一次 poll。网页“等待重连”的判定规则和旧进程消失原因尚无直接证据。

## 目标

完成一个问题级可用性修复，使所有者启动的连续试局在正常 idle、模型思考、单局状态异常和意外子进程退出后，尽可能保持**单个** connector 服务下一局。重点解决跨启动旧局状态丢失与 `play_without_state` 使整个连接器退出；若可由经过验证的持久状态安全恢复旧局，应恢复其原会话及 pending/ACK 边界；无法证明可恢复时，应把该局明确标成未确认并隔离，不能凭空构造动作或让它持续阻断其他新局。审查同步模型等待造成的无 poll 窗口，基于 Botzone 长轮询协议选择安全的服务连续性办法；不要为了页面状态文字盲目并发 GET、重复处理 play 或发送未确认 Header。保留 119 秒模型决策期限及现有回退，不改策略选择。

允许在同一工作包内调整启动器对子进程的监督与重启、会话持久化/恢复、runner 的逐局故障隔离和必要协议调度；由仓库实际机制决定最小一致实现。不能简单删除 `run_token` 保护、共用未经核验的旧 state、吞掉未知错误并无限空转，也不能停止所有者当前进程做现场复现。旧 evidence 和最近 10 局滚动记录保持可审计且不覆盖；普通 30 秒 idle timeout 仍可继续轮询。

## 验收

- 禁网 fake transport 模拟 idle 超时、长模型等待、旧进程在模型调用中途消失、启动器/connector 新进程收到旧局 play、重复请求及 pending Header 的 ACK。证明只允许一个活跃 connector；可恢复局的状态/动作/ACK 只提交一次，不能恢复的旧局不会使下一场新四人局停机。若无法安全并发 poll，给出可复算的协议/事务原因，仍须交付跨启动与逐局隔离改进。
- 对第 28、31、33 局仅使用低敏阶段事件作反例：不能把 `model_enter` 后无退出标记或 `aborted` 自动分类为 DeepSeek timeout；不能把正常 long-poll timeout 算成 transport failure。新留证须能区分子进程退出、旧局不可恢复、正常 timeout 和已确认 ACK，不持久化异常正文或凭据。
- 保留 canonical 原始合法 ID、成功模型不后置改牌、Botzone session pending/ACK 事务、单 connector、所有者网页操作权、逐局目录/最近 10 局滚动语义。运行定向、主规则与适用全量测试及 `git diff --check`。真实 Botzone、connector、浏览器和 DeepSeek 请求均不由 Coding 执行；最终只报告禁网证据支持的修复范围与仍需所有者现场验收的部分。

提交前反补丁自检：检查是否只是给第 31 局、某个 run token 或某条错误字符串开特例；模拟另一个未列出的旧局在相同生命周期下是否自然恢复或隔离。只暂存自有业务代码/tests，提交并报告最终 Git status。
