# Coding Codex 执行 Prompt：关闭开局建议的实际接线缺口

这是 `ad7524e feat: guide DeepSeek opening tradeoffs` 的同一项开局模型前引导工作的验收纠偏，不另建 H3 阶段。开始前阅读根和适用范围内 `AGENTS.md`、匹配的项目 Skill、`docs/PROJECT_STATUS.md` 顶部、`docs/CLEAN_HANDOFF.md` 顶部、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、`README.md`；检查 Git status/diff/HEAD，确认包含 `ad7524e`，保留他人修改。规划 Codex 不改业务代码或测试。

复审已证实两个缺口。第一，新增测试中的三个完整开局状态都使用 `rag_top_k=3`，新指引均进入 Request；但真实 `build_agent_factory("deepseek")` 不设置该参数，Agent 默认 `rag_top_k=1`。以同一禁网 fake transport 通过真实 factory 路径重放，`low_cost_single` 有新指引，`neutral_soft_pair` 和 seed `29` 没有；三场候选仍分别为 23、51、50，原始 ID 和 `model` source 守恒。top‑1 在后两场只命中软对子条目，适用的开局来源原则被检索预算挤出。第二，在 seed `29` 且 `rag_top_k=3` 的开局，关闭 `strategy_recommendation_enabled` 时，新指引虽然被计算为可用，却只在有效 recommendation 区块内渲染；旧“留牌边际判据”仍因该计算结果被省略。相同状态无 RAG 时旧判据保留。这是模型前信息被静默删减的真实回归。现有相关 70 项、主规则 39 项均通过，说明测试尚未覆盖这两条路径。

修复目标：让**实际 Botzone DeepSeek factory** 的开局模型路径也稳定获得符合来源适用条件的简短跨牌型引导，不依赖测试专用 top‑3 设定；同时让新增指引与旧判据的取舍基于“最终确实渲染到实际 Request”的同一条件。可调整开局经验检索的有界来源选择、开局专用投影或渲染位置，但不得简单全局提高 top‑k、无条件注入未命中的来源、把 C 级软假设伪装为 B 级原则，或复制已有冗长关系句。无适用来源/候选时仍省略新指引；recommendation 关闭、不可用或校验失败时，不得同时丢失新旧两种判据。保持公开候选、RAG 与原始 Request 的闭环，字符长度与候选上限受控。

用固定三个完整初始牌局和实际 `build_agent_factory("deepseek")` 的禁网注入 transport 锁定生产默认参数；断言实际 Request 中的来源、指引、关系对照及反例。另覆盖显式 top‑1/top‑3、recommendation 开/关及畸形/不可用、空/不适用 RAG、非开局和候选不足两牌型；当新指引不渲染时，适用的旧判据不得被误省略。检查候选 `<=80`、推荐 ID 闭环、原始合法 action ID 与 `model` source；保留 only-pass、立即出完和本地开局公式的完整关系门槛。对比同三状态当前 factory 基线与修复后的 prompt 字符数，避免明显膨胀。

本轮只修上述实际输入接线与信息丢失，不修改 engine、Botzone 协议/运行预算、配置、`.env`、两个 workspace 或规划 docs；不运行真实 DeepSeek、网络、Botzone/live/connector/browser/preflight，也不重做上一轮三次请求。上一轮报告的 27.14、66.94、40.12 秒只是单点客户端耗时，且字符仅减少约 70 字；不能声称本提交解决响应时延或此前平台 `platform_error`。显式禁用测试进程 dotenv，运行直接相关、主规则和全量 `unittest`，执行 `git diff --check`。只暂存并提交本轮自己的业务/测试文件；报告根因、真实 factory 路径复现与修复、测试、commit、最终 Git status 和任何保留的外部修改。
