# Coding Codex 执行 Prompt：DeepSeek 开局长响应的流式诊断与受控优化

这是一项完整的响应时延任务，不再拆 H3 子阶段。先读根目录及适用范围内的 `AGENTS.md`、匹配项目 Skill、`docs/PROJECT_STATUS.md` 顶部、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、`README.md`，检查 Git status/diff/HEAD；确认包含 `3cbf9e3`，保留所有外部修改。只在本任务直接相关的 DeepSeek 客户端、开局模型前输入及其测试/离线评测辅助中做最小改动，不改引擎、Botzone 协议、个人启动器、规划文档、`.env` 或私密配置。

已验证的起点：默认 Botzone DeepSeek factory 的三个固定完整开局中，B 级原则与条件化 C 级软假设同处最终 Request，候选和推荐闭环，输入比修改前更短。上一任务六次真实请求均成功，但请求发送至首字节只占约 0.2–0.3 秒，首字节后至 SSE 完成仍为约 22–78 秒；本地组装约 0.08–0.13 秒。这些低敏单点测时来自执行报告，不是独立网络证明，也不能把前后差额解释为因果提速。当前默认传输以 `response.read()` 收完整 SSE 后才解析；30 秒网络读超时不是整次决策的硬截止。seed `47005` 的 `platform_error` 未被证实由模型时延引起，禁止把它当作既定根因。

先用禁网传输与真实 `build_agent_factory("deepseek")`，在 `low_cost_single`、`neutral_soft_pair`、seed `29` 三个完整开局固定最终候选及 Request 资格。审计实际 SSE/解析链：区分连接/首字节、首个 reasoning chunk、首个 content chunk、完整可解析合法 JSON、终止事件与最终返回；只记录单调时钟间隔、长度或低基数类别，不保存或输出 prompt、手牌、模型文本、URL、token、密钥。审查 `response.read()` 的缓冲、分块、异常、最大内存和关闭连接行为，以及现有模型请求参数；需要外部 API 能力时只依据官方文档，不猜测参数。确认究竟哪一段有可实施且不损害动作守恒的优化空间，再实施一个最小、可回退的方案。可选方向包括逐行增量解析并仅在协议确认完成、完整 JSON 合法时及时返回，或有官方依据的低时延请求选项；不能仅见到首个可解析 JSON 就中断，因为后续内容仍可能改变结果。不得为了看似提速而任意截断推理、缩小合法候选、切换模型、扩大本地直选或增加成功模型后的策略覆盖。若没有可证明安全的优化，保留诊断和回归结论，不强行改生产行为。

用假传输覆盖 SSE 分块边界、跨 chunk JSON、reasoning 先于 content、重复/畸形事件、迟到内容、非法/未展示 ID、网络中断与关闭、无终止语义等反例；严格保持当前成功模型的原始合法 action ID 与 `model` source、失败 fallback、最多 80 候选、B/C 命中与开局关系/推荐闭环。若实施增量读取，必须证明没有把不完整 JSON、部分候选 ID 或未完成响应当作确定动作；无法证明时不得启用。生产 Botzone 路径仍须通过禁网 factory 请求验证。测试时显式禁用 dotenv，运行相关、主规则及全量 `unittest` 和 `git diff --check`。

只有离线资格与安全回归先通过，才可对同三状态做最多 6 次真实 DeepSeek 请求（基线与改动各最多一次/状态，`max_retries=0`，总数严格少于 10）；配置或网络失败即停止外部测量，不重试或更换样本。按同一低敏分段口径报告耗时、provider outcome、动作粗类别和候选/ID/source 守恒；单点差异不得称为因果加速、策略最优或胜率。不得运行 Botzone/live/connector/browser/preflight，不访问 Codex 或个人 workspace、旧 ledger/evidence。只暂存并提交本轮自有代码/测试；若仅诊断而无安全代码改动，明确报告无 commit。报告实际发现的时延构成、采取或拒绝的方案与理由、测试、真实请求次数、剩余可用性风险、最终 Git status 和任何保留的外部修改。
