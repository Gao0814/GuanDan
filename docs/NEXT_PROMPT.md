# Coding Codex 执行 Prompt：强化 DeepSeek 开局模型前建议

项目所有者选择以 DeepSeek 为开局主要决策者，先强化模型前引导，不继续为增加本地直选频率而放宽公式。开始前阅读根及适用范围内 `AGENTS.md`、匹配的项目 Skill、`docs/PROJECT_STATUS.md` 顶部、`docs/CLEAN_HANDOFF.md` 顶部、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、`README.md`，检查 Git status/diff/HEAD 与 `b17c2d9` 是否已包含；保留他人修改。只做这一项完整实现与验收，不拆成新的 H3 子阶段。

已知事实：`b17c2d9` 以完整公开关系封住了本地直选遗漏；规划复算 600 个完整 27 张初始牌局，仅 17 次安全小单本地直选、对子/三张 0 次，其余交 DeepSeek。现有 `strategy_recommendation` 至多给 3 个原始 ID，常以安全单张及对子兜底；RAG、router、公开关系对照与候选结构虽已有多牌型信息，但最终请求中的开局取舍仍需核对。不要把 0 次成组直选当作应强行增加本地规则的理由，也不要预设模型选择某牌型才算正确。

先用禁网真实 `DeepSeekAIAgent`/`DeepSeekClient` 请求组装路径，记录同一公开状态下的基线：现有两个完整双副牌开局 fixture（`low_cost_single`、`neutral_soft_pair`）及 `tests/test_multi_pattern_opening.py` 中 seed `29` 的完整初始牌局。检查实际 Request body 与最终候选、推荐 ID、RAG 命中、router、关系两侧和 prompt 字符数；只从公开 observation 与完整 canonical `legal_actions()` 取输入，不读取密钥或仓库外 live evidence。区分“候选缺席”“关系/来源未激活”“信息已渲染但缺少跨牌型取舍”和“重复文字过长”；据此实施最小必要修正，不重复堆叠已有关系句。

在模型前形成简短、可核验的**开局取舍指引**：当实际候选成立时，比较结构安全自然单张、自然对子、三张、顺子等首出路线的动作后余组/孤张、拆组成本、控制或回手资源及公开队友/对手紧急性；明确各路线何时值得考虑、什么反例可推翻，而非固定“先出单张/对子”或按点数写死。复用已有 B 级来源原则、条件化 C 级软假设和公开候选关系；若发现确有来源/适用性缺口，可同步修正 RAG 投影与语料登记，但不得把治理元数据或未经核实的策略主张送进模型输入。三 ID 推荐预算与 80 项最终候选预算保持有界；无法把所有牌型塞进推荐 ID 时，仍应让重要、成立的跨牌型对照两侧进入最终候选和实际 prompt。避免明显增加上述三个固定状态的 prompt 长度；报告改动前后字符数，字符数不是时延证明。

保留 only-pass/立即出完、本地开局公式及其完整关系门槛；不改引擎真值、Botzone、连接器、配置、`.env` 或两个 workspace。模型合法动作必须保持实际展示的原始 action ID 与 `model` source；不得新增成功模型后的策略覆盖、现场 seed/点数特判、按 RuleBased 偏好强制选择、暗牌推断或从 RAG 构造动作。异常、畸形公开 payload 和缺失候选继续 fail closed。

验收使用完整引擎初始牌局及实际禁网 Request（不能仅测手工 prompt builder）：覆盖强/中/弱或可实际构造的不同牌力、单张与对子/三张/顺子竞争、候选预算竞争、来源适用与反例、禁用本地公式时仍为模型前建议、非开局不得泄漏开局专用指引；固定三个状态的基线/新版 Request 中，相关两侧 ID 均需来自完整 canonical、在最终 `<=80` 候选内且与正文一致。fake provider 返回任一已展示合法 ID 时必须原样返回且 source=`model`。显式禁用测试进程 dotenv，运行直接相关、主规则及全量 `unittest`，执行 `git diff --check`。报告开局公式直选是否保持、最终候选与推荐闭环、prompt 长度变化和任何未解决的输入缺口。

离线资格全部通过后，在**同一任务**对上述三个预注册状态各做至多 1 次真实 DeepSeek 请求，总数最多 3、重试 0，不运行 Botzone/live/connector/browser/preflight。只在内存中读取模型输出；报告每次 provider outcome、候选内/`model` source 守恒、单次请求墙钟耗时和动作类别，不持久化或输出 prompt、模型文本、手牌、URL、token 或密钥。若配置不可用、资格失败或请求出现异常，立即停在已完成的安全范围并如实报告，不补样本或重试。三次时延只是固定状态单点实测，不声称因果加速、策略最优或胜率改善。

只暂存并提交本轮自己的业务/知识/测试文件，不改规划 docs。报告根因、实际输入改进、测试与有限真实测时结果、commit、最终 Git status 和保留的外部修改。
