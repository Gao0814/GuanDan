# 下一项 Coding 任务：连续人工试局按局留证与最近十局实物轮换

你是 Coding Codex。先读 `AGENTS.md` 最新 Botzone 条款、`README.md`、`CLAUDE.md`、`docs/PROJECT_STATUS.md` 和 `docs/PLAN.md` 顶部、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`，核对 Git status/diff/HEAD；检查 `.agents/skills`，仅在任务真涉及 live 或旧 workspace 清理时按适用 Skill 执行。本任务**只做禁网代码和测试**，不启动 connector/Botzone/浏览器、不发真实 DeepSeek、不读取 `.env` 或现有现场证据正文，不触碰正在运行的旧批次。只提交自有业务代码和测试，不混入规划文档或未知修改。

## 已证实缺口与目标

`run_manual_botzone_batch.cmd` 每次启动建一个 UTC `manual-batch-*` 运行目录；`--games 10` 仅让 `manual-batch-records/recent-games.json` 保留十条**结果摘要**，历史运行目录不轮换。`state/<hash>.json` 是内部会话，不是用户可读的游戏记录。批次入口未启用单场 history/decision trace，也没保存模型请求，因此过去局的具体动作不能由现有证据还原。所有者要求：一个前台连接器持续运行、页面操作仍由本人完成；每一局有一个可按**本地日期时间**找到的完整诊断目录，异常局同样留痕；跨脚本重启实物只保留最近 N 局，默认 10，可用现有 `--games N` 调整。按所有者最新确认，保存每次实际发送给模型的**完整请求 body**，以及可复盘的逐动作记录。修复留证能力，不改 AI 选牌、合法动作、DeepSeek 时限或 ACK 协议。

## 实现范围

1. 在固定 `D:\VsCodeProject\BotzoneWorkspace` 下建立用户可查的 `games/<本地时间>_<单调局序号>/`，Windows 文件名用如 `2026_9_28_20-17-46_000017`，另记 UTC 和时区；同秒并发/重启不得覆盖。每局从首次可信 deal/play 绑定到唯一目录，局间复用同一个持续 poll 的 connector，不新建可见 `manual-batch-*` 顶层运行目录。内部状态、audit、streams 可留在独立的版本化运行区；内部哈希名不得当作逐局命名或结果证据。逐局目录提供一眼能查的时间、序号、终局/中断状态和对应诊断文件，README 写清入口与路径。
2. 每局记录 Botzone **实际观察到**的公开出牌/pass 顺序、本家初始/当前手牌和本家决策时的公开 observation、原始 canonical legal actions、实际展示候选及推荐/关系引用、所选原始 ID/action 与固定 source、模型/本地公式/fallback/timeout 阶段、响应待 ACK/已 ACK/未确认、终局平台结果。每次 DeepSeek 调用在该局私有文件保存**实际发送的完整 JSON request body**（包括模型名/messages/候选正文和非敏感生成参数，保持字节或字段值等价）及摘要/顺序号；不保存 Authorization、API Key、Cookie、连接 URL、Header、原始模型回复/reasoning、异常正文。没有模型调用要明确记录其决策 source。若 Botzone 公开历史尾部缺失，标注“仅 connector 已观察”，不能冒充完整裁判牌谱或推断其他玩家暗牌。
3. 记录链区分 `request_prepared`、`model_enter/complete/timeout`、动作已算出、Header 待发、后续 poll 返回与 ACK 确认；未收到 ACK、运行崩溃或平台中止时保留当前局及最后边界，而不把 pending 动作写成已出牌。证据写入失败应显式显示 `evidence_incomplete` 和安全类别，不改变出牌、响应或 ACK 事务。不要把手牌、完整 prompt、模型自由文本或凭据写到 stdout、聚合 audit、Git 或普通日志。直接 CLI 和个人轻量试局的通用 trace 默认行为不变；新增完整请求仅限这条所有者明确授权的固定 workspace 连续批次路径。
4. 将 `--games N` 实现为**最近 N 个逐局目录**的容量，不因第 N 局停机。第 N+1 局安全落盘后按单调局序号移出最早一局，跨启动继续，异常/未确认局计数；目录/索引必须一致。滚动只可作用于新版精确归属、普通非链接、schema 校验通过且非运行/审计保留的逐局目录；遇到未知项、链接、损坏或写入失败时停止轮换并报告，不扩大为通配删除。旧 `manual-batch-*` 原样保留，不能因新容量清掉；可从可信的旧 `recent-games.json` 导入当前十条低敏结果为 `summary_only`，有时间才用真实本地时间命名，绝不能虚构过去缺失的动作或模型请求。旧目录之后由规划单独审计和按 workspace recycle 规则处理；正在运行的旧进程只能由所有者自行停止，新代码在其下一次启动后生效。

## 验收

- 禁网 fake transport 连续至少 11 局、跨两次启动，验证真实逐局目录按本地时间命名且碰撞安全，容量 10 只保留最新十局；旧 `manual-batch-*` 和未知文件逐字节不变，异常/未确认局保留且按局计数。进程持续跨 idle/局间，只有用户中止或明确运行上限退出。
- 在多动作合法局面检查每局：Botzone 已观察动作与本家 ACK 后动作可区分、观察/原始候选/最终候选/选择 ID 完整绑定；请求文件与 fake transport 实际收到的 body 等价；模型 timeout、fallback、无请求和中途停止分别留有明确最后阶段。测试不得打印请求正文、手牌或密钥。必要时调整单场 writer 为安全的每 match 路由，不要把多个 match 混在一个 trace。
- 路径、链接、损坏/写入失败和滚动中断都不得删除未知或正在使用的 evidence；小范围定向与主规则测试通过，相关 Botzone/DeepSeek 公共路径运行全量 `unittest`，运行中旧 connector 导致的进程探测测试冲突要单独说明，不停止它来追求绿灯。`git diff --check` 通过。报告新目录示例、留证字段、不能恢复的旧证据、测试/限制、commit 和最终 Git status。完成后**不代替所有者启动真实脚本或新桌**。
