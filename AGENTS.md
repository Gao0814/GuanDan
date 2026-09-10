# AGENTS.md

## 项目概览

本项目是一个单局掼蛋（GuanDan）核心规则引擎和 AI 决策层的最小闭环实现。

当前算法优化和 Botzone 验证固定使用级牌 `2`、四人、无需进贡的单局 profile。引擎仍保留单局级牌与逢人配规则真值，但除非项目所有者明确提出新任务，不安排跨 13 种级牌的策略泛化评测，不实现多局升级、进贡、还贡或抗贡流程。

核心边界是：`engine/` 负责规则真值，包括牌型识别、合法动作生成、动作比较、状态推进和终局判定；`agents/` 只读取 `observe()` 与 `legal_actions()` 的公开 payload，并返回一个合法的 `action_id`。AI 层不得直接访问或修改引擎内部状态，也不得自行构造未由引擎给出的动作。

## 技术栈

- 语言：Python 3.11 风格代码，使用标准库为主。
- 依赖管理：`requirements.txt`。
- 第三方依赖：`python-dotenv>=1.0,<2.0`，用于读取 `.env`。
- 测试框架：Python 标准库 `unittest`。
- CLI：`argparse`，入口为 `python -m cli.run_4ai_debug`。
- 配置：`config.py` 统一从环境变量和仓库根目录 `.env` 读取配置。
- AI 接入：规则 AI、DeepSeek API 客户端、可选 RAG 辅助。
- RAG：本地 Markdown 知识库加载与简单检索，位于 `rag/`。
- 未检测到：`package.json`、`Makefile`、`pyproject.toml`、`go.mod`、`Cargo.toml`、`pytest.ini`、`tox.ini` 等命令配置文件。

## 目录结构

- `engine/`：单局掼蛋规则引擎。`cards.py` 定义牌模型与排序；`patterns.py` 做牌型识别；`actions.py` 定义动作模型；`state.py` 定义不可变状态模型；`rules.py` 生成与比较合法动作；`game.py` 提供 `reset()`、`observe()`、`legal_actions()`、`step(action_id)` 主接口；`logging_utils.py` 提供调试日志辅助。
- `agents/`：AI 决策层。`base.py` 定义代理接口和合法 `action_id` 校验；`rule_based_ai.py` 是规则 AI；`deepseek_ai.py` 和 `deepseek_client.py` 负责 DeepSeek 决策接入；`rag_advisor.py` 提供 RAG 证据；`hand_evaluator.py`、`card_tracker.py`、`decision_trace.py` 提供手牌评估、记牌和决策追踪辅助。
- `cli/`：命令行调试入口，目前主要是 `run_4ai_debug.py`，用于 4 AI 单局回放。
- `rag/`：本地知识库加载、检索与语料，包含 `rule_corpus/` 和 `experience_corpus/`。
- `tests/`：当前主线测试，覆盖牌型、规则、状态流转、CLI 输出、DeepSeek 降级、手牌评估和记牌等。
- `docs/`：规格、边界、不变量、测试说明、RAG 知识库说明和计划文档。
- `archive_legacy/`：历史链路和旧测试，默认不属于当前主线修改范围。
- `logs/`：本地日志目录。不要提交运行日志。
- `.venv/`：本地虚拟环境目录，不属于源码。

## 常用命令

安装依赖：

```bash
python -m pip install -r requirements.txt
```

运行全部当前测试：

```bash
python -m unittest discover -q
```

运行主回归测试集合：

```bash
python -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q
```

运行规则 AI 单局调试回放：

```bash
python -m cli.run_4ai_debug --seed 7
```

运行带步数上限的规则 AI 调试回放：

```bash
python -m cli.run_4ai_debug --seed 42 --max-steps 5000
```

运行 DeepSeek AI 调试回放，需要先在 `.env` 中配置 `DEEPSEEK_API_KEY`：

```bash
python -m cli.run_4ai_debug --agent deepseek --seed 7
```

显示 DeepSeek 玩家 1 的思考过程：

```bash
python -m cli.run_4ai_debug --agent deepseek --show-thinking --seed 7 --max-steps 10
```

设置当前级牌：

```bash
python -m cli.run_4ai_debug --agent deepseek --seed 7 --current-level-rank 5
```

构建、lint、format：未在仓库配置文件中检测到对应命令。

## 开发约定

- 保持引擎层和 AI 层分离：引擎决定动作是否合法，AI 只从合法动作列表中选择。
- 只改 AI 策略时，优先修改 `agents/`，不要改 `engine/`。
- 规则、合法性、牌型比较、状态推进或终局判定问题，才修改 `engine/`。
- `observe()` 必须返回固定公开结构，不要暴露内部 `GameState`、`PlayerState`、`Action` 等对象。
- `legal_actions()` 必须返回显式展开的 canonical action，每个动作包含 `action_id`、`declared_pattern`、`declared_cards`、`carrier_cards`、`wildcard_count`、`wildcard_info` 和 `display_text`。
- `step(action_id)` 只接受当前 `legal_actions()` 中存在的动作 ID。
- 通配牌、王炸、顺子边界、炸弹层级、接风、三游终局、胜负/平局等规则属于引擎真值，修改前要阅读对应测试和 `docs/INVARIANTS.md`。
- 状态模型使用 `@dataclass(frozen=True, slots=True)` 的不可变风格；修改状态时优先沿用现有 `replace()` 和 `with_*` 方法。
- 测试使用 `unittest`，测试辅助函数常见命名为 `_card()`、`_cards()`、`_hands()`、`_pass_id()` 等。
- 中文 CLI 输出是测试契约的一部分，修改 `cli/run_4ai_debug.py` 时要同步检查 `tests/test_cli_debug_output.py`。
- `archive_legacy/` 是历史代码，除非任务明确要求，不要主动迁移、扩展或修复。

## 测试要求

- 修改 `engine/` 后，至少运行主回归：

```bash
python -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q
```

- 修改公共接口、DeepSeek、手牌评估、记牌或 RAG 相关逻辑后，优先运行全部测试：

```bash
python -m unittest discover -q
```

- 修改 CLI 输出后，至少运行：

```bash
python -m unittest tests.test_cli_debug_output -q
```

- 修改单个模块时，可先运行对应测试文件，再根据影响面补跑主回归或全部测试。
- 如果测试无法运行，必须在最终说明中写明具体命令、失败原因或环境限制。

## 安全与配置注意事项

- 不要修改或提交 `.env`，不要读取、输出或硬编码真实密钥。
- `.env.example` 只能放示例配置，不应包含真实凭据。
- DeepSeek API Key、Base URL、模型名、超时、重试次数等配置必须经由 `config.py` 和环境变量读取。
- 不要在业务代码中硬编码 API Key、生产 URL 或本地绝对路径。
- 不要删除 `.venv/`、`logs/`、`archive_legacy/` 或用户未明确要求处理的文件。
- 本项目当前没有数据库、迁移脚本或生产部署配置；如未来出现，除非用户明确要求，不要修改迁移、生产配置或密钥相关文件。

## Botzone 现场执行与仓库外工作目录

- 普通 Botzone 算法 smoke 固定使用级牌 `2`、无需进贡；不得为了“泛化”自行扩展为其他级牌、贡还或多局升级测试。
- 必须区分“普通开发/算法诊断运行”和“正式预注册实验”。除非项目所有者在当前任务中明确要求正式实验，普通运行不得继承 manifest 不可变、逐字节 preflight、progress 状态机、seed 永久作废或任一准备错误整批 invalid 等正式实验门槛。
- 在任何外部建桌提交或 live 对局开始前，shell、参数、路径、preflight、日志配置和其他准备阶段错误都属于可原地修正的编排问题；不得把这类零外部副作用的小错误升级为不可恢复的实验失败。正式实验若需要更早的不可重试边界，必须在专门 Prompt 中显式预注册。
- 普通人工 Botzone 单局执行必须读取并遵守项目 Skill `.agents/skills/botzone-manual-live/SKILL.md`。网页建桌、配置和开始默认由项目所有者手工完成；除非当前任务明确授权，否则 Codex 只做 best-effort 只读监督，不点击、输入或提交。
- 人工 live 的硬顺序是：workspace/preflight 就绪 → 唯一 connector 持续运行 → 页面确认“已连接” → 才提示 seed 和建桌配置 → 核对后开始并持续监测。页面不可读时接受项目所有者明确确认；页面明确显示配置不匹配时必须等待修正。seed 从执行 Codex 首次向项目所有者发送含该 seed 的建桌配置时起视为已使用。
- Botzone 运行产生的 state、audit、manifest、progress 和其他 evidence 统一放在仓库外固定根目录 `D:\VsCodeProject\BotzoneWorkspace`。
- `D:\VsCodeProject` 下不得再创建其他以 `Botzone` 开头的顶层运行目录；不得按 seed、pilot、pair 或 capacity 新建顶层目录。
- 固定 workspace 的旧 evidence 清理必须读取并遵守项目 Skill `.agents/skills/botzone-workspace-recycle/SKILL.md`。项目所有者已长期授权：规划 Codex 确认上一轮结果已审计并写入状态文档后，可清理该 workspace 内经精确核对的旧 artifact，无需重复请求授权；授权不得扩大到其他目录、未审计 evidence、C 盘或清空回收站。
- workspace 的清理/准备与 Botzone live 执行必须是不同任务边界。live 执行开始后不得删除、清空或重置 workspace；需要修复或重跑时先停止并交回项目规划 Codex。
- connector 的显式 opt-in 可读牌谱允许记录本家完整初始/当前手牌、Botzone 请求实际暴露的公开出牌历史、本家已确认动作和终局结果；本家手牌只能进入仓库外牌谱文件，不能进入聚合 audit 或普通日志。其他玩家暗牌只允许在终局后、已证明动作尾部完整且能由 108 张实体牌守恒唯一推出时标注为“推导”，否则必须写未知。不得记录密钥、连接 URL、Cookie 或模型自由文本，也不得把可能缺少终局前末尾动作的观测历史声称为完整裁判牌谱。
- connector 的显式 opt-in decision trace 必须写入仓库外的新文件且默认关闭；只允许在响应 Header 已确认后记录本家当时的公开 observation、逐字段一致的原始 canonical legal actions、最终原始合法 action ID/action 与固定低基数 source。pending 未确认动作不得落盘；单文件只能绑定一个 match，fresh CLI 不得覆盖既有 trace。trace 不得包含 match ID、run token、URL、Header、Cookie、密钥、prompt、模型响应/reasoning、notes 或异常正文，也不得进入聚合 audit 或普通日志。

## Codex 工作规则

- 开始任务时先读取适用范围内的 `AGENTS.md`，再检查 `.agents/skills` 中是否有与任务匹配的项目 Skill；命中时必须完整读取并遵守。AGENTS 的项目硬约束优先于 Skill，当前任务的明确特殊要求只覆盖与其直接冲突的流程细节。
- Coding Codex 负责业务源代码、tests 及任务直接相关文件的修改、验证和提交；项目规划 Codex 负责复审执行结果，并只提交其自己产生的 `AGENTS.md`、项目 Skills 和 docs 上下文修改。双方不得把用户、其他 Agent、来源不明或对方未完成的修改混入自己的 commit。
- 项目规划 Codex 不是主要业务代码执行者；除 `AGENTS.md`、`.agents/skills/**` 及 `docs/**/*.md` 外不得主动修改项目文件。发现业务问题时应分析、规划并交给 Coding Codex 实现。
- 写入前后检查 Git 状态和 diff；只按明确路径暂存本轮自有修改，禁止使用 `git add .`。未经项目所有者明确授权，不得用 reset、clean、restore、checkout、stash、history rewrite 或 force push 处理未知修改。提交后再次检查 Git 状态，并报告 commit 及任何保留的外部修改。
- 执行报告必须区分“项目既定适用范围”和“剩余风险”。固定级牌 `2`、无需进贡、单局以及不做跨级牌/贡还/多局升级属于已接受的项目范围，不得写成剩余风险、缺陷或未完成项。只有当前范围内仍可能导致错误、回归或验收失败的事项才能列为剩余风险；如果没有已知范围内风险，应明确写“当前范围内无已知剩余风险”。
- 修改前先阅读相关文件、测试和文档，尤其是 `README.md`、`CLAUDE.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md` 与相关测试。
- 只做与当前任务相关的最小必要修改。
- 不要做无关重构、格式化、迁移或目录清理。
- 不要覆盖用户已有改动；遇到工作区中无关修改时保持不动。
- 新增依赖前先说明理由，并确认确实不能用标准库或现有依赖解决。
- 修改后运行相关测试；如果未运行或无法运行，要说明原因。
- 不确定时列出假设和需要确认的问题，不要编造不存在的命令、配置或行为。
- 对 AI 决策改动，不要把规则合法性判断移入 AI 层。
- DeepSeek 是其合法动作空间内的主要策略决策者。策略质量问题应优先从公开信息投影、prompt、RAG、策略意图和可重复模型评测定位；不得仅因模型选择与 RuleBased 偏好不同，就把 RuleBased 选择新增为成功模型动作的强制后置覆盖。确定性后置覆盖只用于合法性/协议安全，或项目所有者已经明确批准且有独立证据的关键策略不变量。
- 对规则引擎改动，要保持 `observe()`、`legal_actions()`、`step(action_id)` 的公开契约稳定。
