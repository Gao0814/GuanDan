# Coding Codex 执行 Prompt

任务：H3-A11——零网络检验 H3-A10 同状态动作质量代理对续局策略的敏感性。先核对 Git status、diff、HEAD 和最近提交，确认包含 `ce1a37098bcc7158302d8621bb8ce8395ae48ccf`，保留他人修改；阅读适用 `AGENTS.md`、检查 `.agents/skills/`，并阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md` 及 H3-A7/A9/A10 评测代码和相关测试。

H3-A10 在 12 个固定状态穷举了 235 个最终候选，冻结 RuleBased 续局下相对同一 RuleBased 参考动作的优/平/劣为 32/102/101。这只证明代理能区分候选，不证明其排名对续局策略稳健。此任务只检查稳健性；不要修改生产 `engine/`、`agents/`、RAG、prompt、候选生成或 Botzone，不要新增策略性模型后覆盖。

## 范围与方法

1. 复用 H3-A8/A9 的同一 12 个固定引擎状态、完整 canonical 动作、实际最终展示候选及现有 RuleBased 参考动作。首步候选和参考 ID 在两种评测中必须完全相同。基线仍为现有 `RuleBasedAIAgent` 后续续局；唯一实验变量是首步之后四座位均改用仓库已有 `FrozenRuleBasedAIAgent` 续局。不得把 Frozen agent 选择改为新的参考首步，不得用旧 H3 ledger 猜测真实模型动作 ID。
2. 每个候选分别在两个互不共享的快照克隆上完成两种续局；沿用终局类别优先、团队名次和次之、步数仅诊断的比较口径。每种续局都以本策略下相同参考首步的结果为基线，给该候选 `better/tie/worse` 标签。形成每状态及总体三乘三标签转移计数、标签改变数、严格优劣反向数、两种续局完成数和固定状态码；各状态九格之和必须等于该状态最终候选数，总计必须为 235，参考动作在两种续局中均为 tie。
3. 确认替代策略不是名义上的同一路径：在 Frozen 续局经过的公开状态上仅在内存比较它与普通 RuleBased 的合法选择，低敏报告只给出发生差异的候选分支数/状态数；若零差异，明确标记本次敏感性检查无信息量，不宣称代理稳健。不可把候选占比当模型选择概率，也不可从标签一致性推断真实策略优劣或胜率。
4. 校验快照/公开输入、12状态顺序、phase、完整和最终候选数、候选唯一/合法/实际展示、参考可见、独立克隆与原快照不变。任一分支非法、未完成、步数超限、结果畸形或比较异常则该状态 fail closed，整体不得报告完整 235 候选分布；不得跳过坏分支。输出只允许样本名、phase、候选及完成计数、九格聚合、标签改变/严格反向数、续局选择差异分支/状态数、固定状态码与总体聚合；不输出 action ID、手牌、seed、prompt、模型文本、原始快照、URL、密钥或异常正文。
5. 只在 `evaluation/` 与对应 `tests/` 增加最小离线实现和回归。测试至少覆盖 12 个真实引擎状态、基线复算与 H3-A10 的逐状态计数一致、同参考动作/候选闭环、真正不同的续局动作、九格守恒、参考动作双 tie、独立克隆、失败即停和稳定低敏序列化。不要仅用打桩的终局结果宣称两种真实续局可复现。

真实 DeepSeek 请求/重试、其它网络、Botzone/live/connector/browser/preflight 均为 0；不读取 `.env`、旧 H3 ledger、`D:\VsCodeProject\BotzoneWorkspace`、seed `47004` evidence 或系统 Temp 文件，不创建仓库外 artifact。运行相关测试、主规则回归和 `python -m unittest discover -q`；检查完整 diff 与 `git diff --check`。仅按明确路径暂存、提交本轮自有评测和测试文件，报告低敏转移汇总、真实续局差异计数、验证结果、commit、最终 Git status 与保留的外部修改。项目规划 Codex 随后独立复审；本任务不据结果修改生产策略或启动 live。
