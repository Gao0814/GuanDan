# Coding Codex 执行 Prompt：5–8 张残局的出后路线比较

> 当前主线回到掼蛋 AI 算法。项目所有者以后自行完成 Botzone 页面和 connector 操作，Codex 只做局后审计；**本任务不写、不启动 Botzone 脚本或 connector，也不沿用已在第 1 槽停止的 M2 32 槽评测。** `offline-m2` 是禁网占位模型名，并非两版真实模型不一致的证据。现有小手牌最少分组提示只覆盖自由领牌 1–4 张；本任务把这项公开残局能力有界扩展到 5–8 张，并直接验证模型是否得到有用的信息。

## 算法目标

在本家 5–8 张、当前自由领牌且完整 canonical 动作可用时，计算每个可见首手出后**若以后重新取得自由领牌**所需的最少合法动作组数；用原始合法 action ID、出后牌型/孤张与控制资源成本把关键路线交给 DeepSeek 比较。这个数只描述本家手牌可分组性，**不保证重新获得牌权、对手不能压制或队友持有什么牌**。一次出完、队友或危险对手公开剩余张数紧急、高价值回手资源须能推翻单纯的少分组倾向。DeepSeek 仍是合法候选中的主要决策者；不新增成功模型后的强制改牌，也不为提高命中率扩张本地直选。

先读适用 `AGENTS.md`、项目 Skills 清单、`README.md`、`CLAUDE.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、`docs/STRATEGY_SOURCE_AUDIT.md`，核对 Git status/diff/HEAD。重点读 `agents/short_endgame_planner.py`、`strategy_router.py`、`strategy_intent_prompt.py`、`deepseek_client.py`、默认 Botzone DeepSeek factory（只做禁网 Request）、`evaluation/h3_model_probe_fixtures.py` 和相关测试。B 级已核对后半程来源可支持按剩余张数、回手牌与非绝对化计划组织输入；不得把 C 级口诀写成硬动作。只改直接相关的 `agents/`、必要 `evaluation/` 与 tests，不改 `engine/`、Botzone 运行代码、`.env`、规划 docs 或封板标签/bundle。

## 同一工作包内的实现与针对性评估

1. 沿用公开 observation 与完整 `legal_actions()` 的 carrier 多重集，不碰引擎私有状态；在 5–8 张范围做有界分组求解，保持重复实体牌、逢人配和 action ID 的原有语义。现有 1–4 张行为必须保持；无完整/可用证据或所有候选等价时不输出伪精度。模型前只展示少量真正有差异的首手及相应条件，不能把未入最终展示候选的 ID 写进 prompt，不能删除对比所需的合法候选，也不能把分组数改写成未来必然手数。
2. 用引擎 preset hands 构造 5–8 张残局，不用现场 seed/action ID 特判。至少包括：自然对子/三张清理与拆单；顺子或连组与分散单张；炸弹残余或通配资源与出后路线；以及队友或危险对手公开剩余张数紧急的反例。每例先定义要检查的**能力**和可以推翻少分组路线的公开条件，再检查当前与新模型前输入如何描述原始候选。可补一个未参与提示调试的变体；若采用网上经典残局，登记确切出处并按本项目规则重建，不把他人私局暗牌当作 Agent 已知信息。
3. 在默认 factory 的禁网实际 Request 中验证来源适用、推荐与最终候选闭环、合法原始 ID、模型返回保真和出后路线文本。既有 1–4 张、小手牌直接出完、跟牌、队友/危险对手与 malformed payload 回归必须通过。不要以 prompt 长短、候选数或 RuleBased 续局标签单独宣称策略提高。
4. 若配置可用，在同样的 **3–4 个针对性残局**上做修改前/修改后各一次真实 DeepSeek 选择，单任务总请求最多 `8`、零自动重试；此额度属于项目 `AGENTS.md` 已有的少于 10 次授权，不与旧 32 槽任务拼接。两侧以进程环境统一设 `DEEPSEEK_MODEL=deepseek-flash` 并由 `config.py` 读取，保持相同超时/温度与合法动作，不读取或修改 `.env`；记录低敏动作 ID/牌型、能力类别、耗时、成功/失败与 source，不保存 prompt/自由文本/密钥。某次请求失败只记该例不可比较，不因非关键字段差异废掉其余有效例子，也不补请求凑结果；没有可用配置则交付禁网算法实现并明示真实选择未测。

## 验收与交付

- 5–8 张针对性残局至少有若干首手的公开分组路线出现真实差异，模型前信息能解释差异及反例；所有展示 ID 属于最终原始合法候选，成功模型返回仍保持原始 ID 和 `model` source。测试既覆盖有利例，也覆盖少分组不该成为绝对指令的反例。
- 真实对照若完成，按每个能力场景报告修改前后动作类别和可观察的出后用途，明确改善、无变化、退化或不可比较；少量场景只说明这项能力的定向证据，不外推为总体胜率。项目所有者日后手工提供的十局 Botzone 胜负/异常结果另由 Codex 审计，作为方向性补充，不阻挡本任务提交。
- 运行相关 `unittest`、主规则回归、适用全量测试与 `git diff --check`。只提交本轮自有算法、评测和测试文件；报告真实请求数（最多 8）、重试数、测试、commit、最终 Git status 和当前范围内真实限制。不得运行 Botzone/live/connector/browser，不触碰两个 workspace 的旧证据。
