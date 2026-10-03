# AGENTS.md

## 项目概览

本项目是一个单局掼蛋（GuanDan）核心规则引擎和 AI 决策层的最小闭环实现。

当前算法优化和 Botzone 验证固定使用级牌 `2`、四人、无需进贡的单局 profile。引擎仍保留单局级牌与逢人配规则真值，但除非项目所有者明确提出新任务，不安排跨 13 种级牌的策略泛化评测，不实现多局升级、进贡、还贡或抗贡流程。

所有者2026-10-01明确当前项目只使用Flash，不引入双模型调用或跨局对手画像；局内画像仅为待验证方向，不作为真实试局的前置开发任务。

当前 profile 的牌型、逢人配、压制、轮转、接风及终局时机以 Botzone 官方裁判为对齐依据；仓库旧规格与裁判不一致时，不得用旧规格或旧测试否定平台规则。所有者明确保留独立的本局胜/平/负口径：头游与末游同队为规则平，其余头游队获胜；Botzone 的正分1/2/3是平台积分结算，必须另列，不把平台1分直接改成项目规则胜，也不改变残局搜索的规则胜平负目标。当前源码摘录与差异见 `docs/BOTZONE_REFEREE_EXCERPTS.md`、`docs/BOTZONE_RULE_ALIGNMENT.md`。

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
- 已退役的历史链路和专属旧测试在Git历史保留；2026-10-01已核对引用并回收archive_legacy及部分旧阶段评测，当前清单见docs/MAINTENANCE_REPORT.md。
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
- 当前已授权M10共同公开假设的有限续局辅助：假设生成与策略比较仍在AI层；必要时可在`engine/`新增或复用狭窄的公开payload推演接口，使重建和推进采用既有规则。不得因此改变规则真值、让AI读取内部状态，或放宽M9确证与保胜接口。
- `observe()` 必须返回固定公开结构，不要暴露内部 `GameState`、`PlayerState`、`Action` 等对象。
- `legal_actions()` 必须返回显式展开的 canonical action，每个动作包含 `action_id`、`declared_pattern`、`declared_cards`、`carrier_cards`、`wildcard_count`、`wildcard_info` 和 `display_text`。
- `step(action_id)` 只接受当前 `legal_actions()` 中存在的动作 ID。
- 通配牌、王炸、顺子边界、炸弹层级、接风、三游终局、胜负/平局等规则属于引擎真值，修改前要阅读对应测试和 `docs/INVARIANTS.md`。
- 状态模型使用 `@dataclass(frozen=True, slots=True)` 的不可变风格；修改状态时优先沿用现有 `replace()` 和 `with_*` 方法。
- 测试使用 `unittest`，测试辅助函数常见命名为 `_card()`、`_cards()`、`_hands()`、`_pass_id()` 等。
- 中文 CLI 输出是测试契约的一部分，修改 `cli/run_4ai_debug.py` 时要同步检查 `tests/test_cli_debug_output.py`。
- 已退役历史代码不从Git历史主动重新迁入或修复；只有具体新任务确有需要时再恢复必要部分。

## 测试要求

- 默认只运行修改模块的相关测试；接口、规则或共享计算影响其他模块时，按实际调用关系补少量直接受影响的测试，不因修改了 `engine/`、DeepSeek、记牌或 RAG 就自动扩大到全量。
- 根据本次改动选择测试方法或测试文件，不要求整份测试文件、整个主回归集合都重复执行。已有测试足以验证时，不为了每次任务新增测试文件；纯文档和低影响可逆修改做对应检查即可。
- 规则改动可按需要选用下面的主回归集合；这是可用命令，不是每次改动的固定门槛：

```bash
python -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q
```

- 修改 CLI 输出时，选择相关输出测试：

```bash
python -m unittest tests.test_cli_debug_output -q
```

- `python -m unittest discover -q` 保留为可选全量命令，普通 Coding 与规划复审均不默认执行。只有所有者明确要求，或已确认的广泛影响确实无法由定向检查覆盖时才选择全量，并说明具体理由；不得把“未跑全量”本身列为失败、剩余风险或阻止验收的条件。已通过的检查不因进入复审或换对话自动重跑。
- 长期测试只保留稳定、可复用且能发现实际回归的必要覆盖；一次性性能对照、诊断探针和阶段数据核对可作为临时检查，不必进入默认 discover 或永久提交。已完成用途且无持续覆盖价值的脚本、重复/失效测试可经明确路径与引用核对后回收；不得通过删失败测试掩盖未解决问题。测试代码的修改与回收由 Coding Codex 在对应任务内执行，规划 Codex 不越界操作。
- 报告实际命令、结果及验证范围；无法运行时说明具体失败原因或环境限制。不要求每轮复述未涉及的全量、网络或实战验证清单。

## 安全与配置注意事项

- 不要修改或提交 `.env`，不要读取、输出或硬编码真实密钥。
- `.env.example` 只能放示例配置，不应包含真实凭据。
- DeepSeek API Key、Base URL、模型名、超时、重试次数等配置必须经由 `config.py` 和环境变量读取。
- 项目所有者长期授权：单个明确诊断或评测任务中，预注册的真实 DeepSeek API 外部请求总数严格少于 10 次时无需另行申请；达到 10 次或更多仍须事先取得明确授权。该授权只免除请求次数审批，不放宽任务范围、重试上限、密钥保密、低敏报告或禁止持久化模型自由文本等约束。
- 不要在业务代码中硬编码 API Key、生产 URL 或本地绝对路径。
- 不要删除 `.venv/`、`logs/`、在用私有配置/现场证据或用户未明确要求处理的文件；旧代码/评测回收按当前明确任务核对路径与引用。
- 本项目当前没有数据库、迁移脚本或生产部署配置；如未来出现，除非用户明确要求，不要修改迁移、生产配置或密钥相关文件。

## Botzone 现场执行与仓库外工作目录

- 所有者2026-10-02明确：对外称局使用“日期（月日）＋当日有效局序号”，例如100203表示10月2日第三把有效局；无效局不占该序号。内部连续目录号仅用于定位证据，不再作为对外局名；映射维护于当前PROJECT_STATUS/CLEAN_HANDOFF，不改写旧私有目录。所有者以后可选择同号seed方便复现，局编号与实际使用seed分别核对，不仅凭编号倒填历史seed。
- 同一seed的多次尝试只计一个有效局单位，按尝试顺序从0编号，例如100204_0、100204_1；复测不增加当日有效局序号，不把重复尝试算作独立新增样本，各次结果分别保留。所有者只在Planning明确要求重打时重复同一seed；Planning需说明重打要验证的具体问题，不能泛泛要求重复试局。现有100203/100204首次记录对应_0。
- 普通 Botzone 算法 smoke 固定使用级牌 `2`、无需进贡；不得为了“泛化”自行扩展为其他级牌、贡还或多局升级测试。
- 必须区分“普通开发/算法诊断运行”和“正式预注册实验”。除非项目所有者在当前任务中明确要求正式实验，普通运行不得继承 manifest 不可变、逐字节 preflight、progress 状态机、seed 永久作废或任一准备错误整批 invalid 等正式实验门槛。
- 在任何外部建桌提交或 live 对局开始前，shell、参数、路径、preflight、日志配置和其他准备阶段错误都属于可原地修正的编排问题；不得把这类零外部副作用的小错误升级为不可恢复的实验失败。正式实验若需要更早的不可重试边界，必须在专门 Prompt 中显式预注册。
- 只有当前任务明确要求Codex托管/监督实时单局时，才读取并遵守 `.agents/skills/botzone-manual-live/SKILL.md`；所有者自行试局后的证据复盘使用 `.agents/skills/botzone-game-audit/SKILL.md`，不继承托管live流程。网页建桌、配置和开始默认由项目所有者手工完成；除非当前任务明确授权，否则 Codex 不点击、输入或提交。
- 人工 live 的硬顺序是：workspace/preflight 就绪 → 唯一 connector 持续运行 → 页面确认“已连接” → 才提示 seed 和建桌配置 → 核对后开始并持续监测。页面不可读时接受项目所有者明确确认；页面明确显示配置不匹配时必须等待修正。seed 从执行 Codex 首次向项目所有者发送含该 seed 的建桌配置时起视为已使用。
- Codex 执行的 Botzone 运行产生的 state、audit、manifest、progress 和其他 evidence 统一放在仓库外固定根目录 `D:\VsCodeProject\BotzoneWorkspace`。项目所有者亲自进行的轻量试局默认使用独立的 `D:\VsCodeProject\GuanDanManualWorkspace`，不得写入或覆盖 Codex workspace；个人目录不进入正式评测或 Codex 自动清理清单。
- 当前项目所有者自行完成所有真实 Botzone 页面和 connector 启停操作；Codex 仅在所有者交付结果或保留的 evidence 后做只读审计。连续试局脚本已经交付，默认持续轮询、不逐局等按键，`--games N` 表示最近 N 局证据容量而非自动停机局数；网页建桌和开始仍由所有者操作。上文 Codex 托管 live 的顺序和项目 Skill 不强加给所有者的自操作试局。所有者当前选用固定 `D:\VsCodeProject\BotzoneWorkspace` 留证；正在运行的旧批次和此前目录必须原样保留，新版写盘只在所有者下次亲自重启脚本后生效。个人轻量试局仍默认使用 `GuanDanManualWorkspace`。人工约十局的胜负比例可作方向性观察，须列明有效局数、对手/条件差异和异常局；有前后两组时直接比较胜局/有效完局，不设正式实验门槛，也不把小样本比例写成已证明的算法增益。
- `D:\VsCodeProject` 下不得再创建其他以 `Botzone` 开头的顶层运行目录；不得按 seed、pilot、pair 或 capacity 新建顶层目录。上述个人目录虽不以 `Botzone` 开头，也只能用于项目所有者的个人试局，不得借其绕过 Codex live 的固定 workspace 和审计边界。
- 个人试局可在下一次启动时覆盖自己目录中的上一轮证据，但启动器必须先确认精确目录归属、普通非链接属性、内容白名单及无运行中的项目 connector；仅处理该个人目录，优先采用回收站等可恢复方式，不得通配清理 Codex workspace。若所有者发现问题并要求 Codex 复查，暂停下一次个人试局，保留该局目录供 Codex 只读检查；复查前不得自动覆盖。无问题时无需逐局提交报告。个人试局的 prompt、模型自由文本、凭据和连接 URL 仍不得持久化或共享。
- 独立目录只隔离文件，不隔离 Botzone 本地 AI 连接：同一连接地址下个人与 Codex connector 不得同时轮询；若需要并行，必须由项目所有者明确提供互不相同的连接端点，并另行规划。个人启动器默认不得启动第二个项目 connector。
- 固定 workspace 的旧 evidence 清理必须读取并遵守项目 Skill `.agents/skills/botzone-workspace-recycle/SKILL.md`。项目所有者已长期授权：规划 Codex 确认上一轮结果已审计并写入状态文档后，可清理该 workspace 内经精确核对的旧 artifact，无需重复请求授权；授权不得扩大到其他目录、未审计 evidence、C 盘或清空回收站。
- workspace 的清理/准备与 Botzone live 执行必须是不同任务边界。live 执行开始后不得删除、清空或重置 workspace；需要修复或重跑时先停止并交回项目规划 Codex。
- connector 的显式 opt-in 可读牌谱允许记录本家完整初始/当前手牌、Botzone 请求实际暴露的公开出牌历史、本家已确认动作和终局结果；本家手牌只能进入仓库外牌谱文件，不能进入聚合 audit 或普通日志。其他玩家暗牌只允许在终局后、已证明动作尾部完整且能由 108 张实体牌守恒唯一推出时标注为“推导”，否则必须写未知。不得记录密钥、连接 URL、Cookie 或模型自由文本，也不得把可能缺少终局前末尾动作的观测历史声称为完整裁判牌谱。
- connector 的显式 opt-in decision trace 必须写入仓库外的新文件且默认关闭；只允许在响应 Header 已确认后记录本家当时的公开 observation、逐字段一致的原始 canonical legal actions、最终原始合法 action ID/action 与固定低基数 source。pending 未确认动作不得落盘；单文件只能绑定一个 match，fresh CLI 不得覆盖既有 trace。trace 不得包含 match ID、run token、URL、Header、Cookie、密钥、prompt、模型响应/reasoning、notes 或异常正文，也不得进入聚合 audit 或普通日志。
- 2026-09-28 所有者明确要求固定 workspace 的自操作连续试局**另外**保存每局完整模型请求正文，供逐动作调试；这是该固定批次专用、按局隔离的私有诊断证据，对上一条通用 decision trace 的 prompt 禁令及个人轻量试局禁令作局部例外。保存模型交给传输层前准备的完整请求 body 与其摘要、当时的公开观察/本家手牌、完整 canonical 候选、实际展示候选、模型选择与最终 ACK 状态；`request_prepared` 不单独证明网络送达。不得保存 Authorization、API Key、连接 URL、Cookie、原始模型响应/reasoning 或异常正文，不得把请求正文写入 stdout、聚合 audit、仓库或共享报告。未 ACK 的动作也要记录为待确认以便定位停牌，但不得冒充已确认出牌。此类可恢复留证失败必须显式标记 evidence 不完整，不改变合法动作、响应或 ACK 事务。
- 2026-10-01 所有者进一步明确要求实际试局写入模型选择的简短JSON `reason`以便调试：允许在上述固定workspace私有逐局证据内保存成功有效模型动作同次返回的该字段，单行且最多120个Unicode字符，截断时明确标记；以决策编号和最终原始ID绑定，并结合既有ACK区分待确认/已确认。这仅对短 `reason` 作模型自由文本持久化禁令的局部例外，不保存完整content、SSE `reasoning_content`、长思考、异常正文或凭据/URL/Headers，不进入stdout、聚合audit、仓库、共享报告或个人轻量workspace。复盘可只读该私有字段，对外仍用必要的简短脱敏摘要；缺失/无效解释不补造、不追加请求、不改变合法选择、回退或ACK。固定批次既有私有逐局留证开启时接入，通用CLI/trace及其他路径不默认落盘；旧证据不追填，运行中旧批次不修改，所有者下次重启后生效。
- 固定 workspace 新版逐局证据按本地时间命名，每局一个私有目录，连续运行和跨启动只滚动保留最近 N 局（默认 10，异常/未确认局也计入）；只允许在精确归属、非链接、版本化目录内有界移除已退出且不在审计保留中的最早新版逐局证据。清理旧 `manual-batch-*`、未知目录或运行中证据仍遵守上文单独审计与 workspace recycle 规则，不得把新的滚动授权扩展过去。内部会话哈希文件可以继续用于协议恢复，但不能冒充用户可查阅的逐局记录。

## Codex 工作规则

- 所有者2026-10-03明确授权本轮收尾接入同局条件计划：保持JSON action_id/reason两字段，可在既有最多120字符的短reason中包含条件化后续，并在上次实际执行已确认后以本局内存最多一条供下一prompt重估。该短reason作为固定workspace完整实际Request上下文属于已授权私有留证；不新增自由计划字段/文件、长思考、跨局记忆或个人/聚合日志。新事实与当前合法候选优先，缺确认、断历史、换局或晚到结果不得污染计划，不自动执行旧计划或复用旧ID。
- 项目理解与结项文档Codex是独立分工：首次只读理解，之后按所有者明确材料任务默认维护docs/closeout/；不执行NEXT_PROMPT，不修改共享规划文档、AGENTS/Skills、业务或tests，不安排算法/现场/回收任务。Planning维护算法计划并独立复审，Coding实现业务；结项角色发现冲突交所有者转达，不主动向其他对话发消息。
- 开始新任务先读取适用范围内的 `AGENTS.md`；根据已提供的Skill名称/description或目录元数据判断任务是否匹配，只有实际使用时才完整读取对应 `SKILL.md`。不得为了判断适用性先通读全部Skills，也不因换一轮消息重复读取已完整读过且未变更的Skill；上下文缺失或Skill变更时再读取。所有者可显式指定Skill，明确匹配的任务也可自动使用。AGENTS硬约束优先于Skill，当前任务的明确特殊要求只覆盖直接冲突的流程细节。
- 项目Skill按任务分工：`botzone-game-audit`负责最近已留证游戏、可疑单次出牌、模型输入/选择/ACK与必要重放的分析；`botzone-manual-live`仅用于明确要求Codex实时托管单局；`botzone-workspace-recycle`仅用于单独回收已审计的固定workspace清单。普通代码复审、文档维护或技能维护不自动加载现场/清理Skill。
- Coding Codex 负责业务源代码、tests 及任务直接相关文件的修改、验证和提交；项目规划 Codex 负责复审执行结果，并只提交其自己产生的 `AGENTS.md`、项目 Skills 和 docs 上下文修改。双方不得把用户、其他 Agent、来源不明或对方未完成的修改混入自己的 commit。
- 项目规划 Codex 不是主要业务代码执行者；除 `AGENTS.md`、`.agents/skills/**` 及 `docs/**/*.md` 外不得主动修改项目文件。发现业务问题时应分析、规划并交给 Coding Codex 实现。
- 写入前后检查 Git 状态和 diff；只按明确路径暂存本轮自有修改，禁止使用 `git add .`。未经项目所有者明确授权，不得用 reset、clean、restore、checkout、stash、history rewrite 或 force push 处理未知修改。提交后再次检查 Git 状态，并报告 commit 及任何保留的外部修改。
- 执行报告必须区分“项目既定适用范围”和“剩余风险”。固定级牌 `2`、无需进贡、单局以及不做跨级牌/贡还/多局升级属于已接受的项目范围，不得写成剩余风险、缺陷或未完成项。只有当前范围内仍可能导致错误、回归或验收失败的事项才能列为剩余风险；如果没有已知范围内风险，应明确写“当前范围内无已知剩余风险”。
- 修改前先阅读相关文件、测试和文档，尤其是 `README.md`、`CLAUDE.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md` 与相关测试。
- 只做与当前任务相关的最小必要修改。
- 普通迭代与合并默认在当前GuanDan原仓库继续，用Git分支/tag和一份已验证完整bundle保留恢复点；不为普通任务创建常驻工程副本。明确需要隔离时再安排临时工作区。
- PROJECT_STATUS、PLAN、CLEAN_HANDOFF和TESTS只维护当前事实、有效任务/边界与必要入口；不逐轮追加已完成阶段快照、旧Prompt或全部测试日志。旧过程由Git历史恢复，完成的NEXT_PROMPT撤下，不另造历史文件堆。
- 不要做无关重构、格式化、迁移或目录清理。
- 不要覆盖用户已有改动；遇到工作区中无关修改时保持不动。
- 新增依赖前先说明理由，并确认确实不能用标准库或现有依赖解决。
- 修改后运行相关测试；如果未运行或无法运行，要说明原因。
- 不确定时列出假设和需要确认的问题，不要编造不存在的命令、配置或行为。
- 对 AI 决策改动，不要把规则合法性判断移入 AI 层。
- DeepSeek 是其合法动作空间内的主要策略决策者。策略质量问题应优先从公开信息投影、prompt、RAG、策略意图和可重复模型评测定位；不得仅因模型选择与 RuleBased 偏好不同，就把 RuleBased 选择新增为成功模型动作的强制后置覆盖。确定性后置覆盖只用于合法性/协议安全，或项目所有者已经明确批准且有独立证据的关键策略不变量。
- 普通算法迭代应针对声称改善的能力构造可复现的合法牌局（可自行构造，或核对公开经典残局来源）并比较模型前后选择；只设置会改变结论的必要检查，不沿用正式实验的逐字节请求、manifest 或整批作废门槛。所有者自行进行的约十局 Botzone 测试可报告胜局/有效完局和异常作为方向性观察；小样本不能单独证明因果胜率增益，也不妨碍继续处理具体可复现的算法问题。
- 对规则引擎改动，要保持 `observe()`、`legal_actions()`、`step(action_id)` 的公开契约稳定。

## Coding Codex 的执行与反补丁职责

- 每次新任务都从当前仓库事实重新开始：阅读 `AGENTS.md`、适用项目 Skill、`docs/CLEAN_HANDOFF.md` 与当前存在的 `docs/NEXT_PROMPT.md`，核对 Git status、HEAD、相关提交、代码和测试。旧对话或执行报告只是线索；与可验证代码冲突时以仓库和实际运行结果为准。已提交完成的旧任务不重做；没有当前 Coding Prompt 时不从历史快照猜任务。
- 修改业务代码前先定位当前行为的机制与层次；Prompt 中的检查建议不是未经验证的根因。可在任务边界内自主选更统一的实现，必要时说明偏离原因；若正确修复必须突破重要边界，先报告，不静默扩展到无关重构。
- 提交前做反补丁自检：改动能否覆盖同类但未列出的合法局面；新增的特殊分支、白名单、牌点/seed/action ID、source/scene 字符串匹配或重复 mapping，是必要的领域规则还是抽象不足。不要用成功模型后的强制改牌、测试专用旁路或只扩大合成正例来制造表面改善。
- 测试按本次修改及直接影响范围验证机制与必要调用链，不为当前实现反向放宽有效断言或删除暴露未解决问题的测试。区分合成 case、单元/回归、完整牌局、真实模型选择、实战结果与胜率证据；只声明实际验证支持的结论。遵守当前任务明确的验证与禁网/真实调用边界，历史任务的全量门槛不自动继承。
- 完成后检查完整 diff，只暂存并提交本任务自有业务代码和 tests，不处理规划、用户或来源不明的修改。最终简报需说明已确认根因或不确定层级、统一实现、修改文件、反补丁自检、实际验证命令与证据层级、commit、最终 Git status 和当前范围内真实剩余风险。

## 规划 Codex 的工程判断增量职责

- 保持现有项目阶段、算法主线、Coding 分工与事实来源优先级。只有确定下一项真实 Coding 任务时，才在面向所有者的规划汇报中简短说明问题本质（证据不足时写明已确认层级）、当前最可能的 1–3 个补丁风险、最重要的 1–3 个既有不变量，以及 Coding 完成后最值得人工检查的 2–4 处。重要阶段可用 3–6 条的“工程判断”小栏；没有值得强调的判断时不硬凑。
- 复审 Coding 提交时，先核对 Git、源码和已有验证证据，针对本次改动选择有独立价值的少量检查，不机械重跑 Coding 全套测试。检查改动是否自然覆盖同类问题，还是只绑定当前 seed、牌点、action ID 或测试；检查新增分支、字符串硬匹配、重复映射和例外是合理领域枚举，还是抽象不足造成的补丁堆积。需要验证类推能力时，选择能改变结论的相似合法局面，不为每轮固定新增大批完整牌局或模型评测。
- 明确证据层级：合成 case、单元测试、同类机制、完整随机牌局覆盖、真实 DeepSeek 决策、多局实战、胜率收益。低层证据不能直接推出高层结论；公式命中、候选/攻略文字增多或单次模型选中攻略动作都不能自动算作算法收益。始终核对公开可验证条件、原始合法动作、最终候选闭环与 DeepSeek 负责真实取舍的决策链。
- 方向被证伪时，除修正计划外，以两句短结论说明“为什么走错”和“什么信号本可更早发现”。这些判断附着于正常开发与复审，不新拆资格、观测或教学阶段；`docs/NEXT_PROMPT.md` 仍只写 Coding 可执行的目标、事实、必要约束和验收，不放教学内容。
