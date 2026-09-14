# Coding Codex 执行 Prompt

这是一个新的 Coding Codex 任务。不要依赖其他对话的隐含上下文，请从当前仓库和保留的 seed `47004` evidence 重新建立事实。

你的职责是实现和测试业务代码；项目规划文档由规划 Codex 维护。开始前依次：

1. 阅读并遵守根目录及适用范围内的 `AGENTS.md`。
2. 检查 `.agents/skills/`；本任务不是 live 或 workspace 清理，不得执行这两个 Skill 的现场动作。
3. 阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`。
4. 检查 Git status、HEAD 和最近提交；起点必须能解释，不能把外部修改混入提交。
5. 只读检查 `D:\VsCodeProject\BotzoneWorkspace\decision-trace.json` 中 seed `47004` 的三类目标决策。不得在报告、日志、测试或仓库文件中复制完整手牌、完整 observation/action 列表、binding、run token、模型文本或其他私密内容；测试应使用独立构造、语义等价但不复制现场身份/花色/ID的最小 synthetic fixture。

## 已复审事实

规划 Codex 已按当前 schema 验证该局 24 条 ACK trace 与 v8 audit 守恒。以下是需要由你从文件和生产代码再次确认的低敏结论，不得直接当作未经核对的真值：

- 五张同点数牌的跟牌点由 `model` 选择四张炸弹；四张和五张炸弹均存在于原始、剪枝后及最终 prompt 候选。当前 `control / stable_control` 与 bomb RAG 只表达一般控牌/炸弹时机，没有明确比较“较短同点数炸弹留下孤张”与“较长炸弹清空该点数、减少手数并提高本次压制层级”。
- 自由首出 Q 的决策 source 为 `local_shortcut`，实际来自 `OpeningFormulaStrategy`，没有调用模型。强牌/高控制分支对较高普通单张加分、对小单张扣分，现场等价评分因此选择 Q 而不是孤张小牌；之后用 2 是在跟单张 A 的约束下由模型选择，小牌当时不合法。不要把这两次不同来源、不同约束的动作合并成一个模型错误。
- 自由首出单张 3 的点位中，原始 canonical actions 同时包含单 3 和对 3，但 `_select_transition_actions()` 在存在任意 single 时不保留 pair；对 3 因而不在剪枝后或最终 prompt 候选，模型没有选择它的机会。

## 目标

以公开 observation 和原始 canonical legal actions 为唯一输入，修正这三类策略输入缺口，同时保持 DeepSeek 对合法模型动作的自主权：

1. 自由首出 transition 剪枝必须在 singles 存在时仍保留有代表性的自然 pair，至少保证最小自然对子不会因存在单张而全部消失；继续遵守候选预算、稳定顺序、去重、wildcard/pressure/finishing 保留和原始 action ID 追溯。
2. 调整开局公式的结构取舍，使“强牌且控制资源充足、存在可安全处理的孤张小牌”不再因为固定高点单张奖励而机械选择更高普通单张。必须精确限制范围，保留王/级牌保护、炸弹保护、弱牌与中牌既有语义，并基于真实 `carrier_cards` 计算残余结构；不得读取 engine 私有状态。
3. 给模型一个通用、有限、可验证的残余结构提示，覆盖同点数不同长度炸弹候选：明确提示较短动作若只留下同点数孤张，不能被误称为“保留炸弹”，并要求同时比较剩余手数、残余组合价值和当前压制层级。优先在现有 structured prompt/候选摘要中增加由公开 hand 与 canonical actions 推导的低预算信息；只有确有必要才改 RAG。不得直接替模型选择动作。

实现应寻找一个最小、共享且 fail-closed 的 AI 层残余结构表示，避免为三个现场动作各写硬编码规则。Malformed payload 应退化为旧安全行为，不得阻断合法动作选择。

## 禁止事项

- 不得新增或恢复任何成功模型后的 action override、selector、guard 或 decision source；新生产路径仍不得产生 `teammate_control_block`、`danger_opponent_block`、`short_endgame_plan`。
- 不得把 RuleBased 或 opening formula 的选择作为模型成功后的强制结果。
- 不得修改 `engine/` 规则真值、Botzone 协议/session/audit schema、legacy source 读取兼容或固定项目范围。
- 不得联网运行 Botzone、启动 connector、创建桌、清理或改写现有 evidence。
- 不得读取或输出 `.env`、URL、密钥、token、prompt、模型 response/reasoning。

## 必须新增的回归

至少覆盖：

- free-lead 同时存在 singles 与自然 pairs 时，剪枝和最终 prompt 均保留代表性 pair；输入不变、ID来自原始 actions、候选预算不失控。
- 语义等价的强控制开局 fixture 中，孤张小牌与较高普通孤张并存时，公式不再机械选择较高单张；对子/三张/四张以上的部分拆分保护、王/级牌保护及既有 medium/weak fixture 不回归。
- 同点数四张/五张炸弹均合法时，prompt 同时保留两个原始 ID，并包含可测试的残余孤张/清空点数组语义；fake client 返回任一合法 ID 时都必须原样保留并记录 `model`。
- malformed observation、hand/card token、carrier 或候选不一致时 fail closed，不生成伪造结构结论，不改变合法动作集合。
- 三个 legacy source 仍只读兼容，生产 DeepSeek/adapter 路径扫描无主动产生分支。

## 验证顺序

1. 先运行新增和直接相关的 opening/pruning/prompt/DeepSeek 测试。
2. 运行主规则回归：

   `python -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q`

3. 运行全量：

   `python -m unittest discover -q`

4. 运行 `git diff --check`，并扫描生产路径确认没有旧 source 的主动分支或新的 post-model override。
5. 仅在全部离线测试通过后，可使用 synthetic fixture 做最多 2 次真实 DeepSeek prompt-first 诊断：一例比较四/五张同点数炸弹，一例比较单 3/对 3；总外部模型请求硬上限 2、每例最多 1 次、`DEEPSEEK_MAX_RETRIES=0`。这属于 `AGENTS.md` 已授权的严格少于 10 次诊断。不得保存或输出模型文本，只报告前提、候选可见性、source、原始动作类别和 success/failure。若模型结果仍不理想，报告 `not_ready` 并停止，不得增加后置覆盖或追加请求。

## 提交与报告

只提交本任务的业务代码和 tests，不修改规划 docs。提交前后检查 status/diff，只显式暂存自有文件。

报告必须包含：

- 三处根因的独立结论，尤其区分 local shortcut、模型选择和剪枝不可见；
- 修改文件与设计边界；
- 每组测试的命令和通过数量；
- 若执行真实模型诊断，报告实际请求数、重试数与低敏分类；
- commit hash、最终 Git status、保留的外部修改/evidence；
- 当前范围内尚未解决的真实风险。固定级牌 `2`、四人、无贡、单局是既定范围，不列为风险。
