# Coding Codex 执行 Prompt

任务：H3-A12——只读复盘已审计的 seed `47004` 单局 ACK decision trace，定位历史三处观察及其余决策在当前模型前链路中的状态。先核对 Git status、diff、HEAD 和最近提交，确认包含 H3-A11 `e2b5e435d7328fa5d847d8931c5d7053137d5e6a`；阅读适用 `AGENTS.md`、检查 `.agents/skills/`，阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md` 及相关 trace、Botzone agent factory、DeepSeek 模型前投影代码和测试。本任务不改业务代码、测试、RAG、docs 或配置，不创建 commit。

## 证据前提与边界

1. 固定 workspace 为 `D:\VsCodeProject\BotzoneWorkspace`。先只读核对 root、`audit/state/streams`、六份文件均为普通非链接对象，精确 inventory 与 `docs/PROJECT_STATUS.md` 中 seed `47004` 六项 bytes/SHA-256 全部一致；至少包含 `decision-trace.json` 261941 bytes / `87607a11e7dc1acf41e74c86c34767012cd734130e891b7c2fc807e44618ee00`、`history.txt` 11426 bytes / `28864f2e44243085860e6bbbaa180b4fc7b663bc5825cc19416bb4387f23f7c8`、`audit/completion-audit.json` 781 bytes / `018a95e4c6f286bb93f870d2c56baa6c05e6bde72b458f1a7dffdee61a0a88a4`。任一前提不符则在读取正文前停止，不猜测替代文件、不修复或清理 evidence。
2. 只在内存中读取上述历史证据；验证 trace schema、24 条 ACK 序号/唯一性、observation 内外完整 canonical actions 一致、原始 selected ID/action/source 合法，并核对 audit 的请求/决策/source 守恒。不得输出完整手牌、逐动作牌面、原始 action ID、prompt、模型文本、连接 URL、token、凭据、match/binding 标识或异常正文；不得复制、持久化、改写或删除任何 evidence，也不读取旧 H3 ledger、系统 Temp 或 `.env`。

## 复盘问题

1. 将历史 24 条按 `model` 与 local shortcut 等实际 source 及公开阶段做低敏分类。对项目所有者指出的三类点位——同点数四/五张炸弹的残余孤张、开局较高普通单张先手、自然对子与单张清理——只在内存中定位对应 ACK，确认原始 canonical 候选、历史选中动作和当时的责任层；不要再次把旧局面的模型选择与本地公式选择混为一谈。
2. 按当前 HEAD 的 Botzone DeepSeek factory 显式开关与模型前生产函数，对这些历史公开 observation 与完整 canonical actions 作零网络只读投影；使用合成配置并在进程启动前禁用 dotenv，绝不读取 `.env`。若需经过客户端请求路径，只能注入拒绝联网的 fake transport，并仅在内存检查最终候选、router/RAG/recommendation、关系对照和 prompt marker。分别回答：当前开局本地快捷路径会命中还是退出、关键合法候选是否进入最终 `<=80` 项、必要公开结构/来源原则/反例是否实际进入最终请求正文；严格验证原始 action ID 与候选集合，不生成任何模型结果。若历史输入无法被当前接口合法重放，标记固定 `inconclusive`，不要补造牌局或绕过门槛。
3. 其余 ACK 做范围受限的高置信 triage：只报告当前链路中可复现的候选缺失、模型前输入缺失或本地快捷路径异常的数量和责任层；无可验证缺口时明确写无发现。区分“历史版本已修正”“当前仍可复现”“只属模型选择疑问”“证据不足”，并给出是否需要新的真实模型/现场证据，而不是按 RuleBased 偏好判对错。H3-A11 已证明冻结续局代理有 117/235 标签变化与 40 次严格反向，故 H3-A8/A9 单次 `better/worse` 不得作为本任务策略真值。

## 验收与交付

- 真实 DeepSeek 请求、重试、其它网络、Botzone/live/connector/browser/preflight 均为 0；不创建第二桌、不清理 workspace、不产生仓库或仓库外文件。只运行与 trace 解析、模型前投影相关的现有离线测试；所有临时诊断仅在内存中完成，输出固定低敏汇总，不输出敏感原文或调用会写日志的调试模式。
- 报告证据 identity/守恒、24 条分类计数、三处观察的历史责任层与当前投影判定、额外高置信缺口数、`inconclusive` 原因、下一步建议及其证据限制；明确旧 trace 来自旧版本，当前投影不等于当前 DeepSeek 会选择该动作或真实胜率改善。
- 最终检查 Git status/diff，确认没有修改或 commit，并报告任何原有外部修改。若复盘发现需要新增工具或修改代码，停止在本只读任务内实施，只提出单独 Coding 任务供规划 Codex 审核。
