# Coding Codex 执行 Prompt：开局知识预算与真实响应时延联合优化

这是一个完整的算法输入与响应速度任务，不拆为新的 H3 子阶段，也不等待项目所有者再选 B/C。先阅读根及适用范围内的 `AGENTS.md`、匹配的项目 Skill、`docs/PROJECT_STATUS.md` 顶部、`docs/CLEAN_HANDOFF.md` 顶部、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、`README.md`，检查 Git status/diff/HEAD，确认包含 `1b8d493`，保留他人修改。只改本轮直接相关的 AI/RAG/评测测试文件，不改 engine、Botzone 协议/运行预算、个人启动器、配置、`.env` 或规划 docs。

已知基线：Botzone DeepSeek factory 默认 RAG top‑1；`1b8d493` 使三个固定开局均有 B 级 `exp_lead_opening_shape_001` 和跨牌型指引，但原先 top‑1 命中的适用 C 级单张/对子软假设被挤出。三个 factory prompt 为 8840、14286、14733 字符；此前 top‑3 路径三次真实调用耗时 27.14、66.94、40.12 秒，这些不是当前 top‑1 的对照，更不能推断时延根因。DeepSeek 30 秒配置是网络读超时，不应当作端到端完成期限。目标是让默认开局请求在有界预算中同时承载适用 B 原则与条件化 C 软假设，并优先减少冗余输入和过长决策时间；若某条件下二者不能同时成立，须明确报告真实取舍，不能伪装已覆盖。

在修改前固定三个现有完整初始牌局：`low_cost_single`、`neutral_soft_pair`、seed `29`。用真实 `build_agent_factory("deepseek")`、禁网注入 transport 检查最终 Request 的 B/C 来源、候选数与牌型、关系两侧、推荐 ID、prompt 字符和 UTF‑8 字节数；分段统计候选展示、公开关系、RAG、手牌评估等区块的长度与本地组装耗时，找出真正可压缩的重复或过量内容。不要仅以删掉 B/C、关键关系或合法候选换取短 prompt。保留该低敏基线以供最终报告；不得保存 prompt 正文、手牌、模型文本、URL、token 或密钥。

实施一个开局专用、有界的知识与候选展示方案：实际满足公开条件时，B 级开局原则与相关 C 级软假设应在同一默认 factory Request 中各以其原本身份可见；C 级仍明确可撤回，不能变成动作指令。可使用开局专用的至多一个额外条件化经验槽或等价的紧凑投影，不全局放大 RAG top‑k。只有来源状态、scene/phase、公开候选前提和关系条件均通过时才激活；未命中就不填充。压缩重复说明、冗长候选展示或同义关系文字时，保持原始 canonical action ID、重要牌型与对照两侧、推荐 ID 闭环、稳定顺序和最终 `<=80` 候选。只在有证据表明冗余时改动，不任意降低全局候选上限，不把 RuleBased 偏好变成模型成功后的覆盖。对三个固定开局，报告修改前后每个区块与最终 Request 的字符/字节变化；力争总输入不增长，若无法做到则说明新增知识的实际成本和原因。

为区分耗时来源，使用同三状态进行最多 **6 次**真实 DeepSeek 请求：改动前每状态最多 1 次、改动后每状态最多 1 次；每次 `max_retries=0`，整个任务真实请求总数不得达到 10。通过不持久化内容的诊断传输记录本地组装、请求发送至首字节、完整 SSE 接收、响应解析及端到端单调时钟耗时；只报告低敏数值、provider outcome、最终候选数、粗动作类别、原始合法 ID/`model` source 守恒，不输出或落盘自由文本。真实请求必须先通过相应的禁网 Request 资格，配置不可用、网络失败或资格失败时停止该外部测量，不重试、不换样本、不补请求；继续完成安全的离线实现与测试。前后测量受网络和模型波动影响，只能作固定状态描述，不能从 6 次请求宣称因果加速、胜率或策略最优。不要运行 Botzone/live/connector/browser/preflight，也不要访问两个 workspace 或旧 evidence。

回归必须通过真实 factory 禁网 Request，覆盖三个固定开局、无适用 C/无适用 B、空或畸形 RAG、top‑1/top‑3、非开局、recommendation 不可用、候选预算竞争与畸形动作。验证 B/C 来源不污染知识正文或 prompt 治理字段，关系与推荐两侧实际展示、fake provider 的任一展示合法 ID 原样以 `model` source 返回；保留 only-pass、立即出完、本地开局公式及其完整关系门槛，不新增成功模型后的策略覆盖或现场 seed/点数特判。显式禁用测试进程 dotenv，运行直接相关、主规则及全量 `unittest`，执行 `git diff --check`。只暂存并提交本轮自有业务/知识/测试文件；报告根因、输入预算前后对照、有限真实测时、尚不能消除的时延风险、commit、最终 Git status 和保留的外部修改。
