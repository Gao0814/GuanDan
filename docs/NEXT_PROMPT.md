# 下一步实施提示词

## Step L0-A1：Botzone 手动建桌无贡 profile 官方协议收口

请在 GuanDan 项目中完成 Step L0-A1。本步只做 Botzone 官方资料、官方 GuanDan 裁判源码和目标账号非敏感权限元数据的调研与文档封板，只允许修改 `docs/*.md`。不得实现 connector/adapter、不得创建或加入对局、不得调用本地 AI URL、不得读取或输出真实 URL/密钥、不得修改 `.env`、engine、agents、CLI 或 tests。

### 前序分支封板

K-A3d3c3a 已完成独立只读恢复，唯一判定：

```text
no_observed_strategy_intent_action_quality_gain
```

恢复完整性通过，但 changed pair 为 7，小于预注册门槛 8，因此在第一项停止；on/off better=`2/1`、on/off team wins=`8/6` 不得用于越过第一门槛。K-A3d3c2 永久保持 `strategy_intent_live_quality_recovery_invalid`，K-A3d3b 永久保持 `strategy_intent_live_quality_benchmark_invalid`。strategy-intent prompt 继续默认关闭，不进入扩大验收、完整 DeepSeek 对局或胜率声明。

### 本步支持范围

只研究：

```text
Botzone GuanDan manual-table no-tribute profile
```

用户将在网页手动建桌，并明确选择“需要进贡=否”。当前项目不实现 tribute、return、resist、double tribute 或跨局升级。

`runmatch` 与 `X-Initdata` 的无贡表达属于后续可选自动化能力：如果官方资料仍不足，可继续标为 unknown，但不应阻塞手动建桌路径的 Phase 1–3。任何实现仍必须识别 `tribute/return` 并 fail-closed。

### 必读资料

先读取仓库：

- `AGENTS.md`
- `README.md`
- `docs/BOTZONE_INTEGRATION_PLAN.md`
- `docs/SPEC.md`
- `docs/CODING_BOUNDARY.md`
- `docs/INVARIANTS.md`
- `engine/cards.py`
- `engine/actions.py`
- `engine/rules.py`
- `agents/base.py`
- `agents/rule_based_ai.py`

然后只查 Botzone 官方来源：

- 官方“本地 AI”词条及固定版本；
- 官方“Bot”交互词条及固定版本；
- 官方 GuanDan 词条及固定版本；
- Botzone GuanDan 游戏详情页；
- 游戏详情提供的官方裁判源码、样例程序或官方调试输入输出；
- 登录后账号页面仅检查“本地 AI 是否可用/等级门槛”的非敏感状态。

不得用第三方博客、个人仓库、搜索摘要或截图猜测协议。每项结论都记录直接官方链接、页面版本/核对日期和证据类型；找不到则标记“不确定”。

### 必须封板的问题

#### 1. 牌 ID

- `0..107` 与两副牌的精确映射；
- 花色顺序、A/2..K、大小王位置；
- claim 是否要求保留原实体副本 ID，或只按牌面解释；
- claim 内 ID 的合法范围、重复、排序和 canonical 要求。

#### 2. 逢人配 action/claim

- 哪张牌是当前级牌下的配子；
- `action` 中真实 carrier ID 与 `claim` 中声明牌 ID 的精确关系；
- claim 的花色是否参与裁判、是否必须使用特定花色 ID；
- 两副同牌的副本 ID 是否可互换；
- 单手允许使用的配子最大数量；
- 多配子、炸弹、顺子、连对、钢板和同花顺的 claim 约束；
- 无配子时是否强制 `action == claim`；
- pass 是否精确为 `[[], []]`。

至少取得一份官方源码路径或官方样例，能够无歧义解释当前 `carrier_cards / declared_cards` 如何编码为 `[action, claim]`。若无法确认，本项必须 blocked，不能进入 play adapter 实现。

#### 3. 无贡手动桌阶段流

- `deal` request/response 的字段和空响应；
- 无贡配置下是否严格跳过 `tribute/return`；
- 首个 `play` 的先手来源和公开字段；
- `global.level`、`history`、`done`、`pass_on` 的精确含义；
- `history` 是仅近四手还是包含其他上下文；
- 单局结束信息与下一局/桌结束的边界。

不得从贡还规则反推无贡先手；必须有官方依据或标记 unknown。

#### 4. 本地 AI transport

- GET、返回行格式、`X-Match-<match_id>` Header 和多 match 行为；
- request/response 是否重放、何时视为提交成功；
- 超时、断线、异常结束和 finished row；
- 是否需要已有 Bot；手动建桌如何选择“本地 AI 替代我”；
- 当前目标账号是否达到本地 AI 权限门槛。

只记录字段名和权限结果，不记录真实 URL、密钥、match ID、Header 值或账号个人信息。

#### 5. runmatch 可选项

- 查明 `X-Initdata` 是否有官方无贡表达；
- 若仍不确定，明确标为“仅阻塞自动建桌，不阻塞手动建桌”；
- 不调用 runmatch，不创建测试桌。

### 差异与能力边界

更新 `docs/BOTZONE_INTEGRATION_PLAN.md` 的 confirmed/unsupported/unknown 表：

- adapter 可完成的协议/编码差异；
- 当前 engine 可表达的单局 play 子集；
- 必须由 session 持久化的近四手之外状态；
- 当前 engine 无法表达且明确 unsupported 的贡还/升级能力；
- claim 或裁判语义仍不一致时的阻塞级别。

不得修改 engine 来迎合未确认协议，也不得承诺“完整支持 Botzone GuanDan”。

### 验收判定

满足以下条件时，唯一判定：

```text
botzone_manual_no_tribute_phase0_verified
```

- local-AI transport 的 GET/Header/批量 match 语义有官方依据；
- 108 ID 映射封板；
- deal/play/pass 和 action/claim 可无歧义编码；
- 配子数量、claim 花色/副本/排序规则有官方裁判依据；
- 无贡手动桌阶段流与先手来源有官方依据；
- 当前账号可使用本地 AI，或权限前置已明确且可满足；
- 所有未知项只剩 runmatch 自动化等非手动路径阻塞；
- 未读取或持久化敏感信息。

任一手动 play 必需项仍未知时，唯一判定：

```text
botzone_manual_no_tribute_phase0_blocked
```

列出精确阻塞项和下一处官方资料位置，不得用实现假设填空。

### 后续边界

只有 Phase 0 verified 后，下一步才允许 Step L1-A1 实现纯协议模型、108 ID codec 和离线 fixture；仍不联网、不调用 Agent。

### 最终报告

必须包含：

- 唯一判定；
- 官方来源链接、固定版本和核对日期；
- confirmed/unsupported/unknown 表；
- action/claim、配子数量与无贡阶段流结论；
- 手动建桌权限和流程的非敏感结论；
- `X-Initdata` 是否仅作为可选阻塞；
- adapter 可处理项与规则能力缺口；
- 修改的 docs 文件；
- 明确说明未创建对局、未调用本地 AI URL、未读取密钥、未修改代码。
