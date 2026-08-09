# 下一步实施提示词

## Step L0-A2：Botzone 官方裁判证据与账号权限补全

请在 GuanDan 项目中完成 Step L0-A2。本步只做用户辅助的官方证据获取、只读审计和文档封板，只允许修改 `docs/*.md`。不得实现 connector/adapter，不得创建或加入对局，不得调用本地 AI URL，不得读取或输出真实 URL、密钥、Header 值、match ID、账号身份或完整对局数据，不得修改 `.env`、engine、agents、CLI 或 tests。

### 当前前置结论

Phase 0 当前唯一判定：

```text
botzone_manual_no_tribute_phase0_blocked
```

已封板的官方资料为“本地 AI”`oldid=2230`、“Bot”`oldid=2245` 和“GuanDan”`oldid=2497`。这些页面已确认 local-AI GET/Header、108 ID、`deal`、`play`、`[action, claim]` 和 pass，但不能回答 claim 的实体 ID 约束、多配子裁判规则、无贡手动桌的完整请求序列与首个先手。不要反复搜索相同页面并把相同文字包装成新证据。

### 开始条件

至少取得以下一类新的官方证据后再开始审计；若调用方未提供且官方页面也没有可直接下载的入口，应立即保持 blocked，并列出需要用户提供的资料：

1. 从 Botzone GuanDan 游戏详情下载的官方裁判源码，或其官方直接下载链接；
2. 官方样例/调试 fixture，至少覆盖含配子的 `[action, claim]`，以及“需要进贡=否”的 `deal → play` 序列；
3. 用户登录后提供的脱敏可用性截图或文字确认，仅说明目标账号能否看到并使用“本地 AI”功能，不包含 URL、密钥、账号名或身份信息。

用户不得提供真实本地 AI URL、连接密钥、Cookie、Authorization/Header 值或完整私人对局记录。如附件包含此类内容，停止处理并要求先脱敏。

### 必读文件

- `AGENTS.md`
- `README.md`
- `docs/BOTZONE_INTEGRATION_PLAN.md`
- `docs/SPEC.md`
- `docs/CODING_BOUNDARY.md`
- `docs/INVARIANTS.md`
- 用户提供的官方裁判源码、官方 fixture 或脱敏账号可用性证据

### 证据审计

对每个新文件记录来源页面、获取日期、文件大小和 SHA-256；引用源码时记录文件、函数和行号。不得把第三方仓库、博客、搜索摘要、截图推测或本项目实现当作 Botzone 裁判真值。

必须逐项封板：

1. `claim` 中声明牌 ID 的合法范围、花色、副本、重复、排序和 canonical 要求；
2. 单手配子数量上限，以及多配子用于炸弹、顺子、连对、钢板和同花顺时的约束；
3. “需要进贡=否”是否严格跳过 `tribute/return`，从 `deal` 到首个 `play` 的请求序列；
4. 新桌首个 `play` 的先手来源及对应公开字段；
5. 目标账号是否具备本地 AI 功能入口和使用资格，只记录可用/不可用/未知；
6. `X-Initdata` 的无贡表示继续作为可选自动建桌项，不得阻塞已经有证据的手动建桌路径。

同时将官方语义与当前 engine 能力逐项对照，区分 adapter 可完成的编码差异和 engine 无法表达的规则缺口。贡、还贡、抗贡、双贡和跨局升级继续标记 unsupported；未来遇到 `tribute/return` 必须 fail-closed，不能返回 pass、空动作或任意牌。

### 验收判定

只有手动无贡 play 路径的 claim、多配子、阶段流、先手和账号权限全部有官方证据时，唯一判定：

```text
botzone_manual_no_tribute_phase0_verified
```

此时才允许下一步 L1-A1 实现纯协议模型、108 ID codec 和离线 fixture；仍不得联网。

任一必需项仍无官方证据时，唯一判定：

```text
botzone_manual_no_tribute_phase0_blocked
```

blocked 报告必须列出缺失证据、用户可从哪个官方页面下载或脱敏提供，以及哪些后续阶段因此不能启动。不得用实现假设填空，不得进入 L1-A1。

### 最终报告

必须包含：唯一判定、新增官方证据及其来源/hash、六项封板结果、confirmed/unsupported/unknown 差异表、账号可用性非敏感结论、修改的 docs 文件，以及未修改代码、未创建对局、未调用本地 AI URL、未读取密钥的声明。
