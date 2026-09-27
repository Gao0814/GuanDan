# Coding Codex 执行 Prompt：M2 扩大评估真实阶段（待专项授权）

> 起点：`2fafc822a02b94eda7754af8cf7cbd2ca986007f` 已提交 8 个冻结状态、16 条双版本禁网资格和固定 32 槽评测器。**项目所有者尚未批准这 32 次真实 DeepSeek 请求。未获得对本任务最多 32 次的明确授权时，本 Prompt 只作为后续执行交接，不启动真实请求，也不拆成多个小于 10 次的任务。** 既有首轮 8 次真实请求属于已完成的另一轮，不算本轮授权或效果结论。

## 任务与阶段门槛

取得上述专项授权后，完成**同一个 M2 扩大比较任务**：对已冻结的 8 个生产模型状态，在 `9/26_v0` 封板 baseline 与当前 M1 版各执行两次，最多 `8×2×2=32` 次新增真实请求，零自动重试；比较同状态候选覆盖、同版波动、跨版原始选择、固定 RuleBased 双分支续局代理与决策耗时。它不是胜率实验，不能用一两个动作决定整体算法优劣。授权未到时维持 `M2=inconclusive` 和当前 M1 生产版。

先读适用 `AGENTS.md`、项目 Skills 清单、`README.md`、`CLAUDE.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、`docs/STRATEGY_SOURCE_AUDIT.md`、[扩大评测器](../evaluation/m2_expanded_same_state_eval.py)、[首轮评测器](../evaluation/m2_same_state_model_eval.py)及其测试，核对 Git status/diff/HEAD。只修改完成真实评估所必需的 `evaluation/`、tests；不改生产 `agents/`、引擎、RAG、Botzone、`.env`、规划 docs、封板标签/bundle，不访问两个 Botzone workspace。baseline 使用隔离 Git worktree，不 reset/checkout 活动 `cao`；只提交自己产生的文件。

## 已冻结输入与离线检查

使用评测器固定选出的状态，不重新搜更好看的样本、不换区间、不改变选择标准：

| 冻结状态 | seed / step | 原始合法候选 | 两版最终候选 | 完整关系数；双端可见 baseline→current |
| --- | ---: | ---: | ---: | ---: |
| `opening_dense_1` | `150001 / 0` | 255 | 80 / 77 | 70；12→17 |
| `opening_dense_2` | `150002 / 0` | 210 | 80 / 80 | 59；18→24 |
| `opening_diverse_1` | `151002 / 0` | 79 | 55 / 56 | 11；8→9 |
| `opening_diverse_2` | `151004 / 0` | 77 | 53 / 55 | 12；10→11 |
| `midgame_pressure_resource` | `160008 / 8` | 7 | 7 / 7 | 2；2→2 |
| `midgame_team_danger` | `160011 / 8` | 8 | 8 / 8 | 2；2→2 |
| `endgame_1` | `170000 / 28` | 4 | 4 / 4 | 0；0→0 |
| `endgame_2` | `170001 / 28` | 3 | 3 / 3 | 0；0→0 |

Coding 已报告两版共 16 条禁网实际 Request 资格通过、公开状态与完整 canonical 动作摘要一致、fake 返回展示 ID 后 `source=model`。这只是离线资格，真实发送前重新核对封板 tag 指向、当前 M1 祖先、八个状态摘要哈希、版本独立资格、推荐和候选闭环、请求控制指纹、模型设置与 `119` 秒决策预算；任何漂移即停止，不挑替补。H3-A9 `opening_2` 是反事实历史行，不纳入八状态生产比较。读取配置不得展示或持久化密钥、URL、prompt、响应、reasoning 或异常正文。

## 授权后的真实执行

现有 `run_authorized_expanded_requests` 默认拒绝无授权调用，固定 32 槽顺序且每槽最多一次。它接受 `request_once` 回调；如尚无安全的实际调用入口，只补最小接线，复用首轮 `probe_version_state(..., real=True)` 的生产 SSE/default transport/`urlopen` 计数路径，并先用禁网 fake 回归证明无授权零调用、真实发送计数、版本绑定和失败停止。**只有实际收到项目所有者对本任务最多 32 次的明确授权，才可将 `owner_authorization_confirmed=True` 交给入口并执行。** 不把参数自身当授权证据。

按奇数状态 baseline/current/current/baseline、偶数状态反序执行；每版同一模型、温度、超时与 119 秒整次预算。每次已发送请求计入总上限，失败、超时或非法建议保留固定分类并计数，不重试、不补位、不把 fallback 当模型成功。预发送故障、API 预检不可用、请求/状态绑定不一致或发送状态不明时停止；不以再次执行整轮来规避预算。每次只保存低敏状态摘要、版本、顺序、原始合法 ID、固定 source/outcome、计数、单调耗时及代理聚合，不保存模型自由文本或连接细节。

每次成功的原始选择都与该版自己的离线候选和参考动作绑定，再算公开动作后果及固定 RuleBased 双分支续局。按八个状态逐项报告两次同版选择、跨版差异、单张/对子/三张/顺子/炸弹与通配占用及出后剩牌用途；区分模型行为、规则代理方向和未知的真实胜率。若结果方向混合或同版波动明显，结论仍为 `inconclusive`，不为制造结论改生产动作或成功模型返回的 ID。

## 验收与交付

- 记录授权对应的任务上限；报告实际请求数、发送入口计数、成功/超时/失败分类、零重试与停止位置，必须能说明 32 槽中的每一实际尝试。规划与 Coding 均不得把既有 16 条禁网资格、首轮 8 次请求或本轮预发送失败计作本轮 provider 成功。
- 相关 `unittest`、主规则回归、适用全量测试及 `git diff --check` 通过；只提交本轮自有评测/测试文件，交代 commit、最终 Git status 与任何未解决的评估限制。
- 给规划可复审建议：保留 M1；若发现可重复、可归因的具体退化则另拟有界修正；若仍不足以判定则维持 `inconclusive`。不启动 Botzone/live/connector/browser/preflight，不轮换个人或固定 workspace。
