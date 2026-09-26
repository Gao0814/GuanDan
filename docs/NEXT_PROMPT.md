# Coding Codex 执行 Prompt：个人试局中途停牌的可用性闭环（M0）

## 目标

项目主线仍是来源化掼蛋算法优化，但当前连续个人试局出现“先正常出牌，随后中途长时间不出牌，最后页面未知错误”。在继续开局算法实现之前，先用**一个问题级工作包**消除本项目可证明的停牌缺陷，或取得足以明确下一次停顿边界的低敏证据。不要把此任务拆成多个只产资格报告的阶段；也不要在根因未明时宣称 `platform_error` 必然由 DeepSeek 慢造成。M1 算法 Prompt 已冻结在 `ec5616b:docs/NEXT_PROMPT.md`，M0 放行后再恢复。

## 前提与范围

先阅读根及适用范围内的 `AGENTS.md`、`.agents/skills/` 清单、`docs/PROJECT_STATUS.md` 顶部、`docs/PLAN.md` 当前里程碑、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、`README.md` 和相关生产代码/测试；检查 Git status、diff、HEAD。只修改当前可用性问题直接相关的 connector/DeepSeek 客户端或 Agent、个人启动器以及相应 tests；不修改引擎规则、RAG/开局策略、算法规划 docs、`.env` 或连接 URL/密钥。只暂存自己的文件，完成后提交并报告状态。

当前个人 evidence 仅可**只读**访问 `D:\VsCodeProject\GuanDanManualWorkspace`：先核对归属标记、普通非链接属性、白名单与 `docs/PROJECT_STATUS.md` 登记的大小/hash；不满足即停止证据读取，不寻找替代文件。不得启动个人脚本、connector、建桌、Botzone 浏览器、真实 DeepSeek、preflight 或清理/轮换 workspace；Codex 固定 workspace 不在本任务范围。不要持久化或输出手牌、动作详情、prompt、模型文本、URL、token、密钥或其他玩家暗牌。测试禁用 dotenv，使用合成配置和禁网 fake transport。

已审计、仍须独立核对的低敏事实：该局 7 cycles、6/6/6 request/response/Header，传输失败/超时 0；5 次模型 attempt 均 success，5 次本家合法动作获 ACK 且 source=`model`；已观测 history 共 17 步、最后为本家第 5 次动作，终局尾部可能未观测；最终 `platform_error`。没有第 6 次本家决策记录，也没有逐次阶段耗时或平台错误细节。这不能确定停顿发生在请求到达前、模型处理中、响应/ACK 中，还是其他席位/平台。

## 实施与验收

1. 先沿真实生产调用链检查 poll → request parse → handler/Agent → DeepSeek SSE → response preparation → 下次 poll Header ACK → finished。针对“前五次正常、随后停顿”用禁网可控时钟/transport 复现可疑阻塞、异常吞没或状态丢失路径。若发现确定的本项目缺陷，在**本工作包**修复并加入回归；无证据时不要因猜测修改 URL、重试、模型参数、牌型策略或强制后置动作。
2. 为下一次个人试局增加**显式 opt-in、低敏且及时 flush 的阶段观测**，优先复用个人 `streams/stdout.txt` 而非创建新的私密 artifact。至少能区分：新 play 请求是否到达、是否进入模型、模型是否完成、响应是否准备好、Header 是否获 ACK、最终 finished；按本地单调时钟给出阶段耗时或有界时长桶。只记录固定阶段名、顺序号、低基数 outcome 和时长，严禁 match ID、run token、动作 ID、牌、URL、Header 内容、prompt/reasoning/response、异常正文。默认 Codex connector 行为与当前决策 ID/source 保持不变；个人入口只增加观测，不改变连接端点与既有 80 cycles/1800 秒、零重试配置。
3. 若能从实际平台/协议约束和代码安全取消语义证明一个回合总期限，并证明合法本地 fallback 可在期限内返回，可在同包加入**可配置的超时保护**及禁网慢模型/超时/正常模型回归；不得拍脑袋选一个秒数，也不得把成功模型动作改写为启发式动作。若无法证明，明确保留“时限待定”，不要伪称仅加日志已修好现场故障。
4. 运行相关 Botzone/DeepSeek/个人启动器测试、主规则回归和全量 `unittest discover -q`；检查 `git diff --check`。报告确定修复与未证实假设、离线复现结果、低敏阶段输出样例、最终 Git status。**不要自行运行下一局**：提交后交给规划 Codex 独立复审，再由项目所有者决定何时轮换旧个人证据并做一次人工单局验收。M0 只有正常完局且无未解释的本地停牌，或证据将异常明确隔离到项目外并有可用试测路径时才放行 M1。
