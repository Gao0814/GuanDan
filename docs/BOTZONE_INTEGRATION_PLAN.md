# Botzone 本地 AI 接入计划

更新时间：2026-08-09

## 0. Step L0-A1：手动建桌无贡 profile 官方协议封板（2026-08-09）

### 0.1 唯一判定

`botzone_manual_no_tribute_phase0_blocked`

此判定只针对 `Botzone GuanDan manual-table no-tribute profile` 的 Phase 0；它不改变 K-A3d3b、K-A3d3c2 或 K-A3d3c3a 的任何结论。阻塞不是网络、账号密钥或本地 engine 的问题，而是手动 `play` adapter 所必需的官方裁判 claim 语义尚未公开可核。不得据此实现 connector、adapter、创建桌子、加入对局或调用本地 AI。

### 0.2 仅采用的官方来源

| 来源 | 固定版本 / 核对日期 | 证据类型 | 可直接确认的范围 |
|---|---|---|---|
| [本地 AI](https://wiki.botzone.org.cn/index.php?title=%E6%9C%AC%E5%9C%B0AI&oldid=2230) | `oldid=2230`；2026-08-09 | 官方 Wiki 词条与官方 Python/C++ 样例 | GET 长轮询、`m n` 首行、`2*m` match/request 行、finished row、`X-Match-<match_id>`、多 match、`runmatch` Headers。 |
| [Bot](https://wiki.botzone.org.cn/index.php?title=Bot&oldid=2245) | `oldid=2245`；2026-08-09 | 官方 Wiki 词条 | 常规 Bot 的 JSON/simple-IO 历史语义；不能把它当作 local-AI 网关重放保证。 |
| [GuanDan](https://wiki.botzone.org.cn/index.php?title=GuanDan&oldid=2497) | `oldid=2497`；2026-08-09 | 官方 Wiki 规则、字段定义与 request/response 样例 | 108 ID、`deal`/`tribute`/`return`/`play`、`[action, claim]`、pass、近四手 history、`global` 字段。 |
| [GuanDan 游戏详情](https://www.botzone.org.cn/game/GuanDan) | 2026-08-09 | 官方详情页访问尝试 | 官方页面在本次核对中未返回可读取的裁判源码、样例或调试 fixture；不能用搜索摘要、第三方实现或 UI 截图替代。 |
| 目标账号“本地 AI 配置”页面 | 2026-08-09 | 登录后非敏感权限元数据 | **未核验**：本次没有可用的已登录账号页面。官方公开账号页面说明功能面向等级 6 及以上的活跃用户；目标账号是否满足仍须由该页面的非敏感状态确认。 |

所有 URL、版本和内容只用于文档引用；不记录本地 AI URL、连接密钥、match ID、Header 值、账号身份或个人资料。

### 0.3 confirmed / unsupported / unknown

| 项目 | 状态 | 官方依据或边界 | 对手动无贡路径的影响 |
|---|---|---|---|
| 108 ID 映射 | **confirmed** | 每副为 `0..53`；普通牌按 `h,d,s,c`，从 A、2 到 K；`52` 小王、`53` 大王；`54..107` 重复。 | 可进入后续离线 codec 设计；当前 `engine.cards` 的 `S,H,C,D` 和无副本模型不能直接当作平台 ID。 |
| `deal` | **confirmed** | `stage="deal"`，`deliver` 为本家 27 张实体 ID，`your_id` 为座位；response 是 `[]`。 | 可作为无贡 profile 的允许 stage。 |
| `play` 基础形状 | **confirmed** | response 是 `[action, claim]`；两者均为整数 ID 数组；无配子时二者相同；pass 精确为 `[[], []]`。 | 普通牌和 pass 的协议形状可封板。 |
| `play.history` | **confirmed** | 仅近四手，包含 pass；每项含 `player` 与同结构 `response`。 | session 必须持久化近四手之外所需的公开状态；不能从单 request 重建完整本局。 |
| `global.level`、`done`、`pass_on` | **partially confirmed** | `global.level` 是本局等级；`done` 标记已出完玩家；`pass_on` 标定接风上下文，官方样例给出 `-1`。 | `done/pass_on` 的完整状态机和值域未封板，adapter 不能自行推断先手或接风转移。 |
| 配子实体 | **confirmed** | 红桃级牌是配子，可代替任意非大小王牌。 | 与本地 `carrier_cards` / `wildcard_info` 的概念可对接，但不足以编码 claim。 |
| 配子 claim 的花色、副本、排序、重复和 canonical 规则 | **unknown — P0 blocked** | Wiki 只说 claim 是整数 ID 的“宣称牌型”；未规定声明 ID 是否必须保留具体花色/副本、两个同牌副本是否可交换、是否排序、ID 重复/范围的 judge 规则。 | 不能把本地常规 `declared_cards`（常常无花色）无歧义编码为 claim；禁止实现 play adapter。 |
| 单手配子数量及多配子牌型约束 | **unknown — P0 blocked** | Wiki 未给出单手最大数量，也未给出炸弹、顺子、连对、钢板、同花顺中多配子的裁判约束。 | 当前 engine 每手最多一个配子只是本地规则，不能假定等价。 |
| 无贡手动桌首个 `play` 先手 | **unknown — P0 blocked** | Wiki 只说明“如不需贡牌，则由上游者领出”；没有官方无贡手动桌的第一局/新桌 `first` 或首个 `play` fixture。 | 不得从贡还规则、截图或本地默认 player 1 推导。 |
| 无贡时严格跳过 `tribute/return` | **unknown — P0 blocked** | 用户明确要求手动选择“需要进贡=否”，但本次仅有官方通用阶段文档，未得到该配置的官方请求序列。 | profile 必须在未来识别 `tribute/return` 并 fail-closed；不能宣称其不会出现。 |
| 贡/还/抗贡/双贡/跨局升级 | **unsupported** | 当前项目只实现单局 play；无 tribute/return/resist/升级状态模型。 | 任何此类 stage 一律 `unsupported_stage`，不调用 Agent、不伪造 pass。 |
| local-AI GET / Header / 批量 match | **confirmed** | 本地 AI词条规定 GET、首行 `m n`、request/finished 行和 `X-Match-<match_id>`；样例按每 match 维护 pending response。 | connector 只能作为后续实现；当前不实现。 |
| local-AI 重放、提交成功确认、服务端超时秒数 | **unknown** | 官方样例在 URL/HTTP error 后重试，但没有给出 exactly-once ack 或固定长轮询秒数。 | 后续 connector 需保守持久化 pending response；不得承诺重放语义。 |
| `runmatch` / `X-Initdata` 无贡表达 | **unknown — optional** | 官方只定义 `X-Initdata` 为可选初始化数据，未给 GuanDan 无贡值。 | 仅阻塞自动建桌；不阻塞手动建桌的 Phase 1–3。 |
| 目标账号可用本地 AI | **unknown — account prerequisite** | 官方账户说明的公开门槛为等级 6 及以上活跃用户；目标账号必须在登录后页面显示可用才可进入真实 smoke。 | 不阻塞离线 Phase 1–3；阻塞任何真实 local-AI 使用。 |

### 0.4 action / claim 与当前 engine 的封板

已确认的无歧义部分：

- `Action.make_pass()` 必须编码为 `[[], []]`；
- 无配子的 canonical action 只能把同一组**真实实体 ID**同时填入 action 与 claim；
- action 是真实 carrier，claim 是配子替代后的声明；两副相同牌必须在 session inventory 中保留原 ID，不能仅按 token 扣牌；
- 当前 `Action.carrier_cards`、`Action.declared_cards` 和 `WildcardInfo` 是 adapter 输入候选，而不是 Botzone 输出真值。

未确认且因此禁止编码的部分：

- 用于普通单张/对子/三张/炸弹/顺子/连对/钢板的 `declared_cards` 通常没有具体花色；官方未说明 claim 应如何选择对应实体 ID；
- 配子把红桃级牌声明成同花顺或其他指定花色时，claim 是否必须是该花色实体 ID、可否使用另一副同牌副本、是否要求 canonical 排序；
- 多配子在同一手、各类牌型和炸弹中的上限与 judge 行为；
- claim 中 ID 的范围、重复、重复副本的交换性和非法排序的裁判处理。

必须从 GuanDan 游戏详情页可下载的官方裁判源码、官方样例程序或官方调试 request/response fixture 取得上述证据后，才允许 L1-A1 实现 codec 或 play adapter。

### 0.5 无贡手动桌与 transport 的操作边界

用户侧手动操作的唯一目标 profile 为“建桌时选择需要进贡=否”。在官方配置序列尚未取得前，Phase 0 不承诺 `deal` 后一定直接 `play`，也不承诺首个 player；未来 dispatcher 只允许已确认的 `deal` 与可验证的 `play`，遇到 `tribute`、`return` 或未知 stage 必须停在 `unsupported_stage`。

本地 AI 官方词条确认：手动创建或加入桌后可选择“用本地AI替代我”；local-AI 是本机向 opaque URL 发起 GET 的长轮询，不是本机开放端口。一次 GET 可以包含多个 match，finished row 的玩家数为 `0` 表示异常结束。真实 URL、Header 值和 response 内容均不进入文档、日志或测试 fixture。

## 1. 任务目标与可行性结论

任务编号：Step L（Botzone 本地 AI 接入）。

目标是在不改变现有 AI 边界的前提下，让本机连接器通过 Botzone 本地 AI 接口参与 GuanDan 测试对局，用真实平台对手验证 RuleBasedAI 或其他本地策略的合法性、稳定性和实际对抗表现。

第 0 节的 `botzone_manual_no_tribute_phase0_blocked` 是当前唯一 Phase 0 判定。本节保留的规划只说明解除第 0 节列明阻塞后的候选范围，不构成 connector、adapter 或真实桌授权。

- 本地 AI 传输层可行性高：官方协议是由本机发起的重复长轮询 GET，不需要公开本机端口，也不是上传源码或 WebSocket。
- play 阶段 adapter 尚被第 0 节列明的官方 claim、配子数量和无贡阶段证据缺口阻塞；不得实现或声称可用。
- 用户提供的建桌设置截图确认“需要进贡”可选择“否”，且默认测试对局采用该配置；因此首期真实 smoke 的支持范围可以收敛为 `deal + play`。
- 当前 engine 没有贡还能力不再阻塞无贡模式接入；但 adapter 必须识别 `tribute / return` 并以 `unsupported_stage` fail-closed，不能返回空响应、pass 或任意牌绕过。
- 规则一致性尚未完全证明：Botzone `claim` 的精确牌 ID 表示、单手配子数量上限仍需从官方裁判源码或官方样例封板。
- 首期使用网页手动建桌并明确选择“需要进贡=否”；`runmatch X-Initdata` 只属于后续自动化能力，其未知状态不再阻塞 Phase 1–3 或手动 smoke。
- RuleBasedAI 可作为第一阶段默认 AI，但它只保证从合法动作中稳定选择，不代表已有强对抗能力。真实 smoke 只能证明接入正确；实力判断需要座位平衡和固定对手的小批量统计。

本任务不得改变以下边界：

- `engine/` 继续提供出牌规则真值；
- `agents/` 只接收转换后的公开 observation 和 canonical `legal_actions`，只返回原始合法 `action_id`；
- adapter 查找该 `action_id` 对应的原始 action 后再编码 Botzone response；
- Agent 不得生成 Botzone 牌 ID、`action` 或 `claim`；
- 真实连接 URL 和密钥仅作为不透明的环境变量或启动参数传入，不写入源码、测试、文档示例或日志；
- 第一阶段默认使用 `RuleBasedAIAgent`，不使用 DeepSeek。
- 支持范围固定标记为 `Botzone GuanDan no-tribute profile`；贡还模式和跨局升级均为非目标。

## 2. 已核实的官方协议

以下事实来自 Botzone 官方页面，核对日期为 2026-08-05：

- [本地AI词条](https://wiki.botzone.org.cn/index.php?title=%E6%9C%AC%E5%9C%B0AI)，固定版本 `oldid=2230`；
- [Bot 交互词条](https://wiki.botzone.org.cn/index.php?title=Bot)，固定版本 `oldid=2245`；
- [GuanDan 词条](https://wiki.botzone.org.cn/index.php?title=GuanDan)，固定版本 `oldid=2497`；
- [GuanDan 游戏详情](https://www.botzone.org.cn/game/GuanDan)。

### 2.1 本地 AI 传输

1. 用户手动创建/加入游戏桌并勾选“用本地AI替代我”，或调用官方 `runmatch` API。
2. 本机连接器向账号页面生成的本地 AI URL 发起 GET；该 URL 包含敏感身份和密钥，程序必须整体当作 opaque secret。
3. GET 可能阻塞到有新 request 或服务端超时，属于长轮询，不是长连接流或 WebSocket。
4. 返回文本首行为 `m n`：有新 request 的对局数和已结束对局数。
5. 后续 `2*m` 行按“match ID、该回合 request”成对出现；再后续 `n` 行是结束信息。
6. 连接器把已完成 response 放入下一次 GET 的 `X-Match-<match_id>` Header。
7. 一次轮询可同时承载多个 match，必须按 match ID 隔离状态。
8. 结束行包含 match ID、本地 AI 座位、玩家数和各玩家分数；玩家数为 0 表示对局异常终止。
9. 官方未规定固定的服务端长轮询秒数；样例只在 URL/HTTP 错误或超时后等待并重试。

`runmatch` 官方 Header 为 `X-Game`、`X-Player-0..n` 和可选 `X-Initdata`。参与者必须有且只有一个 `me`；其他位置填写 Botzone 已有 Bot ID。创建成功返回 match ID。

### 2.2 Bot 通用交互与本地 AI 的区别

- 普通短生命周期 Bot 的 JSON 输入包含该 Bot 过去全部 `requests/responses`，并可携带 `data/globaldata`。
- GuanDan Wiki 中展示的是单回合游戏 request；本地 AI 网关按官方词条优先返回 simple-IO request，并由连接器自身持续运行。
- 本地 AI 专用接口没有承诺在连接器重启后重放整场历史，也没有说明会转发普通 Bot 的 `data/globaldata` 外层对象。
- 因此不能把普通 Bot 的“完整 requests/responses”保证直接套到本地 AI 连接器；连接器必须有自己的按局恢复机制。

### 2.3 GuanDan 阶段与数据

- 牌 ID 为 `0..107`。`0..53` 是第一副牌，`54..107` 重复同一牌面。
- 每副牌中普通牌按 `h, d, s, c` 排列；`0..3` 为四种花色的 A，`4..7` 为四种花色的 2，依次到 K；`52/53` 为小王/大王。
- `deal`：request 含 `deliver` 27 张牌和 `your_id`；response 是空数组。
- `tribute`：需要进贡；response 是贡牌 ID 数组。
- `return`：需要还贡；response 是还牌 ID 数组。
- `play`：response 为 `[action, claim]`。`action` 是真实打出的 ID；`claim` 是配子替代后的声明牌型。没有配子时二者相同；pass 为两个空数组。
- `play.history` 只包含近四手、包括 pass；每项含 `player` 和同结构 response。
- `done` 标记已出完玩家；`pass_on` 表示接风上下文。
- `global` 总是提供 `level`，并可能提供 `tribute`、上一局 `first/last`、`resist`、`tribute_cards`、`return_cards`。
- 用户提供的当前建桌 UI 显示“需要进贡”可选“否”；本项目只支持该无贡配置。该截图用于确认项目配置范围，不替代官方协议或裁判语义文档。
- 平台协议仍可能出现 `tribute / return`；在本项目无贡 profile 中出现这些 stage 代表建桌配置或协议状态不符合支持范围，必须安全终止该 match。

## 3. 协议与规则差异表

| 维度 | 当前项目 | Botzone GuanDan | 处理位置 / 结论 |
|---|---|---|---|
| 玩家编号 | `1..4`，1/3 与 2/4 组队 | `0..3`，0/2 与 1/3 组队 | adapter 固定 `botzone_id + 1`，测试座位和队伍保持 |
| 牌面编码 | `Card(rank, suit)` / token；无副本 ID | `0..107`，两副牌 ID 不同 | `cards.py` 保留 ID inventory；token 仅给 engine/Agent |
| 花色顺序 | token 使用 `S/H/C/D` | ID 余数顺序 `h/d/s/c` | 明确映射，不依赖枚举顺序 |
| 点数顺序 | token `A,2..K,SJ,BJ` | 每副牌普通 ID 从 A、2 到 K，再 joker/Joker | 公式+108 张穷举测试 |
| 发牌 | `reset()` 自己洗牌并给四家 27 张 | `deal.deliver` 只给本家 27 张 | 不调用随机 reset；session 接受平台发牌 |
| 副本身份 | 两张同花同点不可区分 | 两张同牌有不同 ID | 输出前按当前 ID multiset 决定实体 ID，不能只反向 token |
| 局前阶段 | 无 | 建桌可选择是否进贡；协议定义 `tribute / return / resist / double tribute` | 仅支持“需要进贡=否”；识别其他 stage 后 `unsupported_stage`，不实现策略 |
| 开局领牌者 | 构造参数 `starting_player_id` | 无贡模式的领牌信息仍须以官方 request/global fixture 为准 | session 只消费已确认字段，不从贡还规则或截图猜测 |
| 出牌历史 | engine 保存完整 history | request 只给近四手 | session 去重累计公开事件；不能只看单次 request 做全局统计 |
| 完赛/接风 | engine 内部推进并公开 finish order | `done`、`pass_on` | adapter 转为公开 observation；过渡需去重 |
| 合法动作 | `BaseRuleEngine` 输出 `Action`，`GuanDanGame` 分配 `action_id` | 平台要求 ID 数组 | integration 构造单玩家 `GameState` 投影并序列化 canonical actions |
| pass | canonical pass action | `[[], []]` | action adapter 固定转换 |
| 普通出牌 | `carrier_cards` 与 `declared_cards` | `action` 与 `claim` 相同 | 用 inventory 中实际 ID 同时填两边 |
| 配子出牌 | carrier 与 declared 分离，`wildcard_info` 显式 | `action` 与 `claim` 可不同 | 只从被选 canonical action 转换；精确 claim 编码仍是 Phase 0 阻塞项 |
| 配子数量 | 当前实现每手最多 1 张 | Wiki 未明确每手最多几张 | **不确定**；必须查官方裁判源码，不得假设相同 |
| 牌型/比较 | 当前 SPEC 的单局规则 | Wiki 规则文字相近，但未完整给出所有 judge 比较细节 | Phase 0 建立官方差异 fixture；不以名称相同视为等价 |
| 终局结果 | engine 自己计算 winner/draw | gateway 结束行给各玩家 score | 以平台结束结果为审计真值；本地结果只用于测试 |
| 跨局升级 | 不支持 | 建桌可显式设置双方等级和上一轮名次 | 只消费当前测试桌给出的本局公开配置；不实现升级赛或贡还 |

## 4. 推荐目录与模块职责

建议使用 `integrations/botzone/`，不在 `engine/`、`agents/` 或现有 `cli/` 中加入连接逻辑：

```text
integrations/
  botzone/
    __init__.py
    models.py
    cards.py
    protocol.py
    session.py
    profile.py
    play_adapter.py
    runner.py
    connector.py
    __main__.py
```

| 模块 | 职责 | 禁止事项 |
|---|---|---|
| `models.py` | frozen/slots 的 poll、match result、stage request、pending response 数据模型 | 不读环境、不联网 |
| `cards.py` | 108 ID 双向映射、ID inventory、确定性实体牌选择 | 不丢副本 ID，不做策略 |
| `protocol.py` | 解析 `m/n` 文本、编码/校验 `X-Match-*`、解析 GuanDan stage JSON | 不调用 Agent，不重试网络 |
| `session.py` | match ID 隔离、事件去重、手牌/人数/完成状态、pending response 和持久化恢复 | 不保存 URL/密钥，不依赖单例全局状态 |
| `profile.py` | 验证无贡配置；允许 `deal/play`，识别并拒绝 `tribute/return` | 不实现贡还策略，不用空响应或随意动作绕过 |
| `play_adapter.py` | Botzone 公共请求→engine 规则投影→observation/legal actions；action ID→`[action, claim]` | 不让 Agent 看 Botzone ID，不调用 engine 私有状态 |
| `runner.py` | 按 stage 调度；play 默认调用 `RuleBasedAIAgent`；统一 fail-closed | DeepSeek 不作为默认值 |
| `connector.py` | 可注入 transport 的长轮询、超时/退避、批量 Header、完成通知和脱敏日志 | 不输出完整 URL/Header/response |
| `__main__.py` | 独立启动入口 | 不修改现有 `cli/run_4ai_debug.py` |

第一版优先使用标准库 HTTP 客户端，不新增依赖。连接配置模块不得导入会自动读取仓库 `.env` 的配置路径；只从显式环境变量或启动参数取得 opaque URL。环境变量名称可以文档化，但不得给出真实或可用示例值。

## 5. 完整消息流

```mermaid
sequenceDiagram
    participant Local as 本机 Botzone Connector
    participant Store as Match Session Store
    participant Gateway as Botzone Local-AI Gateway
    participant Judge as Botzone GuanDan Judge
    participant Adapter as Protocol/Stage Adapter
    participant Rules as engine BaseRuleEngine
    participant AI as RuleBasedAIAgent

    Local->>Gateway: GET opaque local-AI URL + pending X-Match headers
    Gateway->>Judge: 提交上一回合 response
    Judge-->>Gateway: 生成 stage request 或终局分数
    Gateway-->>Local: m n + match/request pairs + finished rows
    Local->>Store: 按 match_id 去重并恢复/创建 session
    Local->>Adapter: 解码当前 stage request
    alt deal
        Adapter->>Store: 保存 your_id、level、27 张实体 ID
        Adapter-->>Local: []
    else tribute/return or unsupported stage
        Adapter->>Store: 标记 profile mismatch / unsupported_stage
        Adapter-->>Local: 不生成响应，安全终止该 match
    else play
        Adapter->>Store: 恢复本家手牌、公开历史、done/pass_on
        Adapter->>Rules: 当前手牌 + level + leading action 的单玩家规则投影
        Rules-->>Adapter: engine Action 集合
        Adapter->>AI: 转换后的公开 observation + canonical legal_actions
        AI-->>Adapter: 原始合法 action_id
        Adapter->>Adapter: 查回原 action，编码实体 action 与 claim
        Adapter-->>Local: [action, claim]
    end
    Local->>Store: 原子保存 request hash、response、pending transaction
    Note over Local,Gateway: 下一次成功 GET 前保留 pending response；传输失败不丢响应
```

关键边界：Botzone Gateway 只与 connector 通信；Agent 不直接接触网络、match ID、Botzone 牌 ID、连接 URL 或 Header。

## 6. 状态、持久化与重连

### 6.1 会话状态

每个 match ID 独立保存：

- 协议版本和 stage；
- `your_id`、level、已确认的无贡 profile 和必要公开本局配置；
- 初始和当前本家 Botzone ID multiset；
- 去重后的公开 play 事件、各玩家剩余张数、done 顺序和 pass_on；
- 最新 request digest、已生成 response、pending/acknowledged 状态；
- 不含密钥的诊断计数。

### 6.2 持久化策略

- 内存 map 只作工作集，不能作为唯一真值。
- 每次生成 response 前后使用原子 snapshot 或 append-only journal，目录位于显式 runtime state dir，不放在仓库 `logs/`。
- snapshot 不保存本地 AI URL、密钥、完整 HTTP Header 或环境变量。
- 相同 request digest 必须返回完全相同 response，避免重试导致策略随机漂移。
- 只有携带 pending Header 的 GET 成功返回后，才把该 pending transaction 标为已发送；传输异常时保留并重发同一 response。
- 收到 finished row 后归档最小聚合结果并删除活动手牌状态。
- 启动时若收到非 `deal` request 且本地无可恢复 session，整体 fail-closed，不猜手牌、不伪造 pass；收到 `tribute/return` 同样 fail-closed。

### 6.3 历史恢复边界

Botzone `play.history` 只有近四手，不足以恢复本家当前手牌和完整公开历史。正常运行依赖本地 durable session；不能声称仅靠当前 request 可从任意中途恢复。后续若官方确认本地 AI 会重放全部历史，可再简化，但实现前不得假设。

## 7. 分阶段实施计划

### Phase 0：官方协议核实与差异清单

状态：基础调研已完成，唯一判定为 `botzone_manual_no_tribute_phase0_blocked`。下一步 Step L0-A2 需要用户辅助取得并审计官方裁判源码、官方 fixture 和脱敏账号可用性证据；不得通过重复检索已封板 Wiki 推断缺失语义。runmatch initdata 单独作为可选自动化未知项。

工作：

- 保存官方页面固定版本、核对本地 AI poll/Header/runmatch 协议；
- 从官方 GuanDan 裁判源码或脱敏真实调试 Log 确认 claim、配子数量和无贡模式的 request 顺序；
- 把“需要进贡=否”定义为唯一支持的 Botzone profile，并确认手动建桌可以稳定选择该配置；
- 核实 `runmatch` 的 `X-Initdata` 如何无歧义表达“需要进贡=否”；未确认前不使用 runmatch，但不阻塞手动建桌路径；
- 在登录后的账号设置页确认当前部署的本地 AI 等级门槛；
- 建立不含真实 URL、密钥、match ID 或手牌的协议差异表和脱敏 fixture 清单。

验收：

- 所有字段标为 confirmed/unsupported/unknown，不以第三方实现补官方空白；
- `deal/play` 的字段与顺序有官方依据；`tribute/return` 能被精确识别并返回统一 unsupported 诊断；
- claim 编码可无歧义映射当前 canonical action；
- 确认账号权限和手动桌选择方式；runmatch 前置可保持独立 unknown；
- 未读取或持久化任何真实密钥。

未满足以上条件时，唯一状态为 `botzone_manual_no_tribute_phase0_blocked`，不得进入 L1-A1 或真实连接。

### Phase 1：纯协议模型与卡牌映射

工作：实现 `models.py/cards.py/protocol.py`，加入官方脱敏 fixture；不联网、不调用 Agent。

验收：

- 108 个 ID 全量双向映射；两副同牌 round-trip 后仍保留原 ID；
- `deal/play` request/response 严格编解码；`tribute/return` 至少严格解析 stage 标识并以 unsupported 结果拒绝；
- poll 的多 request、多 finished、异常终止和 CRLF/LF 均有测试；
- Header 名和值拒绝换行注入；未知 stage/字段/type 整体失败；
- 不读取配置、环境变量或 `.env`。

### Phase 2：连接器骨架与 mock Botzone

工作：实现可注入 transport、session store、pending response 事务和独立 module 启动入口；只连 mock transport。

验收：

- mock 覆盖阻塞 poll、超时、HTTP 错误、重试、多 match 和 finished；
- 失败重试不丢失或改变 pending response；
- 重复 request 幂等；多会话手牌/历史完全隔离；
- 进程重启后从临时 state dir 恢复；无状态中途 request fail-closed；
- 日志和异常不含 URL、密钥或完整 Header。

### Phase 3：连接 RuleBasedAI 的端到端回合测试

工作：实现 `profile.py/play_adapter.py/runner.py`，完成无贡 profile 的 `deal + play` 链路；不联网、不实现贡还路径。

验收：

- adapter 只用公开 request/session 生成 observation 和 legal actions；
- `RuleBasedAIAgent` 返回值经 `require_legal_action_id` 和原始 action 映射双重验证；
- pass、自然出牌、配子 action/claim、接风和玩家完成均通过；
- 每个输出都可追溯到原始 legal action，未知输入不伪造动作；
- 单玩家规则投影与 `GuanDanGame.legal_actions()` 在可构造同状态 fixture 上等价；
- deal→多轮 play 的脱敏端到端脚本完成；
- 任一 `tribute/return` 输入都不调用 Agent、不生成动作，并稳定返回 `unsupported_stage`；
- 通过后只能标记 `botzone_no_tribute_adapter_verified`，不得标记完整 Botzone GuanDan 支持。

### Phase 4：真实 Botzone 小规模 smoke test

前置：用户明确授权联网；Phase 0-3 全部通过；账号权限已确认；URL/密钥只存在进程环境或显式参数中。

工作：

1. 先手动创建测试桌，明确把“需要进贡”设为“否”，验证 deal 到终局；
2. 只有在官方资料确认 `X-Initdata` 的无贡表达后，才用 runmatch 与三个指定现有 Bot 创建至多四局，并让 `me` 轮换四个座位；
3. smoke 通过后，可另行预注册固定对手的小批量观察性对抗评测。

验收：

- 无非法 response、超时、断线丢状态或跨局污染；
- 实际只出现已支持的 deal/play；若出现 tribute/return，则该局按配置错误失败，不计为接入成功；
- 保存聚合的完成数、异常数、座位、平台 score 和耗时，不保存请求正文、手牌、match URL 或密钥；
- smoke 只证明接入可用，不声明胜率提升；实力结论至少需要座位平衡、固定对手和预注册局数。

### Phase 5：可选 DeepSeek

前置：RuleBasedAI 的 Phase 4 完整通过，且另行取得 DeepSeek 与 Botzone 两个外部网络面的明确授权。

验收：

- 默认仍为 RuleBasedAI，DeepSeek 必须显式开启；
- Botzone 每回合时限、模型超时和 fallback 预算有硬上限；
- 模型失败仍只能回退到原始 legal actions；
- 不把 DeepSeek API key 与 Botzone URL/密钥写入同一日志或审计文件；
- 不作为 Botzone 基础接入验收条件。

## 8. 计划新增的测试

| 测试文件 | 主要场景 |
|---|---|
| `tests/test_botzone_cards.py` | 108 ID 全覆盖、A/2/K/王边界、花色、两副副本、非法 ID |
| `tests/test_botzone_protocol.py` | poll `m/n`、多局、finished/aborted、stage JSON、Header 注入、malformed fail-closed |
| `tests/test_botzone_profile.py` | 无贡 profile、deal/play 允许、tribute/return 明确 unsupported、未知 stage 拒绝 |
| `tests/test_botzone_session.py` | request 去重、手牌 ID inventory、history 累积、多局隔离、snapshot/restart、无状态中途恢复失败 |
| `tests/test_botzone_play_adapter.py` | 0/1-based 座位、公开 observation、table constraint、pass、自然牌、配子 carrier/claim |
| `tests/test_botzone_action_provenance.py` | 所有输出来自原始 legal action ID；非法/过期/其他会话 action ID 拒绝 |
| `tests/test_botzone_connector.py` | mock GET、阻塞/超时/断线、pending 重发、批量 Header、敏感信息脱敏 |
| `tests/test_botzone_rule_agent_e2e.py` | RuleBasedAI 的 deal→关键 play 回合、终局和无贡 profile 边界 |
| `tests/test_botzone_config.py` | 只读显式环境/参数、缺失配置失败、未导入 dotenv、日志不含配置值 |
| `tests/test_botzone_rule_compatibility.py` | 官方裁判/Log 脱敏 fixture 与当前 engine 的牌型、比较、配子、接风差异 |

测试 fixture 建议放在 `tests/fixtures/botzone/`，只保留官方文档样例和人工脱敏结构。不得提交真实 URL、密钥、match ID、完整真实手牌或对局 Log。

## 9. 风险与阻塞项

### P0 阻塞

1. **claim 编码仍不充分。** 当前 canonical `declared_cards` 的同点数组合通常没有声明花色，而 Botzone claim 使用牌 ID；必须确认 judge 对 claim 中花色/副本的要求。
2. **配子数量规则未封板。** 当前 engine 每手最多一个配子，官方 Wiki 没有明确同一手的数量上限。
3. **无贡手动桌阶段流与首个先手未封板。** 仅有的官方文字不足以证明“需要进贡=否”的新桌严格跳过 `tribute/return`，也没有该配置的首个 `play` fixture；不得从贡还规则或 UI 推断。
4. **目标账号权限未核验。** 官方公开门槛信息不能替代目标账号登录后的非敏感“本地 AI 可用”状态。
5. **无贡 runmatch initdata 未封板。** `X-Initdata` 的对应 JSON/文本形式不能靠截图猜测；该项只阻塞自动建桌，不单独阻塞手动路径。

### P1 风险

1. 本地 AI Wiki 固定版本较旧，接口声明可能变化；Phase 4 前必须重新核对当前页面。
2. 本地 AI 网关没有明确 exactly-once ack；pending response 需要按官方样例的“失败保留、成功后提交”事务处理。
3. `play.history` 只有近四手，进程重启恢复必须依赖本地 durable state。
4. 当前 RuleBasedAI 很弱，合法完成对局不等于实际对抗能力好。
5. Botzone 平台对手与发牌不可固定，少量结果不能与本地固定 seed 评测直接比较。
6. 当前项目与 Botzone 的牌型比较细节尚未经过 judge fixture 差分，名字相同不代表完全等价。
7. 人工建桌误选“需要进贡=是”会进入本项目明确不支持的阶段；必须在启动审计和 stage dispatcher 两处 fail-closed。

## 10. play 子集的前置状态

当前不得实现 `Botzone GuanDan no-tribute profile` 的 `deal + play` adapter。必须先取得第 0 节和第 9 节列出的官方裁判/fixture 与无贡阶段证据，并重新得到 `botzone_manual_no_tribute_phase0_verified`；届时才允许 Step L1-A1 的纯协议模型、108 ID codec 和离线 fixture。

理由：

- 108 ID、`deal`、`pass`、local-AI transport 与 `tribute/return` fail-closed 边界已有可复用的官方文字依据；
- 但 claim 语义、多配子裁判约束和无贡手动桌阶段流是 play 编码与调度的必要条件，缺一不可；
- 贡还属于当前 engine 明确 unsupported 的能力，即使未来无贡 profile 通过，也必须对 `tribute/return` fail-closed；
- 无贡 profile 只有取得该配置的官方证据后才是支持契约，不能由随机对局恰好未发生贡还来替代。

因此里程碑命名必须区分：

- `botzone_no_tribute_protocol_verified`：证明无贡协议、牌 ID 与 unsupported stage 边界；
- `botzone_no_tribute_adapter_verified`：证明 deal + play 接入 RuleBasedAI；
- `botzone_no_tribute_local_ai_smoke_verified`：证明真实平台无贡小规模对局完成。

任何上述状态都不得简写为“完整支持 Botzone GuanDan”。

## 11. 尚不确定的信息与官方查阅位置

| 不确定项 | 当前状态 | 必须查阅的位置 |
|---|---|---|
| claim 中替代牌的花色、副本 ID 和排序要求 | 不确定 | GuanDan 游戏详情的“裁判代码”及一份含配子的官方调试 Log |
| 单手可使用几张配子 | 不确定 | GuanDan 裁判源码，不能仅按 Wiki 单数措辞推断 |
| runmatch `X-Initdata` 中“需要进贡=否”的精确表示 | 不确定 | 官方 runmatch 文档、GuanDan 裁判 initdata schema 或登录后创建请求；不得从 UI 字段名猜 JSON |
| 本地 AI 当前账号等级门槛 | 不确定，官方页面文字冲突 | 目标账号登录后的“本地 AI 配置”区域 |
| 网关服务端长轮询具体超时秒数 | 未公布 | 当前本地 AI 设置页/接口响应 Header；Phase 4 smoke 记录 |
| 本地 AI 是否在重启后重放历史 | 官方未承诺 | 本地 AI 当前词条、实际断线 smoke；设计按“不重放”处理 |
| GuanDan 是否有官方可执行 Bot 样例 | 当前游戏详情只链接 Wiki，Wiki 只有交互样例 | 游戏详情、裁判源码入口；若平台另有下载需登录后确认 |

## 12. 推荐下一动作

执行 Step L0-A2：由用户从 GuanDan 游戏详情提供可下载的官方裁判源码、官方样例或含配子的官方调试 fixture，并在目标账号登录后的“本地 AI 配置”区域只确认可用性状态。Codex 只记录来源、文件大小、SHA-256、相关函数/行号和脱敏结论，不接收 URL/密钥/Cookie/账号身份。还需要“需要进贡=否”的官方 `deal → play` 阶段与先手证据。若用户尚未取得这些材料，应立即保持 blocked，不重复搜索同一 Wiki；取得并重新审计前不得进入 L1-A1。`X-Initdata` 仍只阻塞自动建桌，不单独阻塞手动路径。
