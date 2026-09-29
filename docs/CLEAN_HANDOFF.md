# Clean Project Handoff

## 2026-09-29 当前交接：M9 首版已核，保胜捷径待同任务修正

M9 首版提交 `055b69e9bc327a069a314159c7d1cb4032ecfdda` 已把守恒确证的外部手牌送入模型输入，并在完整有界引擎搜索中区分保底与合法可达终局。规划复跑 M9/M5 定向 13 项；只读复算第 27 局保存的 step 85 公开状态，三路均保底规则平，两个单 9 可达胜、pass 不可达，本地稳定选原始 ID 1/source=`local`。Coding 报告全量 1009 项通过、1 项跳过；没有真实模型或新现场效果结论。

同一 M9 任务尚未放行：`select_proven_endgame_action()` 要求保胜路线唯一，搜索接口要枚举全部首手才返回。规划从 60 个完整引擎续局 seed 取得 117 个适用残局，109 个完整求解、8 个预算退回；10 个没有立即出完路径的状态有多条不同保胜路线但仍交模型。seed 13 step 99 两条合法路线都可保本队胜，且一条所有合法续局只到胜，禁网默认 factory 仍调用模型。所有者明确一条首手严格证明保胜即可立即选，不再搜其他首手；只有判断“唯一可能赢”时才需完整排除其他首手的胜局可能。`docs/NEXT_PROMPT.md` 已更新同一 M9 任务，不改变公开确证手牌输入、本地预算和成功模型原始 ID。所有者继续自行操作 Botzone；本轮没有启动或停止 connector、页面，也未修改仓库外证据。

【工程判断】修正时不能给 seed 13 加特判，也不能把多个保胜 ID 因数量多就一律送模型。优先检查单条保胜证明是否充分且证明完成后不再枚举其他首手；只找到可赢续线或尚未排除其他路线时，不得冒充保胜或唯一机会。

以下“M8 机制已复审，M9 Prompt 已就绪”为首版 Coding 前交接快照，以本节为准。

## 2026-09-29 M8 机制已复审，M9 Prompt 已就绪

M8 Coding 提交 `ec910ae262159627c4c244fa556285e966d3bcf6`：普通动作按完整实体手牌的同花顺/红桃级牌资源投影，在模型候选中合并资源等价的花色实体动作，保留不同资源的原始 ID 与成本。规划独立审阅代码、默认 factory 禁网请求和完整引擎局；投影/规则定向 24 项通过，`git show --check` 通过。135 个引擎中局状态中旧最终候选的 21 个等价槽位被去掉，完整续局 seed 21 step 36 的旧式筛选 12 个候选、新版 factory fake 请求 9 个；50 个完整初局的最终候选并未普遍变少。Coding 报告全量 1002 项通过、1 项跳过。输入机制通过，真实模型效果未证。没有操作 Botzone 页面、connector 或仓库外 evidence。

当前 `docs/NEXT_PROMPT.md` 是唯一可执行 M9 Coding 任务：把守恒唯一确认的外部手牌明确送入 DeepSeek 请求；用完整有界搜索区分保胜、仅有合法胜局机会和保底终局，符合证据时在模型前选稳定原始合法 ID；不完整或有真实取舍时退回模型。第 27 局是回归线索：两个实体单 9 可达胜但不能保胜，pass 只有规则平。M8 投影须保持，不能因普通 ID 合并而丢失同花顺/通配资源差异。所有者继续自操作 Botzone，Codex 不启停现场进程。

【工程判断】M8 的中局候选去重属于机制证据，不是时延或胜率证据。M9 最值得检查的点是：已证对手牌是否即使搜索超限仍在真实请求中、完整搜索是否区别“可能赢”与“保胜”、以及同路线多个实体 ID 是否仍能及时本地选一个。

以下“M8 花色压缩先行”为交付前交接快照，以本节为准。

## 2026-09-29 M8 花色压缩先行，M9 明牌推演后续

所有者明确将合并任务拆成两个 Coding 工作包，并调整顺序：先 M8 普通牌型花色压缩与同花顺/逢人配成本，再 M9 公开明牌残局推演。当前 `docs/NEXT_PROMPT.md` 仅可执行 M8；M9 在 `docs/PLAN.md` 记录目标，待 M8 复审后才形成执行 Prompt。规划没有改业务代码/tests、现场文件或所有者 connector。

M8 核查实际默认 Botzone factory 请求：普通同点数实体牌只在出后同花顺及逢人配用途等价时共用原始合法 ID 代表；资源不同的原始 ID 与成本仍给 DeepSeek。记牌器和原始 canonical 动作保留花色。M9 将把公开守恒确认的外部手牌明确交给 DeepSeek，并在完整求解证明保胜或唯一可达胜局策略路线时复用现有模型前合法快捷路径；第 27 局普通 9 保底规则平且保留胜局机会，pass 只有规则平。可达胜局不等于必胜或胜率；搜索超限时不能用部分结果直选。两项均保留所有者亲自操作 Botzone、Codex 只读审计的边界。

【工程判断】这两个任务验收重点不同：M8 看等价类及请求压缩是否真实发生且没有藏掉同花顺/通配成本；M9 看公开确证手牌是否真正送达模型，以及本地选择是否来自完整可复算的结果。不能把模型前信息增加或本地快捷命中次数直接写成胜率收益。

以下“四局审计与合并 M8 方案”为拆分前快照，以本节为准。

## 2026-09-29 四局现场审计与合并 M8 方案快照

所有者自行完成第 24–27 局；规划只读各局的 manifest、decision、timeline 和请求 metadata，未操作页面/connector/现场文件。四局均 `finished`、证据完整，平台 3 胜 1 负；本家 92 次动作均 ACK，59 次模型 success、1 次第 26 局开局 timeout 后合法回退。所有模型原始选择在实际展示候选，推荐/关系引用闭环，未发现连接/协议故障。小样本不证明 M7 策略收益。

第 27 局末步的完整公开状态可由 108 张守恒唯一推得对手 4 剩 `2C`；本家 `4H 4C 9H 9C`，对手单 6，原合法 ID 为两张实体单 9 和 pass。模型耗约 54 秒选 pass，ACK 后平台标本队胜。现有 M5 只给三路 minimax 规则平；规划对公开重建状态穷举合法续局发现：任一 9 可达规则平 `[3,2,4,1]` 和本队胜 `[3,2,1,4]`，pass 只可达规则平。胜局依赖对手选择 pass，不是本家可保胜；这也说明最坏值相同并不等于策略等价。所有者担心的“pass 必输且单 9 唯一”不符合该局公开事实；待改进的是可证小残局仍等模型、两张普通 9 重复占策略候选，且 M5 值无差异时不向模型呈现已确认的外部末张。

`docs/NEXT_PROMPT.md` 是一个 M8 Coding 工作包：公开证据完整且保底/可达上界证明普通 9 不劣并多出获胜机会时，本地及时选择原始 9 ID；证据不足则给模型已确认的外部牌和条件性比较。所有者进一步明确：普通牌型花色只在同花顺与逢人配资源判断中有策略意义，故先完整计算这些资源，再按出后资源等价压缩不同花色普通候选及模型前描述；不再以“本家完全无同花顺”为唯一门槛。会消耗同花顺路线或逢人配用途的原始候选应明确给 DeepSeek 资源成本，不作一律禁止的硬约束。当前记牌器仍保留实体花色，不改原始 canonical 动作、外部同花顺推断或红桃 2 身份。不得为本局点数/ID 写特判、改胜负规则来追平台标签，或成功模型后改牌。规划只提交文档；Coding 交付后独立复审机制、类似完整牌局、禁网请求和时延。

【工程判断】“模型想了很久才 pass”是症状；机制层是已证手牌没有进入模型，搜索只给一个最坏值并丢失可达机会。若只加一条“敌方一张必压”或把三个 0 视为等价，会漏掉本局的胜局分支。人工快速检查应看花色折叠前后的真实合法 ID 是否可追溯、可达结果是否完整，以及本地捷径是否只在证明充分时触发。

以下“M7 已交付，第 23 局一般模型路径通过”为四局审计前快照，以本节为准。

## 2026-09-29 当前交接：M7 已交付，第 23 局一般模型路径通过

当前业务 HEAD `7f20b72cf1d12eee1ffbe90765b550f09f4b89ab` 将开局公式改为来源化、可推翻的模型前建议，并在模型失败时按公开余牌结构有界回退。规划审阅核心 diff，复跑定向 57 项、规则主回归 43 项通过；Coding 报告全量 994 项通过、1 项跳过。第 22 局保存状态的禁网 fake 复算确认 K 建议与单 3 双端可见、fake 选单 3 后保留原始 ID/source=`model`；旧超时状态的新回退选择钢板 ID 65。未进行真实模型重跑。

所有者随后自行完成第 23 局，运行目录建立于 M7 提交后；`finished/local_team_win`、证据完整。8 次模型 success、1 次既定四张出完本地快捷动作，9 次动作均获 ACK；8 次真实请求的模型原始选择都在实际展示候选，推荐/关系引用闭环。首手 `444555` 为模型动作，但该手公式返回 None；本局无模型 timeout，故不能称为公式建议或新回退的现场验收，更不能由一胜推断胜率提升。所有者页面与 connector 均由其自行操作；规划仅读取精确局目录，未修改证据。

当前无 Coding 任务，已撤下 `docs/NEXT_PROMPT.md`。后续自然试局若触发公式建议或失败回退，规划再只读审计具体请求、合法原始 ID、ACK 和动作后果；若出现可复现机制缺口，再确定一项明确算法改进任务。M7 策略效果保持 `inconclusive`。

【工程判断】第 23 局仅证明新代码的一般模型路径能走通。判断改动是否有效时，应先确认改动路径在现场被触发，再比较同类状态的选择，最后才讨论多局收益。

以下“M7 Prompt 已按所有者决策权要求修正”为交付前交接快照，以本节为准。

## 2026-09-29 当前交接：M7 Prompt 已按所有者决策权要求修正

所有者明确开局公式只作高权重、可撤回的模型前建议，DeepSeek 尽可能决定真实取舍。第 22 局首手 `local_shortcut` K 的真实代码路径为公式直接返回、无模型请求，不符合这一最新要求。单 3 与 K 的现有出后结构摘要同为约 12 组/4 孤张；单 3 参与的 `A-2-3-4-5` 顺子虽然合法，实际会拆 4 炸、A/2 三张和 5 对。不能仅以候选顺子存在排除单 3，也不能说单 3 已证明更优。第 22 局第五次决策的模型 timeout 约发生在决策开始后 114 秒，约 2 秒后 ACK，符合 119 秒总期限扣 5 秒响应预留；其 `778899` 是失败回退而非成功模型选择。

新的 `docs/NEXT_PROMPT.md` 仍是一个 M7 Coding 工作包：让来源化开局公式建议进入模型请求且推荐 ID 进入最终候选，并展示 3/K 与破坏性顺子机会的真实取舍；同时用有界余牌结构比较修复模型失败后的词典序回退。不改成功模型的合法 ID，不把模型失败后的回退当作模型主动取舍，不盲目改变 119 秒期限。所有者继续自行操作真实页面/connector，规划只读现场证据并仅提交文档。下一轮需复审两条实际决策路径和时间预算，不能用单局胜负宣称策略收益。

【工程判断】此前只解释 K 的公式资格，却没有检查公式是否应拥有最终决定权。以后见 `local_shortcut`，先查它是否属于已授权的确定性捷径；见“某牌参与组合”的理由，检查打出该组合本身的余牌代价。

以下“第 22 局已审计，M7 待 Coding”为本次纠正前交接快照，以本节为准。

## 2026-09-29 当前交接：第 22 局已审计，M7 待 Coding

固定 workspace `games/2026_9_29_14-09-31_000022/` 由所有者自操作完成，状态 `finished/local_team_win`、证据完整；规划仅读取该局。首手 K 属于开局公式本地快捷动作，单 3 参与合法 `A-2-3-4-5` 顺子，K 是合格独立单张，故同秒算出且无 DeepSeek 请求。这个解释不证明 K/3 的策略优劣。第五次本家动作的 `778899` 三连对属 DeepSeek `timeout` 后的冻结规则回退，非成功模型选择；该步约 111 秒模型等待后回退，ACK 成功。它把 8、9 的自然三张拆为单张，且同一原始合法列表有自然 `888999` 钢板，余组/孤张事实更好。现行回退同张数时用牌型字符串排序，缺结构代价比较；不据此证明钢板能赢或本局结果受损。

`docs/NEXT_PROMPT.md` 是一个 M7 Coding 工作包，改进失败回退的有界结构比较，保留原始 legal ID、紧急性/终局例外、成功模型决定权和时间预算。不得硬编码本局牌点或 ID；现场 evidence 原样保留，所有者继续独立操作页面和 connector。M6 输入机制的真实模型收益仍 `inconclusive`。规划仅提交文档；待 Coding 交付后独立复审 diff、完整引擎类比局、禁网实际调用链和时延。

【工程判断】“打出三连对”与“模型认为三连对更好”是两件事，本局属于超时回退。后续几分钟人工审查优先看回退是否仍按词典序处理同张数动作、余牌结构是否真实进入排序、超时后能否及时交回合法动作。

以下“M6 已交付”为第 22 局审计前交接快照，以本节为准。

## 2026-09-29 当前交接：M6 已交付，等待自然试局证据

当前 HEAD 的 M6 业务提交为 `5dac6228cccbfc037d3c89a412f888f272c52c3c`，前一业务提交为 `bdd5cbe80abc18c45a04a3a786a2339bd4eda978`。通用 pass/应手净得失关系和两格关系预算的普通/资源路线平衡均已落地。规划复核修正 diff、定向 9 项与主规则 43 项通过；用第 19 局第 20、28、52、60 步的公开状态禁网重组默认 factory 请求，四步 pass/原所选应手均成对进入最终候选，第 20 步 `(8,1)` 顺子与一组炸弹路线同时出现。没有从保存的旧请求推断修正后的真实模型会改选。

首版 Coding 全量 991 项中 2 项旧 Windows 进程探测因所有者现场进程存在而失败，修正版未重跑全量；规划没有启停现场进程。真实 DeepSeek 与 Botzone 效果仍 `inconclusive`。当前无 Coding 任务，完成的 `docs/NEXT_PROMPT.md` 已撤下。下一步只在所有者自行试局并交付新证据后审计真实关系、动作和结果；若出现具体可复现的机制缺口再规划下一项算法 Coding 工作包。固定 workspace 第 19 局保留原样，本轮仅读取该局所需公开状态，未修改仓库外证据。

【工程判断】首版关系存在且闭环，却把两格都给炸弹；仅看测试数或关系总数会错过关键路线。复审时先确认关系选择覆盖不同的实际代价，再看请求双端与原始合法 ID，最后才讨论模型效果。

以下“M6 首版候选预算漏掉关键路线”为修正前交接快照，以本节为准。

## 2026-09-29 当前交接：M6 首版候选预算漏掉关键路线，待同任务修正

Coding 首版 commit `bdd5cbe80abc18c45a04a3a786a2339bd4eda978` 已新增通用 pass/应手净得失关系和请求文案。规划复跑 M4/M6 测试 8 项、主规则 43 项通过，`git show --check` 通过；Coding 全量 991 项的 2 项旧 Windows 进程探测失败与当前所有者 connector/批次冲突，未处理其进程。真实模型/Botzone 效果未测。规划只读第 19 局证据，用四个已保存公开局面做当前代码禁网重组；第 28、52、60 步均覆盖原所选应手，但第 20 步的两组 pass 关系均选炸弹，漏掉同样可见的原所选普通顺子。这是关系选择预算问题，尚不能验收 M6 的完整目标。

已将该漏点退回“优化3”同一 Coding 任务：按公开收益/成本选择不同路线代表，而不是对现场牌点或 action ID 特判；保持最多 80 候选、双端闭环、模型合法原始 ID 和选择权。`docs/NEXT_PROMPT.md` 仍待执行完成。规划只提交自己的文档，没有读写其他现场局正文，没有启动/停止 connector。修正结果回来后继续独立复审，再决定是否撤下 Prompt 或进入效果观察。

以下“第 19 局已审计，M6 待 Coding”为首版交付前快照，以本节为准。

## 2026-09-29 当前交接：第 19 局已审计，M6 待 Coding

所有者完成第 19 局；规划只读审计固定 workspace 的 `games/2026_9_29_13-01-36_000019/`，没有操作页面、connector 或证据。该局 `finished/local_team_loss`、证据完整，24 次本家决策、12 次成功模型路径。第 20 步顺子拆 9 的自然四炸并重新领出，第 28 步用含红桃 2 的对子接 K 对随后被炸弹压过，第 52 步拆 10 对出单 10，第 60 步在单 10 也合法时选单 2、接着被小王压过。它们显示资源支出及真实取舍；隐藏手牌和反事实结果未知，不能认定哪一步导致败局或模型未考虑成本。

四个关键请求均展示 pass，但没有与所选应手组成直接关系；第 60 步已有单 10/单 2 的资源关系，说明单纯增加文字未必改变动作。M5 历史 pass 提示已出现在本局请求，已知手牌搜索不适用。`docs/NEXT_PROMPT.md` 是单个 M6 应手净得失 Coding 任务：统一比较出牌收益、拆组/资源成本及 pass 的放弃与保留，用完整合法牌局和反例验收，不做本局牌点硬编码或模型成功后的强制改牌。第 20 局目录的 manifest 为结果未确认、决策文件为空，不作为本轮算法证据；未读取其局面正文，也未改动任一现场目录。规划仅提交文档；下一次真实 Botzone 仍由所有者自行操作。

以下“M5 已交付，下一步只读效果观察”为第 19 局审计前快照，以本节为准。

## 2026-09-29 当前交接：M5 已交付，下一步只读效果观察

HEAD `b0e18e12db85bfc55942891b0d65201aed9d1339` 的 M5 机制经规划独立复审：公开 pass 仅作为可撤回的候选相关线索；公开守恒唯一确认手牌的残局由引擎做有界多步搜索，只有完整求解的唯一保胜动作可在模型前直选。定向 21 项、主规则 43 项通过；20 个引擎与 RuleBased 完整续局 seed 的 79 个适用状态中 75 个求解、4 个预算回退，35 个多候选小残局逐动作值与引擎独立参考一致。Coding 报告全量 989 项通过、1 项跳过，规划未重跑全量。真实 DeepSeek/Botzone 效果未评估，结论为 `inconclusive`，不回推历史负局根因。

当前没有 Coding 任务，M5 Prompt 已撤下。所有者自行进行真实 Botzone 页面及 connector 操作；规划在收到后续逐局 evidence 时只读审计命中、动作、ACK、结果和条件差异，不启动、停止或清理现场运行。若具体问题可复现，再制定单个有算法收益目标的 Coding 任务。`D:\VsCodeProject\BotzoneWorkspace` 和个人 workspace 本轮均未访问或修改。

以下“M5 记牌推断与有界推演待 Coding”为交付前交接快照，以本节为准。

## 2026-09-29 当前交接：M5 记牌推断与有界推演待 Coding

所有者明确要求改进多人局 pass 线索与公开已知手牌残局的本地多步推演，而不是只等胜率测试。当前 `CardBeliefState` 保存 `pass_count`，硬约束层故意不将 pass 当作无牌；M3 E1 是外部未分配牌池上界，E2 只做即时应手；现有 1–8 张分组是条件性本家拆牌，非轮流博弈。根因仅定位到这些能力缺口，不能归因上一局负局。`docs/NEXT_PROMPT.md` 是一个完整 M5 算法任务，要求软推断、真实规则下有界多步搜索、完整局面与请求验收，保留 DeepSeek 对未知与真实取舍的决策权。

“优化3”与本仓库同 checkout、当前空闲；它上一轮因 `NEXT_PROMPT.md` 不存在而正确停止，没有待提交业务改动。规划将沿用该 Coding 对话执行新 Prompt，无须新建；所有者提供的独立事实核对与反补丁原则已在该对话中。规划不运行 Botzone、connector、浏览器，也不访问现场 evidence；M4 效果仍 `inconclusive`，首局留证验收结论不变。

以下“新版首局完整留证”为 M5 确定前快照，以本节为准。

## 2026-09-29 当前交接：新版首局完整留证已现场核对

所有者亲自完成一局；规划只读审计 `D:\VsCodeProject\BotzoneWorkspace\games\2026_9_28_23-56-54_000018`。索引容量 10，9 条旧摘要加 1 条完整局；manifest 为 `finished/local_team_loss`、留证完整。26 条观察、26 次决策均有合法 ID 与 ACK 关联；13 份请求 body 与 metadata 摘要、模型名、候选/推荐闭环相符，13 次模型完成均为 success，另 13 次为本地快捷决策。时间线 1 条终局事件，最后阶段为 `platform_result`。额外无动作 ID 的 ACK 不算出牌。规划没有操作 connector、页面、模型或修改 evidence。

留证首局现场验收完成；旧摘要无法恢复细节，`request_prepared` 不证明网络送达，公开历史只代表 connector 已观察范围。真实长期重连与第 11 局轮换待自然试局核对。无待 Coding Prompt；接下来恢复 M4/记牌效果观察，遇到具体问题先审计该局证据再规划业务修复。

以下“待所有者现场验证”为首局验收前快照，以本节为准。

## 2026-09-28 当前交接：逐局留证实现已交付，待所有者现场验证

Coding `a870c6b6aff82e9fcb188ba49bdc60a0b8242e7e` 已将所有者自启的固定 workspace 连续批次接到新版 `games/<本地时间>_<单调局号>/`，保存逐动作公开观察、本家手牌、合法/展示候选、决策来源与 ACK、终局或未确认状态，以及传输调用前准备的完整模型 JSON 请求 body。最近 N 局只轮换新版逐局目录，默认 10；旧摘要仅 `summary_only` 导入，旧批次和 `runtime/v2/runs/` 内部运行目录仍保留。`request_prepared` 不证明模型服务端已收到请求。

规划独立定向 29 项通过、1 项符号链接环境跳过；Coding 报告全量 983 项通过、1 项跳过。未运行真实 connector/模型，也未读或修改现有现场 evidence。下一步由所有者自行启动新版和建桌，交付一局新目录后规划只读核对。没有待 Coding 的下一步，已执行 Prompt 撤下；如现场发现具体证据缺口，再给 Coding 一项明确修复。M4 策略效果仍 `inconclusive`。

以下“最近十局逐局留证”为交付前快照，以本节为准。

## 2026-09-28 当前交接：所有者要求真正的最近十局逐局留证

规划只读确认固定 workspace 的 `manual-batch-20260928T021001Z-...` 与 `manual-batch-20260928T115001Z-...` 分别是北京时间 10:10、19:50 的两次脚本运行目录，不是两局；`state` 的哈希名是内部会话查找键。现有滚动索引容量 10、保留 10、累计 17，滚动对象仅为结果摘要。批次没有启用 history/decision trace，也没有保存模型请求，不能靠旧文件重建四局具体选择。所有者确认下一版要保存完整模型请求 body 和逐动作证据，每局以本地时间命名，跨启动仅保留最近 10 局目录，异常局也留。密钥、连接 URL、Header、模型自由文本及异常正文不保存。旧批次尚可能运行；规划未停止进程、修改或清理任何 workspace 文件，旧目录原件须保留。

下一项 `docs/NEXT_PROMPT.md` 为一次完整 Coding 任务：新版固定 workspace 的 `games/` 内按局存证，安全轮换最近 N 局，旧结果仅可标记 `summary_only` 导入，不能补造历史动作；运行状态文件与用户可查逐局证据隔离。Coding 禁网测试，不运行现场；完成后所有者自行重启脚本和操作页面，规划只读验收。M4 输入已交付，实际策略效果尚不确定。此留证修复先于下一轮有解释力的算法试测。

以下“M4 已交付，等待所有者效果观察”为本轮留证缺口提出前的交接快照，以本节为准。

## 2026-09-28 当前交接：M4 已交付，等待所有者效果观察

Coding `04f694b1b08677661699fdd9cf76e9b4f87d2f89` 已交付三类 M4 公开候选关系及默认模型前提示，保留 ≤80 候选、关系双端和原始合法 ID/source=`model`。规划独立复跑相关 68 项及主规则 43 项通过，提交差异检查通过。Coding 8 次 `deepseek-flash` 同状态请求零重试，四组中两组选择变化、两组未变；策略收益尚无结论，现场四局也不能据此归因。

全量 971 项有两项旧批次进程探测测试失败；规划复跑单模块仍是两项，现场一个真实 connector 的 venv 父子进程正在运行，故测试探测 `connector_running`。规划未停止 connector、未访问或修改现场证据；全量绿灯仍待空闲环境确认，但没有这两项指向 M4 算法回归的证据。现阶段不安排新的 Coding 任务，已执行 `docs/NEXT_PROMPT.md` 撤下。所有 Botzone 页面与 connector 操作由所有者自行完成，规划收到后续动作与结果时只读审计；M4 模型前输入已交付，效果仍 `inconclusive`。

以下“M4 现场反例驱动算法修正”为交付前交接快照，以本节为准。

## 2026-09-28 当前交接：M4 现场反例驱动算法修正

所有者 M3d 后自操作四局，规则判断 1 胜 3 负；固定 workspace 四条低敏终局记录平台口径同为 1 胜 3 负，四局均 `finished/qualified`，阶段记录未见模型 timeout。批次仍在运行，规划只读核对，未操作页面、connector、证据文件或个人 workspace。没有逐动作 trace，不能从批次记录还原模型理由。第 2 局截图和所有者观察明确打出 `333QQ` 拆五张 3 炸、耗掉 QQ，后来又打四张 7 加红桃 2 的五炸；第 3/4 局由所有者观察到队友单 4 时未接单 10、对手单 5 时用 2 而未用 8。不要再要求所有者提供已观察动作的证明。

规划复算一组与截图牌型相符但非现场原局的完整合法牌池：112 原始/80 最终候选；自然四张 7 和使用红桃 2 的五张 7 均展示，但现有关系无跨长度成本对照，三带二与保留自然五炸的损失也不成对表达，跟牌高低单的比较缺位。近似状态的 `333QQ` 未进入最终 80，不说明现场缺席。当前下一项是一个实质算法 Coding 工作包 `docs/NEXT_PROMPT.md`，覆盖三类场景、正反例、候选与默认 factory 输入、少于 10 次的同模型请求；DeepSeek 保留最后取舍，禁止按现场牌点/ID 特判或成功后改牌。四局不构成胜率因果结论。Coding 不运行真实 Botzone，完成后规划复审再决定下一轮所有者人工试测。

2026-09-28 最新交接：M3d Coding 提交 `06d45f0fb47d879538f8b2356e5a8ee9257261d3` 已把公开实体应手目录和单观察内的候选画像复用；规划独立定向 31 项通过，seed `0/1` 与上一版相同候选的 M3 摘要逐字一致，冷测组装 `6.489/3.589s → 0.870/0.580s`，容量排除与 E2 摘要也逐字一致。Coding 报告全量 965 项和五轮禁网 fake 请求通过，无真实 DeepSeek/Botzone。已见本地时延回归关闭，但 M3c 四次真实请求仅一组选择变化且条件续局无优势，整体算法效果仍 `inconclusive`。下一步为所有者自行进行约十局普通试局后由规划只读审计；当前没有 Coding 任务，已删除完成的 `docs/NEXT_PROMPT.md`。Botzone 页面/connector 由所有者操作，规划不碰两个 workspace 或旧证据；若得到具体可复现算法缺口，再制定下一份 Coding Prompt。

以下“M3c 资源比较与本地时延回归”为历史交接，以本段为准。

2026-09-28 最新交接：Coding 的 M3c 提交 `b8e40a80a81559a85bd07279d3e23a079fe4299e` 已让公开应手资源上界区分单张 3/A，并在四次零重试 `deepseek-flash` 请求中观察到 seed `0` 一组合法单张选择变化、seed `1` 选择相同；固定规则条件续局无优势，策略收益仍 `inconclusive`。规划独立定向 29 项通过，但同状态禁网冷测显示记牌组装从上一版约 `0.084/0.062s` 增至 `6.401/3.497s`（seed `0/1`，80/39 候选）；简化 factory 整次调用约 `6.652/3.576s`。Botzone 决策预算从请求到达起计，故下一项 `docs/NEXT_PROMPT.md` 是单个 M3d Coding 工作包：保留资源与候选事实，复用公开牌域应手计算以收回本地时延，并同机禁网对照。规划只改 docs；不发真实模型请求、不运行 connector 或操作两个 workspace。速度修复后再决定所有者试局与算法效果复审。

以下“M3b 逐家应手分类”为历史交接，以本段为准。

2026-09-28 最新交接：Coding 的 M3b 提交 `309927ff5e8f138a8f0745eb2110e060632c029c` 已交付逐家公开容量/应手分类、推荐锚定及同型候选对照；规划复跑定向 26 项通过，Coding 报告全量 960 项通过。真实 DeepSeek 请求 0，策略收益仍未证实。规划独立发现默认摘要仍把 seed `0` 起局的单张 3 与单张 A 对三家都写成相同的“可能单张/炸弹”，没有展示高于它们的公开实体资源差异；候选选对照的排序也未使用逐家应手结果。下一项 `docs/NEXT_PROMPT.md` 是一个有业务改动与有限真实选择验证的 M3c 工作包，不是纯资格检查。DeepSeek 保留合法候选的最终取舍，未知归属不变成持牌概率或确定事实。规划只改 docs，不碰两个 workspace 或现场 connector。

以下“`b5daf9f` 已修复牌型校验”为历史交接，以本段为准。

2026-09-28 最新交接：`b5daf9f` 已把记牌器天王炸/连对长度与引擎真值对齐；规划独立定向 15 项通过，合法四王出牌后的摘要从先前 E0 恢复为 E1。Coding 报告全量 957 项与同模型 8 次零重试请求通过；四个冻结状态的 baseline/current 模型 ID 均未变化，两个残局的条件 RuleBased 续局都为 loss。M3 的输入准确性已交付，策略收益 `inconclusive`，不因这四对结果直接回退或宣称有效。下一项 `docs/NEXT_PROMPT.md` 为 M3b 整体记牌器算法任务：逐个玩家的公开余牌容量对应手可行性作保守判断，改进同牌型及跨牌型实际候选对照，压缩低价值总池文字，并用有反例的引擎局面做有限真实选择对照。旧四组不简单重跑，DeepSeek 仍是取舍决策者。规划本轮仅改 docs，不访问两个 workspace、不操作 Botzone。

以下“`e10057d` 后的牌型校验复审”为历史交接，以本段为准。

2026-09-28 最新交接：`e10057d` 已接入默认 M3 公开记牌事实与展示候选比较，禁网 Request/source 闭环成立；Coding 报告全量 953 项通过、真实模型请求 0，规划独立定向 11 项通过，动作质量仍未知。规划以真实引擎四张天王炸出牌复现新记牌摘要错误降为 E0：`card_tracker` 将 `joker_bomb` 长度误写为 2，另将固定 6 张连对宽松接受为 6 张以上偶数张。下一份 `docs/NEXT_PROMPT.md` 为一个 Coding 任务，先修两处规则长度映射并做引擎状态回归，再做最多 8 次、零重试、相同 `deepseek-flash` 的代表状态改前/改后选择对照。评测进程的 `deepseek-v4-flash`/`deepseek_enabled=false` 不是人工 Botzone 批次配置证据：批次启动器明确覆盖模型为 `deepseek-flash`，显式 deepseek factory 不依赖该布尔标志。不得改 `.env`，不得让此配置差异变成另一纯检查阶段。本轮规划未改代码/tests，未访问两个 workspace 或启动现场。

以下“整体记牌器算法优化”为实现前历史交接，以本段为准。

2026-09-28 最新交接：所有者明确下一轮主线是**整体记牌器算法优化**，一对一明牌只是其中一种能力验收。规划从源码独立复审：默认 `CardTracker` 已读取公开历史，但只输出外部点数总量/炸弹可能清单，无法归属到具体对手或比较当前候选出后的接管与留牌；“当前最大牌”与“除上述可能外不存在其他炸弹”措辞有误导性。J 系列已有公开实体牌池、逐玩家事实、硬归属和受控残局分配，但默认 Botzone factory 的 confidence 消费关闭；旧通用边际概率 prompt 在 24 对模型选择代理中未观察到质量收益，不应直接开启。最近十局缺少逐动作 trace，所有者的 `445566` 连对选择是近似场景需求，不是已证实的单局 bug。下一项 M3 Coding 任务见 `docs/NEXT_PROMPT.md`：改进默认记牌决策输入，并用完整合法牌局及反例做前后对比；DeepSeek 仍决定未证实的策略取舍。规划未改代码/tests，未碰两个 workspace 或现场 connector。

2026-09-28 最新交接：所有者完成同一人工批次第 6–10 局，按其可见名次记负、平、平、平、平。固定 workspace 批次 `manual-batch-20260928T021001Z-52825b53f95cb2ed` 的新增五条平台分数分类为负、负、胜、负、负；滚动总序号 9–13 连续。当前最近 10 条是本次十局的总序号 4–13，三个旧导入项已移出；十局平台分类合计 4 胜 6 负，所有者规则名次判断为 7 平 3 负，后者没有逐局名次证据可独立复算。十局均到 `finished/qualified`，本家响应均获 ACK；第 6–10 局模型均完成 success、未见模型 timeout 或 poll 传输失败。批次尚运行，completion audit 为空属未结束状态。规划只读复核；没有启动/停止 connector、修改 workspace 证据或访问个人目录。连对 `pair_straight` 在引擎规则、Botzone 编码和模型候选中存在；禁网默认 factory seed 0 原始/最终候选连对为 5/5、总候选 224/80。人工批次未启用逐动作 trace，不能判定这十局是否曾有可出连对及模型为何未选；不把未见牌型直接定为 bug。当前无已证实 Coding 修复目标，`docs/NEXT_PROMPT.md` 继续撤下。第 7–10 局平台结算标签待所有者确认，后续再按具体可复现局面推进算法任务。

以下“前五局记录完整，平台胜与规则平分列”是这次十局汇总前的阶段快照，以本段为准。

2026-09-28 最新交接：所有者新跑五局；固定 workspace 当前批次 `manual-batch-20260928T021001Z-52825b53f95cb2ed` 的五条逐局记录及滚动总序号 4–8 均为本队胜、负、负、胜、胜。所有者澄清第 1、4、5 局 Botzone 结算实际显示“胜”且只加 1 分，其“平”是按头游与末游同队的单局名次判断；平台标签与本地记录一致，规则平须单列，低敏文件未保存四席名次。规划仅只读检查滚动文件、逐局 JSONL 和低敏阶段事件，未启动/停止 connector、修改现场文件或读取个人 workspace。五局都到 `finished/qualified`，无未确认局；第 2 局 13 次模型 success、最长模型等待约 111.1 秒，至对应 ACK 约 118.2 秒，另有一次 poll 传输失败后恢复；第 3 局 9 次模型 success，未见模型超时或传输失败。第 2、3 局页面曾给出手动出牌选项，动画/跳过本家原因尚不可由阶段日志确认。前五局记录可用，所有者可继续五局；新增恰好五局后当前五条仍在默认最近 10 条窗口，旧导入三条会移出。当前无 Coding Prompt，后续按平台与名次两种口径分别审计，再恢复算法复审。

以下“滚动记录已交付，待现场验收”是前一阶段快照，以本段为准。

2026-09-28 最新交接：`1844cb2ac2e1ed6ae46480eb610dad793a08c46c` 已实现所有者自启连续试局的跨启动最近 N 条结果窗口（默认 10）、旧批次可核验结果幂等导入、本地分钟安全记录键，以及 idle/局间持续轮询和 `network_error` 退避。规划核对提交范围与差异检查，独立相关禁网测试 27 项通过；Coding 报告全量 947 项通过。未启动真实 connector、Botzone、联网预检或 DeepSeek；未读取、迁移或修改两个 workspace 的现场证据。当前没有 Coding Prompt，`docs/NEXT_PROMPT.md` 已撤下。下一步由所有者先停止仍运行的旧批次，再自行启动新版并确认页面连接、跨 10 局及重启续记；多个旧批次候选时按固定错误类别用 `--import-from <精确批次目录名>` 指定。近期中途终止及“等待重连”具体原因待所有者交付证据后只读审计，不预断为模型超时或 connector 故障。现场验收后回到算法能力改进与效果复审；M2 总体效果仍 `inconclusive`。

以下“所有者确认连续试局脚本”是实现前阶段快照，以本段为准。

2026-09-27 最新交接：所有者确认连续试局脚本须在一次启动中持续轮询，直到其主动 Ctrl+C/关闭窗口；最近 N 局窗口默认 10，跨脚本重启继续写，不清空，满额后移出最早局。新版第一次要把当前旧批次可核验的逐局结果纳入，旧目录原样保留。新局本地时间展示形如 `2026_9_27_23:33`，Windows 文件名用 `2026_9_27_23-33` 加同分钟序号；旧结果无逐局时间，不编造。`docs/NEXT_PROMPT.md` 现为持续连接、跨启动滚动区、幂等旧批次导入和异常局未知结果的完整 Coding 任务。当前旧批次可能仍在运行，规划没有读取或修改其证据；近期“等待重连”后恢复的中途终止原因未定。

以下“单次批次滚动结果”是最终需求确认前的阶段快照，以本段为准。

2026-09-27 最新交接：Coding 提交 `29b8027` 排除本机同次 venv Python 父进程，所有者确认 Botzone 已连接。人工一局中途终止，页面“等待重连”后恢复“已连接”，尚无阶段证据复审，不归因 120 秒倒计时、DeepSeek 或 connector。规划只读源码确认当前默认 `--games 10` 会在 10 个符合条件的完局后自动停机，`game-results.jsonl` 只追加，不会第 11 局覆盖第 1 局；无确认完局事件的异常局可能不进入逐局结果。所有者要持续运行、可调容量、仅保留最近 10 条逐局结果，已写成新的 `docs/NEXT_PROMPT.md` Coding 任务。当前批次仍在运行，规划未访问或改变其证据；新代码只在所有者下次启动后生效。

以下“venv 自拦截修复”是本次连接确认前的交接快照，以本段为准。

2026-09-27 最新交接：Coding 提交 `fe507d5` 将 connector 与启动器模块名分开，所有者新截图却显示 `batch_launcher_already_running exit=2`，Botzone 未连接。规划独立检查提交范围与 `git show --check`，复跑 `tests.test_botzone_manual_batch` 14 项通过。只读进程检查发现本机 `.venv` Python 有父、子两个 `python.exe`；安全 `-c` 模拟批次命令行并调用生产探测函数，复现 `batch_launcher_running`。当前 guard 只排除子 PID，故本次启动链自拦截是有证据的修复目标。`docs/NEXT_PROMPT.md` 已收窄为排除本次 venv 包装进程，同时继续阻止独立第二批次和真实 connector；Coding 禁网修后由所有者亲自验收页面连接。旧报错根因仍不反推，两个 workspace 旧证据未碰。

以下“模块前缀误匹配”是本次新截图前的交接快照，以本段为准。

2026-09-27 规划纠正：所有者要求以排除法推进，不先执着查清两次现场报错的唯一根因。已证实 `manual_batch.py` 的 `-m integrations.botzone\b` 模块前缀同时匹配启动器 `-m integrations.botzone.manual_batch`。当前 `docs/NEXT_PROMPT.md` 已改为最小 Coding 修复：收紧匹配、保留真实 connector 并发保护、少量禁网测试，随后由所有者亲自启动验证；若仍失败再补低敏进程诊断。历史报错瞬间命中的进程仍未知，不能提前宣称修复已解决现场连接。

2026-09-27 最新交接：所有者再次运行 `run_manual_botzone_batch.cmd`，仍报与前次相同的 `connector_already_running`，刷新 Botzone 无“已连接”。规划立即按源码匹配规则只读扫描，当前 `matching_count=0`；同一 `.venv` Python 调用探测函数返回 `connector_absent`。均为失败后的状态，不能断言错误发生时无竞争进程。源码的 `-m integrations.botzone` 前缀匹配可覆盖 `-m integrations.botzone.manual_batch`，存在启动器被归为 connector 的风险，是否导致本次失败待证。恢复 `docs/NEXT_PROMPT.md` 单个 Coding 修复任务：低敏记录 guard 命中的 PID/类型、禁网复现并修正确认误判，真实并发 connector 仍要拒绝，所有者随后亲自做页面连接验收。规划没有运行/停止真实 connector、Botzone 或 DeepSeek，也没有碰两个 workspace 旧证据。

以下“首次可见进程占用类别”是复发前的交接快照，以本段为准。

2026-09-27 最新交接：`905b246` 已让批次 `.cmd` 在退出时显示固定类别并等待。所有者重试截图给出 `batch_error category=connector_already_running exit=2`，Botzone 未显示“已连接”；当次在创建批次目录和预检之前被进程占用保护挡住。规划按代码的匹配规则事后只读检查，当前没有匹配的 Botzone Python/py 进程；无法反推出截图时进程身份，不能判断是真冲突还是误判。未停止或启动 connector，未碰旧 evidence。下一步所有者重启现有脚本并在页面核对连接；若同类错误重现，先保存报错时进程证据再决定 Coding 修复。当前无新 Coding Prompt，已执行的 `docs/NEXT_PROMPT.md` 撤下。算法主线待试测链路可用后继续，旧中途停牌根因仍未定。

以下“窗口闪退”是本次可见错误类别出现前的交接快照，以本段为准。

2026-09-27 最新交接：所有者实际双击 `run_manual_botzone_batch.cmd` 后窗口闪退，Botzone 未显示“已连接”。规划只读确认新 `.cmd` 不像旧单局 `.cmd` 那样退出后等待；`--help` 能返回，当前进程探测与固定 workspace 根属性检查通过，固定 workspace 当前无新 `manual-batch-*` 子目录。具体早退边界未证实，不能归为模型超时或中途停牌。当前 `docs/NEXT_PROMPT.md` 是一个禁网 Coding 修复任务：让错误/退出类别可见，定位并修正早退，验证单 connector 跨 idle 与局间持续运行，保留固定 workspace 新子目录和旧证据；之后所有者亲自启动并确认页面“已连接”。规划不改业务代码，也未运行真实 connector/DeepSeek/Botzone。旧 M2 效果仍 `inconclusive`。

以下“脚本已交付、暂无 Coding Prompt”为问题报告前的交接快照，以本段为准。

2026-09-27 最新交接：`4afa7fc` 已提交所有者自启连续 Botzone 批次脚本、ACK 后逐局低敏结果与禁网测试；规划复核提交仅含 8 个 Botzone/脚本/tests 文件，`git show --check`、新增 14 项和主规则 39 项均通过，Coding 报告全量 917 项通过。默认最多 10 局、可调，一次前台 connector 连续运行、固定 `D:\VsCodeProject\BotzoneWorkspace` 新子目录留证、子进程 `deepseek-flash`、零网络预检与 stage trace；history/decision trace 关闭。真实 Botzone/DeepSeek 均未由本轮运行，两个 workspace 旧证据未由规划访问或改动。当前无新的 Coding 任务，旧 `docs/NEXT_PROMPT.md` 撤下；所有者可自行决定何时启动并逐局操作，Codex局后只读审计。M2 旧 32 槽仍 `inconclusive`、旧授权不可续跑，旧 `platform_error` 根因未知。下一轮算法任务由具体试局反例或新能力目标确定。

以下“十局脚本待交付”为上一阶段交接快照，以本段为准。

2026-09-27 最新交接：`15041efb` 已交付 5–8 张残局条件性路线输入。规划确认提交范围、`git show --check`，独立复跑 32 项残局/路由及 39 项主规则均通过；Coding 报告 903 项全量通过、四状态双版本 8/8 真实请求成功且零重试，四对动作相同。输入能力已实现，动作质量/胜率收益未证实。当前 `docs/NEXT_PROMPT.md` 已切为所有者自启十局 Botzone 脚本的禁网 Coding 任务：固定 `D:\VsCodeProject\BotzoneWorkspace` 新子目录留证，一次启动持续运行，默认最多 10 局可改，所有页面和 connector 操作由所有者完成，Codex 只在事后审计。现有单局 history/decision trace 不得跨局共用一个文件；本任务至少保证逐局低敏结果、聚合审计及阶段事件，不把完整逐局牌谱扩建设成门槛。两个 workspace 的旧证据未访问或改动。旧 M2 32 槽授权不能续用，效果仍 `inconclusive`；旧 `platform_error` 根因未知。

以下“十局脚本暂缓”是上一阶段交接快照；当前已进入脚本交付任务，以本段为准。

2026-09-27 最新交接：所有者明确将十局 Botzone 试测归为支线；以后自己完成所有页面与 connector 操作，Codex 只做局后审计。先前 `30c2bf5` 的新十局脚本/多局留证任务**暂缓而非取消**，尚未改业务代码；当前算法任务处理后、下次真实 Botzone 试测前，应交付供所有者启动的脚本：持续运行、不逐局暂停，默认最多记录 10 局且可改，旧证据不覆盖。十局胜负比例作方向性观察，列明有效完局、异常及条件差异，不以严苛正式实验门槛阻挡算法迭代，也不写成因果证明。当前 `docs/NEXT_PROMPT.md` 是扩展 5–8 张公开残局出后路线比较的算法任务；DeepSeek 保留合法动作最终决策权。M2 原 32 槽仍在第 1 槽后停止，绑定工具问题留待实际复用时修；旧授权不可续跑。两个 workspace 及旧证据均未触碰。

以下“所有者自操作十局批次”是先前优先级的规划快照；任务保留，执行时机以本段为准。

2026-09-27 所有者最新方向：评测器离线 `offline-m2` 与真实配置模型名不同，不等于两次真实版本用了不同模型；实际配置未读。下一项改为 Coding 实现固定 `D:\VsCodeProject\BotzoneWorkspace` 下的**所有者自操作十局批次脚本**：所有者启动一次后在 Botzone 页面逐局手工操作，connector 连续运行、不逐局暂停，默认最多完成 10 局且可改，测试模型在脚本子进程统一为 `deepseek-flash`。旧固定 workspace 证据原样保留，新批次只写全新子目录，每局独立 history/ACK trace/低敏审计；现有单局 recorder 不可直接共享一个文件。Coding 只做禁网实现和测试，真实试局由所有者启动，结束后 Codex 只读审计。M2 32 槽在第 1 槽后已停、效果 `inconclusive`、旧授权不可续用；未来重启需先修复绑定并另定预算。`docs/NEXT_PROMPT.md` 为当前执行任务。

以下 `99d31b0` 交接是前一阶段快照，以本段为准。

2026-09-27 `99d31b0` 停止后交接：Coding 报告冻结 8 状态、16 条禁网资格仍 ready；本轮获批 32 槽仅第 1 槽 `opening_dense_1 / baseline / repeat 1` 发出 1 次真实请求、success、0 重试，ID `40` 在展示候选内且 source=`model`，随后 `attempt_offline_binding_mismatch_stopped`，其余 31 槽未执行、无续局比较。规划检查提交仅含评测器/测试、Git clean，独立复跑新增模块 16 项；发现 `request_utf8_bytes` 仍在离线占位模型名与真实配置模型名之间严格比较，禁网合成差异可复现同一停止分类。但原始停止结果未给出字段，不能声称已确认唯一原因。M2 继续 `inconclusive`，M1 生产版保留。当前 `docs/NEXT_PROMPT.md` 仅安排禁网绑定修复和低敏分类，真实请求 `0`；旧授权已随停止结束，后续完整 32 槽须重新规划、明确授权。两个 workspace、`.env`、封板不动。

以下 `2fafc82` 离线复审交接为上一阶段快照，以本段为准。

2026-09-27 `2fafc82` 离线复审交接：Coding 已提交 M2 扩大评估器与测试，报告 8 个冻结生产状态、双版本 16 条禁网 Request 资格全部通过，真实 DeepSeek 请求 `0`、重试 `0`，全量 895 项通过。规划核对提交仅含评测与测试、Git clean、授权/停止路径，独立复跑新增模块 15 项通过；规划未复算全部跨版本资格。两个密集开局的参考动作可见性和关系双端召回改善是输入证据，模型效果仍 `inconclusive`，M1 生产版暂保留。**32 次真实请求专项授权尚未给出**；下一份可执行说明见 `docs/NEXT_PROMPT.md`，只有获明确授权才运行真实阶段，不拆小任务、不增重试。旧 `platform_error` 根因、119 秒现场期限余量未定；两个 workspace、`.env`、封板标签/bundle 保持原样。

以下 `8910669` 交接是上一阶段快照，以本段为准。

2026-09-27 `8910669` 复审交接：规划检查新增评测工具与测试，独立复跑 11 项通过；Coding 报告四个冻结状态双版本离线资格、8/8 真实 DeepSeek 请求 success、0 重试，关联 207/主规则 39/全量 880 项通过。两密集开局的候选关系召回明显改善，四对模型选择有 3 对相同；seed 5000 当前钢板对固定 RuleBased 续局代理优于封板三带二，但单状态不能证明总体质量。耗时方向混合。此前 `urlopen` 包装器的 `TypeError` 在发送前已修正；另一项跨版本 `reference_visible` 汇总已按独立离线资格核正。当前 M1 版本暂保留，M2 首轮 `inconclusive`。`docs/NEXT_PROMPT.md` 是一次性 8 状态×2 版本×2 重复、最多 32 次新增真实请求的扩大评估；依 `AGENTS.md`，10 次或更多须所有者明确授权，授权前只做禁网准备，不拆多个 8 次任务。封板标签/bundle、两个 workspace 均不动；旧 `platform_error` 根因未知。

2026-09-27 `0e6f5c7`、`cecf7cd` 复审交接：规划审阅两次生产/评测 diff，独立复跑 8 项定向测试通过；Coding 报告全量 869 项、六组各 200 局默认 factory 禁网复算通过。前五组自然对子/单张关系双端可见从 211–218 对提升到 366–373 对，通配资源仅小幅改善，最终候选仍不超过 80；这些是输入召回，不是模型质量。公式未改，六组直选 `36/1200`、对子/三张 0，本地开局快速覆盖目标仍未达。H3-A9 `opening_2` 的 seed 921 step 0、74/49 是关闭公式且冻结旧关系代表的反事实行，已从默认生产汇总隔离。当前进入 M2 同状态模型主导效果评估，直接执行 `docs/NEXT_PROMPT.md`；最多 8 次真实请求、零自动重试，默认不跑 Botzone/live、不碰两个 workspace，不改 `9/26_v0` 标签/bundle。旧 `platform_error` 根因未知。

2026-09-26 `3a45057` 复审交接：规划独立复跑 48 项相关测试通过；Coding 报告全量 867 项通过，所有外部请求和两个 workspace 访问为零。完整开局公式仍为 `25/800`、对子/三张直选为零；密集 seed 0 的默认 factory 候选从三带二 43 个降到 14 个，多牌型比较空间明显增加，但对子/单张和通配资源完整关系仍常缺双端，不能据此声称模型质量或胜率收益。H3-A9 `opening_2` 固定回 seed 921 step 0、74/49，因该状态生产公式直选顺子，其模型候选请求明确属于关闭公式后的反事实评测。M1 未封板；`docs/NEXT_PROMPT.md` 是同一工作包的关系预算与模型前比较续作，之后进入 M2 同状态效果复审。不触碰 `9/26_v0` 标签/bundle，不派 live、不轮换两个 workspace。旧 `platform_error` 根因未知。

2026-09-26 `75833e4` 复审交接：Git clean，`9/26_v0` 标签与仓库外 bundle 保持原样。规划复跑 50 项相关测试并独立重算四组各 200 个完整起局：当前直选 `8/8/4/5`，对比封板后基线 `7/6/4/5`，仅新增 3 次顺子，0 次对子/三张；800 局中 794 局无唯一原始 ID Pareto 前沿。默认 factory 的模型前家族代表与关系成对保护有局部改善，但尚无实质算法效果证据。H3-A9 `opening_2` 已从 step 0、74/49 变为 step 4、3/3，不可当作同状态前后效果。当前 `docs/NEXT_PROMPT.md` 是**同一 M1** 的生产算法续作及评测可比性纠偏，不派 Botzone/live、不触碰两个 workspace；M2 仍待真正有意义的算法变化后再进入。旧 `platform_error` 根因未定；下文“两次个人局正常完赛”仍是有效现场事实，但不是本轮算法收益证明。

2026-09-26 当前交接：`9d6288d` 的 119 秒 Botzone DeepSeek 整次决策期限已通过禁网实现验证；所有者在 120 秒桌下亲自完成两次分开的正常个人局，规划归档并复核 16/30 条本家 canonical ACK 决策、13/20 次模型 success、0 fallback、正常终局与完整阶段顺序。归档为 `D:\VsCodeProject\GuanDanManualEvidenceArchive\20260926-172058-119s-first-game` 和 `D:\VsCodeProject\GuanDanManualEvidenceArchive\20260926-181002-119s-second-game`，两局 7 份文件均与原件大小/哈希一致；第二局原个人 workspace 未改。M0 的本轮链路放行门槛满足，当前执行 `docs/NEXT_PROMPT.md` 的 M1 来源化开局、多牌型候选、条件化 B/C RAG 与 DeepSeek 模型前比较 Coding 任务，默认禁网/离线，不启动新 Botzone 局、不轮换个人或固定 workspace；之后做 M2 算法效果复审。旧 `platform_error` 根因仍未定，两局均未触发 live timeout/fallback，119 秒贴近 120 秒桌面倒计时。再现停牌时保留新证据并回到同一 M0 问题阶段。下文“当前执行 M0 Coding 任务”是历史快照。

2026-09-26 复发后的交接：当前执行 `docs/NEXT_PROMPT.md` 的 M0 Botzone DeepSeek 整次决策期限 Coding 任务。项目所有者报告本家再次在倒计时结束未出牌，另有两局开局不出牌，并将个人 Botzone 桌延时设为 120 秒。已核验的异常局一局停在 `model_enter`，另一局虽有 10 条本家决策 ACK、8 次模型 success，最终仍 `platform_error`；两者不能合并为“已证实模型超时”。原始个人证据分别逐文件验哈希复制到 `D:\VsCodeProject\GuanDanManualEvidenceArchive\20260926-153323-midgame-stall` 和 `D:\VsCodeProject\GuanDanManualEvidenceArchive\20260926-154450-teammate-lead-platform-error`；不要启动会覆盖现有个人 workspace 的脚本，不要触碰固定 Codex workspace。`DEEPSEEK_TIMEOUT=120` 是单次读取超时，不是整次决策期限。当前先做小于 120 秒桌面倒计时的模型期限、合法回退和禁网验收；随后由所有者自行试局，规划按阶段、响应和 ACK 复审。M0 放行后恢复 `docs/OPENING_ALGORITHM_PROMPT.md` 的 M1 算法实现，再做 M2 效果复审。下文“暂缓 M0、立即 M1”是历史快照。

2026-09-26 最新交接：项目所有者已亲自完成一局个人试测；规划只读复审确认 `local_team_win` 正常完局、13 条合法 ACK 决策与 audit 守恒、7 次模型调用均成功，最长约 59.3 秒。旧异常局中途停牌根因仍未知，不能据此归因模型超时或称故障已修复。按所有者新的优先级，M0 调查暂缓、不再阻挡禁网离线的 M1 算法工作；当前直接执行 `docs/NEXT_PROMPT.md`，无需先让所有者再人工操作。M1 不启动 Botzone、不轮换个人证据，完成后再做 M2 效果复审。若现场同类问题复发，保留当局证据并回到 M0。下文此前“等待个人验证局”的句子是历史快照。

2026-09-26 最新规划复审：`f5fb88a` 的低敏阶段观测已接入个人启动器并通过独立禁网/合成验证；它没有修复或定位旧局中途停牌。M0 仍在进行，当前等待项目所有者决定是否允许下一次个人试局轮换 `D:\VsCodeProject\GuanDanManualWorkspace` 的旧证据；规划与 Coding 均不代为启动。所有者新局结束后直接按 `docs/NEXT_PROMPT.md` 做只读证据复审；异常时保留目录并暂停再启动。根因未知的放行条件是两次分开的正常完整试局均有阶段证据和规划复审；随后恢复 `docs/OPENING_ALGORITHM_PROMPT.md` 的 M1 算法实现，再做 M2 效果复审。下段旧“当前 Coding Prompt”是提交前快照。

2026-09-26 规划独立复核后的当前顺序为 **M0 中途停牌可用性 → M1 来源化算法 → M2 效果复审**。旧个人局五次本家合法模型动作已获 ACK，最终 `platform_error`；根因仍未定，不能改写为开局未出牌或模型超时。个人 workspace 六份证据和归属标记的大小/hash 本轮只读复核一致，未轮换。当前 Coding Prompt 是 `docs/NEXT_PROMPT.md`；它在一个问题级工作包内验证/修复确切本地缺陷并补低敏阶段观测，不自行开新局。M0 的放行条件见 `docs/PLAN.md`，一次偶然正常完局或仅声称外部故障不足以放行。M1 完整任务已从 `ec5616b` 保存为 `docs/OPENING_ALGORITHM_PROMPT.md`，M0 放行后直接恢复。以下较早“当前/下一项”文字只保留历史事实，以本段及 `docs/PROJECT_STATUS.md` 顶部为准。

2026-09-26 算法规划历史快照：当时 `docs/NEXT_PROMPT.md` 曾是完整的来源条件化开局与多牌型模型前比较 Coding 任务，现已迁至 `docs/OPENING_ALGORITHM_PROMPT.md` 排队。规划复核的三段各 200 局完整随机起局公式直选为 `7/6/4`、全部单张；默认 Botzone factory 的禁网 Request 已有 B/C 条件化输入和推荐/候选闭环，但 seed `0` 的 80 个最终候选含 46 个三带二变体。这些算法事实保持有效，旧“立即执行”顺序已废止。

2026-09-26 最新状态：`d0cd02b` 已将 DeepSeek Chat Completions SSE 改为逐行读取并以 `[DONE]` 为完成边界，规划独立通过定向 55 项、主规则 39 项、全量 842 项。单点测时显示主要等待在模型产生完整合法 JSON 之前；不宣称改动带来因果加速，也不据此解释 seed `47005` 的平台错误。当前下一步为项目所有者个人单局试测；异常时停止下一次个人启动、保留证据，按 `docs/NEXT_PROMPT.md` 只读复审。以下较早的“下一项”是历史快照，当前状态以 `docs/PROJECT_STATUS.md` 顶部为准。

2026-09-26 最新补充：下文所述 B/C 知识预算与输入压缩任务已由 `3cbf9e3` 完成；默认 Botzone DeepSeek factory 的三个固定开局均同时展示 B 原则与条件化 C 软假设，输入字节下降。规划复审与当前下一步以 `docs/PROJECT_STATUS.md` 顶部、`docs/NEXT_PROMPT.md` 为准：首字节后 SSE 仍可等待数十秒，下一项只做证据驱动的流式诊断与安全优化，不将单次前后耗时差称作因果提速，也不把 seed `47005` 的 `platform_error` 归因于模型时延。下文此前的“下一项”是历史快照。

## 1. Project Goal

本项目的长期目标是提供一个可验证的单局掼蛋规则引擎、受规则引擎约束的 AI 决策层，以及用于真实 Botzone 无贡测试桌的本地 AI connector。

当前主线已从严格 Botzone capacity 实验切换为算法优化。真实 Botzone 对局用于阶段性 smoke 和获取公开决策轨迹；只有候选策略先在本地固定 seed 评估中显示稳定收益、且项目所有者明确要求正式对比时，才恢复可比、可审计的 RuleBased/DeepSeek 成对实验。

本项目不是完整的多局升级/贡还比赛引擎。当前 Botzone 主线明确限定为四人、需要进贡为否的单局 play 子集。

最新工作状态以 `docs/PROJECT_STATUS.md` 顶部为准：seed `47005` 单局的六份固定 Codex workspace evidence 仍保留，平台结果为 `platform_error`；额外的空 `D:\VsCodeProject\BotzoneState` 已单独回收。规划 Codex 曾从固定 workspace 短时启动同一个 connector，项目所有者确认页面“已连接”；其新 probe artifact 与旧六份证据共存。随后项目所有者刷新页面，确认个人脚本也显示“已连接”，因此暂停两条启动路径的连接差异排查，不把刷新现象当作已证实的网络或代码根因。`b17c2d9` 已使本地开局直选采用完整关系门槛；`ad7524e` 加入模型前跨牌型指引，`1b8d493` 使 Botzone DeepSeek factory 默认 RAG top‑1 的三个固定开局均收到 B 级来源与新指引，并修复 recommendation 缺席时的判据渲染。规划独立通过相关 96 项、主规则 39 项、全量 835 项及禁网实际 Request 复验。项目所有者已要求把默认 B/C 知识预算和响应时延归因合成下一项完整 Coding 任务，不再暂停等待选择；直接执行 Prompt 见 `docs/NEXT_PROMPT.md`。后续如需 live，必须重新盘点 workspace，不能把此处历史快照当作新 inventory 或建目录指令。

## 2. Current Repository State

以下能力已经存在于当前代码，并有测试覆盖：

- `engine/` 实现单局四人掼蛋状态、发牌、牌型、合法动作生成、动作比较、回合推进、接风、名次和终局。
- `GuanDanGame` 暴露 `reset()`、`observe()`、`legal_actions()` 和 `step(action_id)`；公开动作使用稳定的原始 `action_id`。
- `agents/` 包含 `RuleBasedAIAgent`、`DeepSeekAIAgent`、开局公式、手牌评分、记牌、RAG、confidence shadow/prompt 和 strategy intent shadow/prompt。
- `integrations/botzone/` 包含 Botzone 108 实体牌 ID 映射、deal/play 协议、Bot JSON envelope 与 direct-stage 两种 wire mode、HTTP 长轮询、会话持久化、pending/ack 事务、无贡 play adapter、RuleBased/DeepSeek 组合、运行 provenance、聚合审计和前台 runner。
- connector 支持显式 `--agent rule|deepseek|conditional_pressure_pass`、仓库外 state 目录、`--run-token`、零网络 preflight、完成目标和 v7/v8 completion audit。新增条件 mode 只由精确 opt-in 启用，默认仍是 `rule`。可读history负责逐手展示；新增默认关闭的decision trace在Header ack后保存完整公开observation、原始canonical legal actions、selected action及低基数source。
- 仓库级Skills位于 `.agents/skills/`：`botzone-manual-live` 封装单局人工连接、建桌、监测和evidence验收；`botzone-workspace-recycle` 封装已审计artifact的精确回收站清理。run-specific seed、Agent、预算、文件allowlist与hash仍只放在当前任务Prompt。
- `evaluation/botzone_policy_benchmark.py` 能生成正式四座位成对赛程或显式 selected-seat 赛程，并严格聚合 RuleBased/DeepSeek v7/v8 audit。
- `botzone_upload_py36/` 是独立的 Python 3.6.5、无贡、自然牌规则 Bot；`botzone_deepseek_probe_py36/` 的 DeepSeek 调用只做探测，不参与动作选择。
- 最新业务提交链为 `d20dba3`、`7020b35`、`da2fd6b`、`caa1cc0`，由 `7494897` 合入主线：H3-A1 已完成来源策略、十域决策链、RAG/prompt 投影、canonical/预算 fail-closed 和有界代表选择。规划 Codex 独立通过 212 项相关、39 项主规则、732 项全量及 30 局/2730 状态真实引擎离线探针；H3-A0/H3-A0a 已封板，H3-A1 现有基础保留，但 H3-A2 资格检查暴露的 recommendation/final-candidate 跨阶段守恒缺口仍待 H3-A1.1 修复。
- H3-A2 首轮在任何网络调用前停止，请求0、重试0。八场 engine-backed fixture 中五场因完整动作集产生的 recommendation ID 未被 prompt shortlist 保留，严格校验进而删除整个模型前建议区块。规划 Codex 在真实引擎 seed `0..9` 的初始局面全部复现同类失败；当前问题不是模型选择、RAG 来源或 fixture 绕过问题。
- `ba449f5` 已实现通过校验后的 recommendation-ID 两层保护和实际 prompt-candidate 响应边界，但规划复审未封板：40局/3379状态发现4个 builder/validator 预算漂移反例。builder 可产生5个 objective 的 ready payload，而 validator 上限为4，保护随之关闭；当前还需 H3-A1.1a 最小纠错。
- `8d2146e` 已完成 H3-A1.1a：builder/validator 共用4项目标预算，模型前目标按公开紧急性稳定收敛，外部超预算payload继续fail closed。规划Codex独立通过66/39/740项测试和80局/9381状态双推进探针，ready recommendation、受保护ID、最终候选及prompt闭环零失败；H3-A1.1封板。
- H3-A2后续执行报告称八场离线资格均通过，但真实请求进程最终stdout未被会话捕获，且未生成低敏持久结果。请求计数、逐场provider outcome与动作分类不可审计，因此该次真实阶段只记`inconclusive / evidence_missing`，不追认。独立H3-A2r恢复已有可审计低敏ledger：八场资格ready、8请求/8 success/0重试、6 ready/2 not_ready；两个not_ready分别为炸弹残余场景`alternative`与对子清理场景`other`，只支持模型前对照继续诊断。
- canonical危险对手fixture的受约束真实模型检查已判定`danger_opponent_prompt_raw_model_ready`：唯一请求成功、重试0，模型在后置守卫前自行返回固定候选集内的`ordinary`动作；现有`block_opponent / urgent_opponent_controls_table`输入已足以支持退役强制pass阻断。该结果以低敏执行报告为证据，不是整体胜率结论。
- 项目所有者长期授权单个明确诊断/评测任务中严格少于10次的预注册真实DeepSeek请求，无需另行申请；10次及以上仍须事先授权，范围、重试、密钥和自由文本保密边界不变。
- 固定4张自由出牌fixture的守卫前真实模型检查判定为`short_endgame_prompt_raw_model_not_ready`：最少分组集合为`{1,2,5}`，但唯一成功请求的原始动作落在严格更差的单J集合`{3,4}`。当前`ready / control / stable_control`提示未提供最少剩余分组语义；该低敏单点证据支持补充专用prompt，不支持删除或扩大守卫，也不是胜率结论。
- `c32259d`后的同fixture专用prompt复放已判定`short_endgame_dedicated_prompt_raw_model_ready`：唯一请求成功、重试0，原始动作进入最少分组集合`{1,2,5}`；`run_out / short_endgame_minimum_groups`、两项关键语义和RAG低基数字段均符合前提。规划Codex独立复跑126项相关测试；该低敏单点证据支持下一任务退役`short_endgame_plan`生产改写，但不构成整局或胜率结论。
- seed `47004` 的最新HEAD人工DeepSeek采样已形成有效ACK decision trace：25/25/25 request/response/Header、qualified finish=1、24条决策与audit守恒，15次模型success、9次local shortcut、0 fallback、0 transport failure，v8 audit/v4 tombstone provenance一致。平台分类`local_team_loss`不作为策略优劣证据；六份evidence保留在固定workspace。

上述实现检查点：

```text
66009fc
```

当前分支：`cao`。提交数量会随规划检查点继续变化；读取者应以实际 `git rev-list --left-right --count origin/cao...HEAD` 为准，不使用本文中的历史 ahead 数字。

## 3. Confirmed Architecture

### Local game path

```text
GuanDanGame.observe()
        + legal_actions()
        -> Agent.select_action(observation, legal_actions)
        -> original legal action_id
        -> GuanDanGame.step(action_id)
```

`engine/` 是规则真值。AI 只选择动作，不生成规则结果。

### Botzone connector path

```text
Botzone local-AI endpoint
        -> HTTPS GET long poll
        -> poll/parser (Bot envelope or direct stage)
        -> per-match SessionStore
        -> no-tribute public projection + canonical legal actions
        -> RuleBasedAIAgent or DeepSeekAIAgent
        -> validated original action_id + provenance lookup
        -> Botzone [action, claim]
        -> X-Match-* response header
        -> successful delivery acknowledgement
        -> commit pending PlayEffect / update durable session
```

关键实现边界：

- `integrations/botzone/protocol.py`：严格解析 deal/play、history、global、done 和 table view。
- `integrations/botzone/bot_io.py`：处理 Bot envelope replay、direct-stage response 和历史 response 重放。
- `integrations/botzone/session.py`：隔离 match state；成功发送前不提交出牌 effect；完成后生成最小 tombstone。
- `integrations/botzone/play_adapter.py`：把公开 Botzone 局面投影为 engine 兼容的 observation/legal actions，并把选中动作绑定回实体牌 ID。
- `integrations/botzone/agent_runtime.py`：组合 RuleBased 或 DeepSeek；DeepSeek 故障时保留严格分类和 RuleBased fallback。
- `integrations/botzone/runner.py`：运行循环、退出分类、v7/v8 audit 和聚合守恒。
- `evaluation/botzone_policy_benchmark.py`：只消费聚合 audit，不启动 connector、模型或网络。

## 4. Important Invariants

- AI、RAG、confidence、strategy router 和 Botzone adapter 都不得绕过 engine 的合法动作集合。
- 最终动作必须是严格整数 `action_id`，并存在于调用时的原始 `legal_actions()`。
- `declared_cards` 表示声明语义，`carrier_cards` 表示真实消耗牌；两者不能混用。
- `observe()` 只能暴露公开 payload，不能暴露 `GameState`、`PlayerState`、`Action` 或其他 engine 私有对象。
- Botzone adapter 不能让 Agent 直接生成 Botzone 实体牌数组；实体 `[action, claim]` 必须由 provenance 映射生成。
- 当前 live profile 只支持无贡。`tribute`、`return`、非零 tribute 和未知阶段必须 fail-closed。
- Botzone URL、Header、match ID、手牌、prompt、response、reasoning、API key 和 Cookie 不得进入聚合 audit 或日志。
- state 与 audit 必须位于仓库外；每局使用隔离目录。运行 token 只接受 32 位小写十六进制。
- 清理完成后，`D:\VsCodeProject` 下只允许一个 Botzone 顶层运行目录 `D:\VsCodeProject\BotzoneWorkspace`；后续任务复用它，不再按 seed、pilot、pair 或 capacity 创建新顶层目录。清空旧内容必须在结果记录后、live 开始前作为独立任务执行。
- pending response/effect 只在 transport acknowledge 后提交；重发、重启或重复 acknowledge 不得重复扣牌。
- long-poll timeout 是 idle 事件；只有严格匹配的 timeout 计数/诊断才能被 benchmark 接纳。其他 transport failure 仍使样本无效。
- v8 audit、v4 tombstone 和预注册 token 必须一致；不具备可证明归属的证据不能进入正式配对聚合。
- DeepSeek 路径允许本地 shortcut；模型返回异常、无动作或非法 ID 时必须走受控 fallback，不能伪造合法动作。
- 不读取、修改或提交 `.env`、真实密钥、`logs/` 或 `archive_legacy/`。

配置事实：`integrations/botzone/runtime_config.py` 只读取 Botzone URL/state 两个指定变量；`config.AppConfig.from_env()` 会调用 `load_dotenv()`，开关并非由 `config.py` 自己处理。2026-09-01 只读复核确认项目 `.venv` 使用 `python-dotenv 1.2.2`，其 `load_dotenv()` 在创建解析器或读取 `.env` 前检查 `PYTHON_DOTENV_DISABLED`；系统 PATH 中的 Python 使用 `python-dotenv 1.1.1`，不具备该分支。因此禁用流程只在显式使用项目 `.venv\Scripts\python.exe` 时得到当前环境证据支持，裸 `python` 不属于受支持执行方式。

## 5. Current Task

长期目标仍包括在需要时取得条件可比、证据归属明确的真实 Botzone 无贡 RuleBased/DeepSeek 成对对局；但该目标已延期，不再阻塞算法优化。

期望容量在现有文档中定义为两个 seed × 四个本家座位，每个条件各运行 RuleBased 和 DeepSeek，共 8 对/16 局，AB/BA 平衡。这个容量目标是计划，不是已经完成的结果。

connector可读牌谱、普通人工RuleBased history smoke、两阶段候选评测、Botzone显式 `conditional_pressure_pass` wiring、trial validator、默认RuleBased两类保牌、DeepSeek危险对手pass阻断、自由出牌小手牌短序列守卫和队友小王后大王保留均已完成。DeepSeek失败fallback仍使用冻结旧静态基线。seed `47002`已完成真实对局但含2次HTTP error，真实条件化pass为0；其后只读策略审计没有得到新的高置信度缺陷。

seed `47003` 的单局DeepSeek采样已经完成connector与ACK trace闭环：11/11/11 request/response/Header、qualified finish=1、10条decision trace与audit守恒、history/trace均为`ok`，无transport failure。平台终局分类为`platform_error`，所以不能作为正常胜负结果；它不否定已通过binding、selected-action、ACK和provenance校验的逐决策证据。

strategy-intent接线已提交为`454a422`：Botzone DeepSeek factory启用现有router与prompt formatter，未新增后置动作覆盖。规划Codex独立复跑119项定向、39项主规则和709项全量通过；真实第9条公开输入经无网络factory复核得到ready的`support_teammate / teammate_controls_table`，fake模型的原始合法特殊牌仍保持`model`。

受约束执行报告将该固定决策的真实DeepSeek off/on复放判定为`strategy_intent_target_decision_improved`：off侧模型成功返回合法特殊牌，on侧模型成功返回合法pass；on侧意图为`ready / support_teammate / teammate_controls_table`，两侧使用独立Agent，总请求2、重试0，没有RuleBased替代或新增后置pass。规划Codex独立复核trace仍为88,983 bytes / SHA-256 `4ba2ea88a13046f8f7907df6dd124175dceee3a88e9723be88c6581a28bc3512`，仓库仍clean；模型响应按隐私契约未持久化，无法从artifact独立重演。该结果是目标决策的输入消融证据，不是整体胜率结论。

全10条trace及三个成功模型动作后置守卫的只读审计随后判定为`seed_47003_no_additional_high_confidence_candidate`。规划Codex使用当前生产代码独立复算，得到自由2、队友领牌4、对手领牌1、证据不足3，以及pass 5、ordinary 4、special 1；三个守卫对记录动作的触发数均为0。第9条只重复已完成缺口，其他记录不足以定义新的prompt/RAG修改，故seed `47003`分析封板。三个守卫均属策略覆盖而非协议安全，但在没有对应证据时不直接删除。

其后的`teammate_control_block`守卫前真实模型调用成功并返回`target_special`，但评测前提无效：复用的`tests/test_deepseek_step_e.py::_teammate_joker_legal_actions()`同时提供pass、大王和单张9，而当前引擎证明9不能压单张小王。该列表不是canonical legal actions。规划Codex据此把执行判定从`teammate_control_prompt_raw_model_not_ready`改为`teammate_control_prompt_raw_model_inconclusive`；本次调用不授权prompt/RAG修改，因此当时只安排修复测试fixture并锁定engine真值。

测试证据修正已提交为`8db3154`：目标小王场景现只含pass与大王两个canonical候选；原普通低价值动作非触发测试已迁移到队友普通单张8、本家以9合法压制的独立场景，并新增引擎真值回归。规划Codex独立检查两文件提交范围，复跑定向41项、主规则39项和全量710项通过，`git diff --check`通过，工作树clean；随后只对该canonical fixture做了一次新的守卫前真实模型检查，旧inconclusive调用未合并。

受约束执行报告将新的canonical检查判定为`teammate_control_canonical_prompt_raw_model_not_ready`：候选数2，intent为`ready / support_teammate / teammate_controls_table`，RAG为`endgame / endgame`，唯一模型请求成功且原始选择为合法大王；结果在后置守卫前捕获。模型响应按隐私契约未持久化，但规划Codex独立确认提交、fixture、引擎真值与Git clean。当前可复现缺口是strategy-intent只表达泛化“队友当前控桌”，没有表达小王→大王的高价值资源代价和无紧急阻断需要。下一任务只实现共享公开判定驱动的专用prompt reason，不改RAG或后置动作行为。

专用prompt改进已提交为`24fb362`。新增`teammate_big_joker_opportunity()`在模型选择前只从公开observation与canonical legal actions识别原始pass/大王机会，既有后置守卫改为复用它；router新增`teammate_big_joker_preservation` reason，prompt增加小王控桌、pass合法、不能直接出完、无紧急对手及保留大王的策略意义。RAG、engine、Botzone协议、audit、observability与守卫优先级/范围未改。规划Codex独立检查8文件diff并复跑83项定向、39项主规则、712项全量及`git diff --check`，全部通过。

其后的单次canonical真实模型复放判定为`teammate_big_joker_prompt_raw_model_improved`：两个候选与共享机会判定均成立，intent为`ready / support_teammate / teammate_big_joker_preservation`，RAG保持`endgame / endgame`；唯一模型调用成功、重试0，后置守卫前原始选择为合法pass。仓库与workspace未修改。该结果支持下一任务退役`teammate_control_block`主动改写，保留专用prompt和共享机会真值；旧source只保留必要的持久证据读取兼容。

L5-A4h11a partial manifest、seed `45001` evidence、seed `47001` prestart evidence、seed `47002` evidence与已完成审计的seed `47003` evidence均已移入Windows回收站；未永久删除或清空回收站，无残留connector。

seed `45001` 的普通人工 RuleBased history smoke 已完成并通过独立复核：15/15/15 请求闭环、qualified finished 1、14 次 rule primary、零 model/fallback、exit 0、`history=ok`，stderr 空。最后不完整观测段的显示语义与标题格式均已修复，并经16/54/643项独立复跑通过。

14次本家决策审计确认修改前 RuleBased 的首个候选机制：它无条件排除 pass，因此在跟随对手且可用压制全为炸弹类时也不会保牌。真实两手动作因缺少当时完整 legal actions 只能作为线索。候选已在固定级牌2的同状态 one-step 与整局重复触发 trial 上满足 retain 门槛，并已于 `150006a` 合入默认RuleBased；不再追加跨级牌容量。

seed `47001` 已使用且不得复用。项目所有者确认页面一直显示“未连接”，所以游戏从未开始；audit的2次timeout与0 request只说明调用以timeout结束，不能证明页面已连接。该次没有Agent决策、state或history，不能评价条件化策略。其evidence现已回收。后续普通人工live的顺序已经固化进 `AGENTS.md`：先启动唯一connector并确认页面已连接，再分配seed、创建/配置桌。

seed `47002`也已使用且不得复用。页面连接门槛先通过，对局随后exit 0 / `finished_target`并形成17/17/17、qualified finish、v4/v8归属和可读history；但2次 `http_error`使严格零故障smoke标签不成立。16次决策均为 `conditional_rule_based`，真实候选pass未激活。这是非激活runtime兼容性证据，不是候选胜率或激活证据。

seed `47002` 后续只读策略审计确认：16次决策中14次可按公开语义重建，9次pass均只有pass合法；两个可精确比较的自由出牌点不存在严格更优的残余分组。第1、6次缺少足以唯一恢复canonical动作的声明/载体细节。结论是现有evidence不足以支持下一项算法修改，不得据此猜测新规则。

决策证据实现已最终提交为 `045fb75`。五个历史反例全部转绿：fresh输出前置拒绝、跨recorder随机持久binding、Agent深隔离、observation/top-level legal actions强一致，以及history-only direct CLI旧路径兼容。规划复跑88项定向、39项主规则和707项全量通过；当前范围内无已知剩余风险。

seed `47004` 的三处策略观察已经由规划Codex从trace和生产代码独立分因：同点数四/五张炸弹均对模型可见但现有prompt没有残余孤张取舍；自由首出Q来自开局公式local shortcut而非模型，缺陷就是Q这一首攻自身——清理孤张应优先不拆结构的低牌，低成本试探也应优先10或更低的可牺牲普通单张，并保留更高单张的残局牌权机会；对3存在于原始合法集合，却因free-lead transition剪枝在有single时完全不保留pair而对模型不可见。下一任务只修剪枝、开局公式和公开残余结构输入，不恢复任何后置策略改写。

该修正方向随后上提为策略来源重建。规划Codex确认现有经验RAG与开局公式没有可追溯的人类经验来源或权重校准；`docs/STRATEGY_SOURCE_AUDIT.md` 已将官方规则、具名专家/正规出版物、弱来源转载和学术架构资料分层。后续不再按Q、4、10等单点动作追加神秘分数：确定性公式只承载来源清楚、范围明确、fixture稳定的少数定式，证据不足时退出给RAG+DeepSeek；剪枝保持牌型高召回。经验正文只保留纯策略知识和语义标签，作者、书目、URL、来源等级与激活状态由独立治理registry关联，不得参与检索或进入模型prompt。

`5dbdd2c` 已完成上述 H3-A0 主体，但规划复审发现 pair 修复只停留在第一层剪枝。最终 `_limit_prompt_actions()` 在 critical 数量达到 80 时会返回全部 critical，真实引擎初始局面可同时出现最终候选超过 80 且自然 pair 全部消失；已知 seed `47004` 同样复现该低敏结论。因此知识/治理隔离、窄开局定式和炸弹结构输入可以保留，H3-A0 整体仍需 H3-A0a 修复最终预算与 pair 召回后才能封板。

项目所有者随后批准 H3-A1 的 DeepSeek 中心策略方向：本地层负责候选、公开结构、场景/目标、来源经验和模型前推荐，DeepSeek 保持最终策略裁决；开局公式只作为延迟约束下的窄高置信快速路径及可供模型验证的推荐，不扩张成第二套完整策略 AI。H3-A1 将以十个策略域批量覆盖开局、结构、控制、牌权、协同、阻断、炸弹/通配、残局和不确定性，不再按单个现场动作追加神秘分数。provenance 治理字段继续与知识平面隔离。

## 6. Confirmed Symptoms

### Historical formal batch summary

截至 2026-09-03 清理执行前，以下目录曾实际存在：

```text
D:\VsCodeProject\BotzoneVerifiedUiCapacity-42001-42002
D:\VsCodeProject\BotzoneVerifiedUiCapacity-43001-43002
```

只读核对结果：

- `capacity-manifest.json`：4661 bytes，SHA-256 `5989a6dc07441c94b02725a31b29706d9708311ce7eee597e82b96b47921b4ff`。
- `preflight-summary.json`：2273 bytes，SHA-256 `32a9cf1adfdc881037aea6adb8f594a51876a958df88fc0a4432ddf55370cad9`。
- `progress.json`：状态 `invalid`，completed=0，next=1，failed=1，failure stage=`ui_readback`。
- game 1 completion audit：v8、exit 130、`interrupted`、cycles=4、request/response/Header=`0/0/0`、qualified finished=0、transport failure=0、transport timeout=4、agent mode=`rule`。
- 16 个 state 目录当前均无 state 文件。
- 该目录中没有成功完成的正式 pair。

`43001/43002` 只读核对结果：

- `capacity-manifest.json`：4661 bytes，SHA-256 `e98e60423dea922f1ae5454edd847ea8210798a345ad13ffabc8fb343fc0dea6`。
- `preflight-summary.json`：2273 bytes，SHA-256 `207b6408642c1e85ec850c929304fcf5f3e0cc08f82ec844f0977dff45890f42`；双模式零网络 preflight 均通过。
- `progress.json`：284 bytes，SHA-256 `2a4dc0140a2bb406021add3e4af725ce39af93c06267bc6d7734b7c0c1010abc`；状态 `invalid`，completed=0，next=1，failed=1，failure stage=`lobby_gate`。
- 页面在配置写入与 connector 启动前进入 `?msg=destroyed`，可见“游戏桌被房主关闭了”。
- connector、Agent、DeepSeek/model 调用均为 0；16 个 game 目录存在，state/audit 文件总数为 0/0，无残留 connector。
- 正式 root 创建时 HEAD 为 `08962800af7c47779b1435dcac97c8de17471e0f`，正式批次期间仓库保持冻结。

项目所有者随后明确授权清理 `D:\VsCodeProject` 下全部 21 个本任务形成的 `Botzone*` 顶层目录，包括上述两组 formal evidence。L5-A4h10a 已把它们全部移入 Windows 回收站；原路径不再存在，但在回收站清空前仍可由项目所有者恢复。本节记录的状态、大小和 SHA-256 只作为历史摘要。

清理完成后，`D:\VsCodeProject\BotzoneWorkspace` 已再次被独立复核为唯一直属 `Botzone*` 目录、普通非链接，且递归精确只剩空的 `audit/`、`state/`、`streams/`；当前状态应以第 5 节的最新 inventory 为准。

### Functionality known to work

仓库文档记录过以下成功运行结果：

- 一次人工无贡 DeepSeek connector：12/12/12 request/response/Header，qualified finished=1；10 次模型尝试均 success，fallback=0。来源：`docs/PROJECT_STATUS.md` 的 L5-A3c。
- 一次自动 UI RuleBased pilot：34/34/34，qualified finished=1，33 次 `rule_primary`，v8/v4 provenance 一致。来源：`docs/PROJECT_STATUS.md` 的 L5-A4f7。
- 一次 selected-seat 单对只读恢复聚合有效，但两侧均为负且分数相同。来源：`docs/PLAN.md` / `docs/PROJECT_STATUS.md` 的 L5-A4g2。该结果不是策略收益证据。

这些结果证明单局 connector、模型动作进入响应和单对聚合路径曾分别成功；它们不证明完整 8 对容量能够可靠执行，也不证明 DeepSeek 优于 RuleBased。

## 7. Verified Facts

- `GuanDanGame.step()` 拒绝不在当前 action map 中的 ID。来源：`engine/game.py`、`tests/test_game_flow.py`。
- `BaseAgent` 契约只返回 action ID；`require_legal_action_id()` 再次验证 ID。来源：`agents/base.py`。
- `DeepSeekAIAgent` 在模型前执行 only-pass、一次出完和可选开局公式 shortcut。来源：`agents/deepseek_ai.py::select_action()`。
- connector 的 DeepSeek 组合继续关闭confidence prompt，但已由`454a422`启用strategy router shadow与strategy-intent prompt。来源：`integrations/botzone/agent_runtime.py::build_agent_factory()`。
- DeepSeek client wrapper 只保留合法 action ID，丢弃自由文本 reasoning，并分类 success/timeout/exception/invalid_suggestion。来源：`integrations/botzone/agent_runtime.py::_StrictDeepSeekClient`。
- adapter 会对 Agent 返回类型、合法 ID 和 provenance 分别 fail-closed；DeepSeek 外层 fallback 仍必须返回合法 ID。来源：`integrations/botzone/play_adapter.py::NoTributeRuleBasedHandler`。
- transport 只发 HTTPS GET，拒绝重定向，限制响应大小，并用固定类别脱敏错误。来源：`integrations/botzone/http_transport.py`。
- run-token 模式生成 session/tombstone v4 和 audit v8；默认兼容 v3/v7。来源：`integrations/botzone/run_provenance.py`、`session.py`、`runner.py`。
- benchmark 要求成功终止、request=response=Header>0、qualified finished=1、正常结果=1、无真实 transport failure，以及 Agent/model/result 守恒。来源：`evaluation/botzone_policy_benchmark.py::_validate_audit()`。
- benchmark 可接受唯一、计数严格匹配的 idle timeout diagnostic，但拒绝混合诊断或真实 transport failure。来源：同上及 `tests/test_botzone_policy_benchmark.py`。
- `RuleBasedAIAgent` 当前不读取 observation；存在任一非 pass 时排除 pass。最小 `pass+bomb` 与 `pass+straight_flush` 输入均稳定返回非 pass。来源：`agents/rule_based_ai.py` 与2026-09-05只读诊断。
- `evaluation/conditional_pressure_pass.py` 已分开校验完整 legal/table action 与六字段 history row，并只核对二者共同语义。seed `46000` 的真实 public API 回归证明 baseline 选 bomb、candidate 选原始 pass ID。
- 原 `46000..46199` one-step benchmark 两次完全一致：686次机会、617个 changed pairs、candidate/baseline/tie=`191/172/254`、score=`635/619`、名次和=`3053/3079`、零失败/diagnostics；唯一判定 `retain_conditional_pressure_pass_for_runtime_trial`。
- 新 `46200..46399` 整局 trial 两次完全一致：400/400局、197 active pairs、1433次 pass、candidate/baseline score=`422/378`、名次和=`1966/2034`、pair=`73/53/74`；判定 `retain_conditional_pressure_pass_for_botzone_opt_in_smoke`。该结果仍不证明真实 Botzone 胜率。
- trial的pair/game、W/D/L互补、rank/diagnostic、非空容量、active/pass、单方名次范围和digest均已封口；真实两套report/hash不变。
- Botzone显式mode已接通并以 `conditional_pressure_pass` / `conditional_rule_based` 低敏source守恒；正式RuleBased/DeepSeek benchmark拒绝混入conditional audit。
- 当前全量测试：718 项通过。命令：`.venv\Scripts\python.exe -m unittest discover -q`，Python 3.11.9。
- 当前 decision-trace/Botzone 定向：88 项通过；engine主回归：39项通过。精确命令见 `docs/TESTS.md`。
- 当前 benchmark 定向测试：13 项通过。命令：`python -m unittest tests.test_botzone_policy_benchmark -q`。
- 当前 engine 主回归：39 项通过。命令：`python -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q`。
- 当前 preflight 输出定向测试：5 项通过。命令：`.venv\Scripts\python.exe -m unittest tests.test_botzone_preflight_output -q`。
- `git diff --check` 通过。
- 2026-09-03 独立 Edge 排障：Edge 正在运行；ChatGPT Edge 扩展已安装且启用；native-host manifest、注册表路径和允许 origin 均正确；`edge.user.openTabs()` 成功。现有 Botzone destroyed 标签在重新绑定时被报告为属于另一个浏览器控制会话。

## 8. Unverified Hypotheses

- **UNVERIFIED / DEFERRED:** `?msg=destroyed` 是由无操作超时、某个页面动作、房主/平台状态还是其他 UI 生命周期条件触发；自动建桌路线已停止，不再作为当前任务。
- **UNVERIFIED / DEFERRED:** 旧标签的浏览器会话占用是否就是上一轮 Playwright locator 超时的原因；项目所有者改为手工建桌后不再继续此诊断。
- **UNVERIFIED:** UI 自动化是正式容量采集唯一剩余的失败来源；progress、平台状态、长轮询和人工验证码仍可能影响批次。
- **VERIFIED:** 人工建桌、connector 就绪后人工点击开始的新交接顺序已在 seed `45001` 完成一局并形成可归属 history/audit/state/streams evidence；这不证明每次都不会受平台状态影响。
- **UNVERIFIED:** 上一执行报告所称 PowerShell 参数不兼容的精确命令与根因；报告未提供足够错误细节。
- **UNVERIFIED:** 首次 formal preflight 的具体失败断言；报告未提供 return code 或 stdout/stderr 捕获值。当前代码测试支持 LF/CRLF，两者不能仅凭猜测归因为旧验证器误判。
- **UNVERIFIED:** DeepSeek 相对 RuleBased 存在动作质量、因果效果或胜率提升。
- **CONFIRMED（受约束执行报告 + 本地完整性复核）:** seed `47003`第9条固定决策中，off侧真实模型选择合法特殊牌，on侧在队友控桌意图提示下选择合法pass；trace bytes/hash与Git未变已独立复核，模型动作对照因隐私契约不持久化而不能从artifact重演。该证据支持公开上下文改善了目标决策，不外推到其他决策或胜率。
- **VERIFIED（本地 proxy）:** 条件化炸弹资源保留 pass 在修复后的 one-step 与整局固定 seed 评测中均满足预设 retain 门槛，且两次运行结果确定一致。
- **UNVERIFIED:** 该候选在真实 Botzone 对局中是否会触发，以及是否改善长期真实胜率；下一次单局 smoke 只验证 opt-in 路径，不回答长期胜率问题。

已从未验证项移除 dotenv 禁用流程：项目 `.venv` 的依赖实现已只读确认支持该开关；该结论不适用于系统 PATH 中的其他 Python。

## 9. Failed Approaches — Minimal Record

- L5-A4h1 至 L5-A4h11b 的共同流程问题已经确认：**把每一个可以原地修正的准备阶段小错误，都升级成不可恢复的正式实验失败。** 具体故障包括 manifest/fsync、progress schema、命令解析、serializer 分叉、浏览器控制、workspace 准备和 preflight 捕获。它们不是同一个代码 bug，但都说明正式实验边界启用过早、编排层和实验层没有分离。未来恢复正式实验时应保留这些失败记录，并把零外部副作用的准备错误留在可修正 qualification 层。
- connector 已由多次真实完整对局证明可用；上述失败不能概括为 connector 不稳定。严格 16 局 capacity 现已延期，直到存在离线验证有收益的候选算法。

- 自动 `runmatch` 建桌曾产生无法完成归属或闭环的运行；没有形成有效 benchmark。该路线没有删除 connector 代码，但后续正式测试改用网页桌。
- 多个早期容量批次因桌面条件不匹配、进度/evidence 契约或 UI 生命周期失败而停止。相关代码缺口中的 idle timeout 和 run provenance 已由提交 `569d543`、`45d34f0` 修复；旧批次 evidence 按各自文档状态封存。
- `42001/42002` 正式批次在 game 1 提交前的 UI readback 阶段停止，completed=0。目录保持只读，没有恢复或重试。
- `43001/43002` 正式批次在 game 1 / `lobby_gate` 停止，completed=0；页面在配置和 connector 前显示房主关闭。该症状与历史 `33001` 的预提交 UI 生命周期失败同类，但两次都没有足够动作证据确认根因。
- L5-A4h9 只读到任务开始前的 destroyed 标签，随后 locator 超时；新桌和页面写动作均为 0。因此它没有形成新的生命周期结果，执行报告中的 destroyed 判定不作为规划事实，改记为前置 locator 不可用。
- 原定 L5-A4h9a 的新标签 locator 资格尚未执行即由项目所有者取消；以后由项目所有者手工建桌，不再投入任务恢复自动 Edge 操作。
- L5-A4h10 的永久递归删除在启动前被执行环境策略拦截；安全门槛全部通过，但删除和目录创建均为 0。不得使用其他永久删除 API 绕过；下一步只尝试回收站式可恢复清理。
- L5-A4h10a 已将 21 个旧目录移入 Windows 回收站并建立唯一空的固定 workspace；原始 evidence 不再位于原路径。
- L5-A4h11 在首个 workspace artifact 前因笼统的 PowerShell 参数不兼容停止；独立复核 workspace 仍为空，preflight/connector/table/network 为 0。该结果重分类为 preparation precondition failure，不消耗 `44001`。
- L5-A4h11a qualification 与 manifest 成功，但 formal preflight 严格验证失败；manifest 已锁定，state/audit 仍空，未请求建桌。当前只允许诊断后的一次 formal recovery。
- 牌谱完成并决定退役旧 formal recovery 后，manifest 清理任务的全部只读门槛通过，但精确非递归永久删除命令仍在实际执行前被命令级安全策略拦截。授权本身有效；该结果不得误报为授权缺失，也不再继续尝试永久删除。恢复动作改为精确的 Windows 回收站式单文件移动，不清空回收站。
- 回收站式恢复动作随后成功：旧 manifest 原路径不存在，workspace 只含空 `audit/` 与 `state/`；清理工作已完成，不再是当前阻塞项。
- seed `45001` history smoke 随后成功。牌谱的6轮只是6个已观测牌权段；本家在最后一段出完后不再收到请求，finished row 又不含完整尾部，所以不能据此声称裁判整局在第6轮结束。原“第6轮结束后的手牌”展示语义已经修复。
- 该展示语义与新标题空格均已完成修正并通过16/54/643测试；不再是当前待办。
- 文档曾在通用 Windows Computer Use 与 Edge 浏览器扩展之间切换。提交 `0896280` 只修改了文档；后续已证明 Edge family 可绑定，但没有证明它能维持建桌表单或完成正式容量。

## 10. Files Relevant to the Current Problem

- `docs/CLEAN_HANDOFF.md`：本交接事实基线。
- `docs/NEXT_PROMPT.md`：当前计划草案；不是实现事实或已验证方案。
- `docs/PROJECT_STATUS.md`：已记录的里程碑与 live 结果索引。
- `docs/BOTZONE_INTEGRATION_PLAN.md`：Botzone 范围、协议差异和历史阶段。
- `docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`：规则与架构硬边界。
- `integrations/botzone/__main__.py`：connector CLI、preflight、agent 选择、audit 写入。
- `integrations/botzone/runner.py`：前台生命周期、停止条件和 v7/v8 audit。
- `integrations/botzone/connector.py`：poll、session、response Header 和 finished 处理。
- `integrations/botzone/session.py`：持久 session、pending/ack、history merge 和 tombstone。
- `integrations/botzone/play_adapter.py`：公开局面投影、Agent 调用、provenance 和 action/claim 编码。
- `integrations/botzone/agent_runtime.py`：RuleBased/DeepSeek 组合与 fallback。
- `integrations/botzone/http_transport.py`：长轮询传输和 timeout 分类。
- `integrations/botzone/run_provenance.py`：v4/v8 token 契约。
- `integrations/botzone/agent_observability.py`、`result_observability.py`：低基数聚合守恒。
- `evaluation/botzone_policy_benchmark.py`：正式/selected-seat 赛程与 pair 聚合。
- `agents/rule_based_ai.py`：当前最小规则 AI；存在非 pass 时排除 pass，且不读取 observation。
- `evaluation/pass_policy_benchmark.py`：历史 evaluation-only 宽泛战略 pass 轨迹载体；相关正式结果拒绝的是牌面推断信号，不是策略 outcome。不可直接把该结果当作当前质量证据，也不宜改名覆盖原语义。
- `evaluation/confidence_action_quality.py`、`evaluation/strategy_intent_action_quality.py`：已有同状态双分支 RuleBased rollout 与团队结果/名次和比较口径。
- `tests/test_botzone_policy_benchmark.py`：当前 benchmark 的最直接契约测试。
- `tests/test_botzone_connector.py`、`test_botzone_session.py`、`test_botzone_play_adapter.py`、`test_botzone_deepseek_agent_runtime.py`：connector 主链测试。
- `config.py`：DeepSeek 配置和实际 dotenv 加载行为。
- 仓库外运行目录（当时快照）：当时唯一顶层目录为 `D:\VsCodeProject\BotzoneWorkspace`，递归只有三个空目录、文件数0；seed `47003` evidence已在审计后移入回收站。最新状态以文首链接为准。

## 11. Tests and Reproduction

### Deterministic local checks

```powershell
python -m unittest discover -q
python -m unittest tests.test_botzone_policy_benchmark -q
python -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q
git diff --check
```

当前最新独立结果为：strategy-intent/DeepSeek/Botzone相关119项、engine主回归39项、全量709项通过，`git diff --check`通过。更早的decision-trace相关88项、runtime-trial validator单文件8项、条件化相关28项与四个固定SHA-256也已独立复核，不因本阶段改变。

### Minimal reproduction of the current failure state

当前问题不是一个失败的本地单元测试。旧 batch 原始路径已被清理，历史结果只能从本交接及 `docs/PROJECT_STATUS.md`、`docs/PLAN.md` 的低敏摘要复核。

当前 H3-A0 业务检查点为 `5dbdd2c`。规划复审运行197项相关定向、39项主规则和717项全量均通过；知识/治理隔离、来源激活、开局窄定式、炸弹结构摘要及模型动作保真未发现回归。当前失败状态不是规则或协议测试失败，而是最终候选层仍可能突破80项并重新移除全部自然pair。

H3-A0a 已由 `66009fc` 修复并独立复审：原6个真实引擎复现样本的第一层候选为132–243项，最终均为80项且保留natural single和稳定最小natural pair；500个独立初始局面性质检查同样通过。相关230项、主规则39项、全量720项均通过。当前不再存在已知候选预算/pair召回阻塞。

## 12. Working Tree Status

- 分支：`cao`。
- 已验证基础实现检查点：`150006a feat: add observed history and pressure-pass strategy`。
- 队友保炸弹检查点：`5daf326 feat: preserve bombs behind teammate leads`。
- 危险对手阻断检查点：`fb3d791 feat: block passes against near-finish opponents`。
- 小手牌短序列检查点：`dc9638c feat: guard short free-lead endgames`。
- 最新算法检查点：`295b9b5 feat: preserve big joker behind teammate`。
- 最新检查点新增队友小王→大王守卫、`teammate_control_block`、双action-ID schema校验与对应测试；提交前由规划Codex独立运行相关65项、主规则39项和全量689项通过，并完成staged diff检查。
- 最新Botzone诊断检查点：`045fb75 feat: record acknowledged Botzone decisions`；提交前由规划Codex独立复现反例并运行定向88项、主规则39项、全量707项及staged diff检查。
- 最新DeepSeek提示检查点：`454a422 feat: enable strategy intent prompt for Botzone DeepSeek`；规划Codex独立检查三文件diff，复跑119/39/709项，并以真实第9条公开输入验证factory提示接线和模型动作自主权。
- 最新测试证据检查点：`8db3154 test: align teammate joker fixtures with rules`；规划Codex独立检查仅两份测试，复跑41/39/710项并确认生产文件零修改。
- 最新strategy-intent检查点：`24fb362 feat: prompt big joker teammate preservation`；规划Codex独立检查8文件diff，复跑83/39/712项，确认RAG、engine、Botzone协议及后置守卫范围未改变。
- 最新动作自主性检查点：`e30362f feat: retire teammate control action override`；核心退役路径经113/39/713项回归通过，但legacy v7/v8 audit的policy benchmark读取兼容尚未达成。
- 最新audit兼容检查点：`3ee6e0e fix: read legacy DeepSeek audit sources`；规划Codex独立复跑109/39/718项，legacy v7/v8正例可读且错误outcome反例fail closed。
- 最新危险对手覆盖退役检查点：`7499ccc feat: retire danger opponent action override`；规划Codex独立复跑132/39/718项，确认原始pass/9/J保留、旧source只读兼容且`short_endgame_plan`无漂移。
- 最新短残局专用提示检查点：`c32259d feat: prompt short endgame grouping`；规划Codex独立复跑92/39/721项，确认共享分组真值、专用prompt和最终输入验证生效，后置planner/source无漂移。
- 最新动作自主性封板检查点：`f426693 feat: retire short endgame action override`；规划Codex独立复跑134/39/718项，确认所有合法模型ID保真、三个旧source仅legacy可读且专用短残局输入未削弱。
- 最新策略来源重建检查点：`5dbdd2c feat: rebuild sourced opening strategy`；主体边界通过复审，但最终 prompt limiter 的硬预算和 natural pair 召回未通过，尚未封板。
- 最新候选召回封板检查点：`66009fc fix: bound DeepSeek prompt candidates`；规划 Codex 独立确认最终硬上限、natural single/pair、原始 ID、签名去重、稳定顺序及模型自主权，H3-A0/H3-A0a 封板。
- 本交接及其他Markdown由随后独立规划文档检查点封存。读取者应以实际 `git status --short` 判断现场，不使用历史静态清单推断未提交文件。
- Coding Codex负责提交其业务代码、tests及任务直接相关修改；规划Codex独立复核结果，只提交自己产生的 `AGENTS.md`、项目Skills和docs上下文修改，不代为提交未完成或未经复核的业务改动。

## 13. Do Not Assume

- 不要假设当前对话提出过的任何诊断正确。
- 不要默认沿用 `docs/NEXT_PROMPT.md` 最后选择的浏览器控制方案。
- 不要把规划文档中的未来步骤当成已实现、已运行或已验证。
- 不要把一次 connector 成功、一次模型 success 或一个有效 pair 当成策略优势。
- 不要把旧批次的失败自动归因于 connector、浏览器、Codex 权限、Botzone 或用户操作中的任何单一因素。
- 从当前代码、测试、实际文件和新运行的可观察行为重新建立判断。

## 14. Recommended Starting Point

H3-A1 组合实现已通过基础复审并合入 `cao`。最新独立结果为相关 212 项、主规则 39 项、全量 732 项；30 局真实引擎离线探针覆盖 2730 个状态、零异常，十域与全部 11 条 active 经验均有生产路径可达证据。但后续 H3-A2 资格检查证明 recommendation 与实际模型候选未形成闭环，因此不能把“域可达”解释为“建议必然进入最终 prompt”。工作区状态仍必须以实际 `git status --short` 为准。

H3-A2r 低敏ledger位于 `D:\VsCodeProject\GuanDanH3A2Audit\h3-a2r.jsonl`，7270 bytes，SHA-256 `32ec0dcbf7709ff30702fc85f5aae0c0c2aabfbb197fb223ebeb4823d9f0a63a`；规划Codex已复核27条事件、请求/结果和汇总守恒，并独立复跑23/23指定回归。其后进入H3-A3离线模型前对照纠错，不重新运行八场真实请求、不运行Botzone/connector/live，也不读取seed `47004` evidence。现有单点结果不构成胜率结论。

`b40000e` 已实现H3-A3关系识别与prompt对照，规划Codex独立通过30/39/747项测试，合法模型动作ID/source与历史边界未漂移。但30个不同初始局面中30/30将自然对子/单张关系放在推荐最前，其中29个另有安全自然小单；100个初始局面里的18个四/五炸关系虽都在最终候选及prompt可见，0个被完整推荐，因为普通对子关系先占最多3项预算。故H3-A3的模型前范围当时未封板，转入H3-A3a离线推荐优先级收窄。仓库外H3-A2r ledger和Coding任务报告的系统Temp流文件均保留，不因本规划复审清理。

`b670753` 已修复H3-A3的推荐优先级外溢，规划Codex独立通过32/39/749项测试。100个真实引擎初始状态中，推荐预算100/100合规；前30个自然对子关系均存在但占推荐前两位0/30，另有安全自然小单29/30；18个四/五炸关系均完整进入推荐、最终候选和prompt。H3-A3/H3-A3a离线范围封板。当时规划的H3-A4低敏真实模型诊断需先八场资格、再最多8请求/0重试；原H3-A2r ledger与系统Temp文件均保持原样，不接触Botzone workspace或seed `47004` evidence，不把类别变化直接当因果收益。

H3-A4已在网络前依门槛停止，不能称为真实模型探针完成。规划Codex独立核对新低敏`D:\VsCodeProject\GuanDanH3A2Audit\h3-a4.jsonl`为3209 bytes、SHA-256 `033107dcd2fb1b242a0cf824a4ec453cee77c494920a8101b1acd0b6944dc54a`，11条事件记录八场资格全部failed、`qualification_complete=false`、真实请求/重试均0。ledger只给出各场候选数0，没有逐阶段失败码；相关32项回归通过，当前引擎两个合成关系场景可生成非零合法候选及ready推荐，因此不能据此宣称生产回归。旧H3-A4 ledger封存不覆盖。当前执行`docs/NEXT_PROMPT.md`的H3-A4q：仅实现与验证可重复的八场engine-backed离线资格场景及固定失败阶段；独立复审8/8后才另立fresh-ledger真实模型诊断。原H3-A2r ledger、Botzone workspace、seed`47004` evidence与系统Temp文件均保持原样。

`c87defa`已建立八场固定engine-backed资格工具，规划Codex独立复跑35/39/752项测试通过，最终候选数6/5/4/6/3/3/4/25；禁网真实DeepSeekClient组装路径与工具当前八场prompt、原始ID/source对照相等。但资格API对空RAG scene/hits的无网络反例仍有六场返回`ready`，没有实质检验RAG层；fake client还绕过了实际最终客户端组装。故当前不放行真实模型请求。`docs/NEXT_PROMPT.md`已转为H3-A4q1离线纠错：仅补RAG/intent/最终组装的可失败门槛与反例，规划复审通过后再单独发起fresh-ledger真实诊断，不修改旧ledger或Botzone证据。

`b229371`已用真实DeepSeekClient禁网transport与RAG scene/hits阶段收紧资格，规划Codex独立复跑39/39/756项通过；八场正例ready，空/错配RAG八场固定失败。但规划Codex注入仅在`_build_structured_prompt()`返回时删除`【模型前建议】`、保留客户端预先记录的`final_prompt`，transport实际接收的请求缺该区块，资格仍误报ready。这是离线资格工具的请求体绑定缺口，生产策略尚无对应反例。下一项`docs/NEXT_PROMPT.md`为H3-A4q1a最小纠错：在禁网transport内捕获实际请求正文，仅以其与记录的候选/prompt及唯一调用次数守恒判定ready；不读旧ledger，不启动真实模型或Botzone。

`81506f8`已封住请求体绑定缺口。规划Codex独立复跑相关40项、主规则39项、全量757项；八场固定离线资格全部ready，最终候选数6/5/4/6/3/3/4/25；单独篡改实际Request user prompt而保留记录prompt的无网络反例固定落在`request_binding`。完整提交只改`evaluation/h3_model_probe_fixtures.py`及对应测试，生产策略未变。H3-A4q组合离线资格门槛封板。当前执行`docs/NEXT_PROMPT.md`的H3-A4r独立真实模型诊断：先全数离线资格，再最多8次/0重试，fresh仓库外低敏ledger；旧H3-A2r/H3-A4 ledger、Botzone workspace、seed`47004` evidence及系统Temp文件均保持原样。

H3-A4r已形成可审计单点技术结果：规划Codex独立核对fresh普通非链接ledger`D:\VsCodeProject\GuanDanH3A2Audit\h3-a4r.jsonl`的5461 bytes、SHA-256`e5e3e2f2ab724ca809af01ef7e513d56974eace0ee5a40fafcb5e95b96f60c51`、27条固定事件及8组连续请求起止；8次success、0重试，八场候选/source守恒。原始类别依序为`alternative / low_cost_single / other / other / pass_preserve / block / minimum_group / spend_resource`，不等于胜率或配对改善。当前HEAD离线资格重跑与ledger计数一致。但八个fixture都被公开phase分到残局，`low_cost_single`不是开局；`neutral_soft_pair`渲染的是炸弹C级条目而非对子C级条目，且该局无炸弹/通配候选。下一项`docs/NEXT_PROMPT.md`为H3-A5离线知识适用性与场景语义纠错；不据这次类别直接改模型prompt或恢复后置覆盖，不读写旧ledger、Botzone workspace或seed证据。

`6ff6d97` 的 H3-A5 来源经验适用门槛已由规划 Codex 独立复审：完整 canonical 候选驱动的炸弹/通配与自然对子激活、知识字段白名单隔离、八场禁网资格均 ready；相关39、主规则39、全量760项通过。两项目标场景已公开分类为 `lead_opening / opening` 并实际投影对子 C 级来源，但其 `step_no=0` 时手牌为 `18/16/16/16`、总数66，非真实完整开局。故下一项 `docs/NEXT_PROMPT.md` 是 H3-A5b：仅修两项评测 fixture 的108张/每家27张或合法回放可达性并重跑离线资格；此前不启动新真实模型诊断。旧 ledger、Botzone workspace、seed证据均保持原样。

`13b9817` 已完成 H3-A5b，规划 Codex 独立审阅提交、复跑57项相关与762项全量测试。两项开局 fixture 现在均为完整108张双副牌、四家各27张、第0步空历史；八场禁网资格均ready，最终候选数按顺序为6/21/4/50/3/3/4/25，source均为`model`。下一项`docs/NEXT_PROMPT.md`为H3-A6：独立最多8次、重试0真实DeepSeek低敏单点诊断，新fresh ledger；旧H3 ledger、Botzone workspace、seed证据与系统Temp文件保持原样。结果只解释当前fixture的单次选择，不推断旧版同状态改善或胜率。

H3-A6 已有可审计低敏结果：规划 Codex 只读核对 `D:\VsCodeProject\GuanDanH3A2Audit\h3-a6.jsonl` 为普通非链接文件、6730 bytes、SHA-256 `7cb3dd76198929871484a03c44dcb12c362082b3915fe70d8914ae727de863bc`；27条事件与当前HEAD八场离线资格、8对请求起止及summary守恒，账本为8 success、0重试、8个候选/source守恒。指定45项测试独立通过。类别依序`alternative / low_cost_single / other / single / pass_preserve / block / minimum_group / spend_resource`，不能从中还原具体动作或断言策略优劣。下一项`docs/NEXT_PROMPT.md`为H3-A7零网络同状态动作质量代理；旧H3 ledger、Botzone workspace、seed证据和系统Temp文件不清理。

H3-A7 `cb262c5` 已交付六状态零网络同局面动作质量代理。规划 Codex 审阅完整提交，独立复跑相关41项、主规则39项、全量775项，并执行未打桩的六组分支续局：6/6完成、参考动作6/6进入最终候选。两个开局、中局两个、残局族两个均从完整108张单局取得；比较仍只是冻结RuleBased后续策略下的终局/名次代理。当前评测尚以禁网假provider提供ID，未封住真实模型Request、最终候选、原始响应和续局首步的绑定。下一项`docs/NEXT_PROMPT.md`是H3-A7a零网络评测接线与反例测试；独立复审前不做真实模型质量请求，不清理旧ledger或Botzone evidence。

H3-A7a `6e304dc` 已完成零网络真实客户端 transport 接线：规划 Codex 审阅完整提交，独立通过相关46项、主规则39项、全量780项。六个固定样本由禁网假 transport 完成实际请求体/SSE/客户端 ID/source 绑定和未打桩本地续局，报告字节级复现；故障反例固定 fail closed，生产策略未变。下一项`docs/NEXT_PROMPT.md`为H3-A8独立真实模型同状态代理：先六场离线资格，后最多六次/重试零请求，fresh低敏ledger同步审计，遇技术失败即停。不读写旧H3 ledger、Botzone workspace或seed证据；代理结果不是胜率真值。

H3-A8 低敏新ledger `D:\VsCodeProject\GuanDanH3A2Audit\h3-a8.jsonl` 已由规划 Codex 只读核对为5700 bytes、SHA-256 `2fe5525ffe17e1fe5b7335f43fe96d0df878851ec627e81dbd6d342bb1f74a3d`，21条事件的六项资格、六对请求起止、六次success/零重试和summary守恒。当前HEAD独立重建六样本phase/候选数，相关46项及主规则39项通过；终局/名次和代理重算为3 `selected_better`、3 `tie`，没有`reference_better`或`unevaluable`。此结果不是胜率，也不能独立核对网络侧计数或具体动作。下一项`docs/NEXT_PROMPT.md`是H3-A9独立状态队列与至多六次真实模型复核；旧ledger、Botzone workspace及seed证据不触碰。

H3-A9 `6b8bd48` 独立六状态队列已由规划 Codex 复审：当前HEAD重建 seed 920–925 的公开phase/候选数与低敏ledger一致；相关51、主规则39、全量785项通过。`D:\VsCodeProject\GuanDanH3A2Audit\h3-a9.jsonl` 为5724 bytes，SHA-256 `1b374e75a4d034bf1b4a480066867308d0ac75e5d8fc4f718889579c7e0b5fd1`；最终21条事件记录六次success/零重试，比较重算为1 `selected_better`、2 `reference_better`、3 `tie`。执行方披露零网络准备阶段曾移除过早写入的summary，最终文件无法审计这段准备历史；只把它作为客户端侧最终结果账本，不作为不可改写或网络侧独立证明。H3-A8/A9方向混合，下一项`docs/NEXT_PROMPT.md`为H3-A10零网络穷举候选的代理区分度校准，不修改生产策略、不读旧ledger或Botzone evidence。

H3-A10 `ce1a370` 已由规划 Codex 审阅并独立重跑30/39/792项测试及未打桩校准：12个冻结状态的235个最终候选全部完成，参考动作12/12可见；相对同一RuleBased参考的优/平/劣为32/102/101，10个状态有严格差异，2个状态全平。没有生产策略、网络或现场修改。该结果只证明冻结续局代理能区分一些候选，不验证真实策略优劣；旧H3-A8/A9 ledger缺模型动作ID，无法回填其具体排名。当前`docs/NEXT_PROMPT.md`转为H3-A11零网络续局敏感性检查，使用已有FrozenRuleBased作为第二续局，不读取旧ledger或Botzone证据。

H3-A11 `e2b5e43` 由规划 Codex 独立通过相关36、主规则39、全量798项，直接重算总转移矩阵`22,6,4；30,64,8；36,33,32`、两种续局各235/235完成、117次标签改变、40次严格优劣反向；197个候选分支和739个去重公开状态出现真实策略选择差异。此结果使冻结RuleBased续局代理不适合作为生产策略优劣门槛；旧H3-A8/A9低敏结果保持描述性，不追改。项目所有者选择先复盘已有seed`47004`单局证据。固定workspace的六份文件大小/哈希经规划Codex只读复核与既有inventory一致，尚未读取正文或清理。`docs/NEXT_PROMPT.md`现为H3-A12只读历史决策证据复盘，不执行模型、live或代码修改。

2026-09-24 项目所有者进一步明确：先充分整合已找到的攻略到启发式体系的 RAG、公式、公开特征、路由和模型前决策链，再检查旧三处现场问题；未整合前不逐点修补，以免后续整合覆盖或引入冲突。规划 Codex 因此暂停上一段所述独立 H3-A12 旧 trace 复盘 Prompt，改为一个连贯的来源策略整合 Coding 任务；旧 trace 仅在整合后的只读验收中使用。H3-A11 代理敏感性结论仍有效，不再扩建该代理或用其标签判策略优劣。具体当前执行任务以`docs/NEXT_PROMPT.md`最新版本为准。
