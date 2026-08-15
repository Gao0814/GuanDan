# 下一步实施提示词

## Step L5-A2b17：四手窗口零重叠轮换契约

L5-A2b16 永久判定：

```text
botzone_manual_no_tribute_deepseek_mode_smoke_invalid
```

唯一 connector 在项目所有者确认人工新桌进入对局前自行 exit 5：cycles=4、requests/responses/headers=`4/3/3`、finished raw/qualified=`0/0`、唯一诊断 `history_alignment_failed=1`，非 timeout transport failure 与 timeout 均为 0。v5 audit 合法且脱敏；state 留有一份有效 active session，未读取原文、修改或清理。该运行不得归属于后续人工新桌，也不证明 DeepSeek 调用。

现有代码存在一个可独立离线证明、与该诊断一致的契约缺口：`session.merge_history()` 与 `bot_io._merge_history()` 只接受重复窗口或至少一项 suffix/prefix 重叠；但 Botzone 只在本家需要决策时交付 request，两次本家请求间可能恰好发生四个公开动作，使固定四手窗口完整轮换且与上一窗口零重叠。当前实现会把这种合法 full-window replacement 误判为 `history_alignment_failed`。

本步只实现并测试该离线契约。不得读取或修改 live state/audit，不得运行 preflight、connector、runmatch、Botzone 或 DeepSeek 网络请求，不得修改 `engine/`、`agents/`、CLI、RAG 或 evaluation。

### 允许修改

- `integrations/botzone/session.py`
- `integrations/botzone/bot_io.py`
- `tests/test_botzone_session.py`
- `tests/test_botzone_bot_io.py`
- 如端到端合成回归确有必要，只允许最小修改现有 Botzone connector/session E2E 测试；不得修改 runtime、transport 或 adapter 业务代码。

### 固定行为

1. 保持首次窗口、完全重复窗口和现有可验证 suffix/prefix overlap 行为不变。
2. 当且仅当以下条件全部成立时，允许零重叠追加：
   - incoming window 精确包含 4 个已严格解析的 `HistoryEntry`；
   - 与 latest window 不相等；
   - 所有 1..4 长度的 suffix/prefix overlap 均不存在；
   - accumulated 仍以 latest window 为严格后缀。
3. 合法零重叠时，将 incoming 的 4 个事件全部追加到 accumulated，并将 latest window 替换为 incoming；不得猜测或构造窗口之外的事件。
4. 零重叠 incoming 少于 4 项仍必须 `history_alignment_failed` / `replay_history_invalid`，不得放宽。
5. overlap 存在时仍采用最长 overlap；不得因新增 full-replacement 分支重复累计事件。
6. durable session 与 Bot envelope replay 必须保持等价语义，不能只修其中一条路径。
7. 不改变四槽前缀空位解析、牌 ID/claim、pending/ack、action provenance、finished tombstone 或诊断名称。

### 测试要求

- `latest=[a,b,c,d]`、`incoming=[e,f,g,h]` 的合法完整替换，累计历史增加 4。
- 初期不足四项 latest 后收到无重叠完整四项 incoming，仍可完整追加。
- 无重叠 incoming 为 0..3 项时 fail-closed。
- 有 1..4 项 overlap、完全重复窗口、滑动窗口行为保持原结果。
- pass、finished-player skip、自然牌与配子 response 的历史项不会被改写。
- Bot envelope replay 与 durable direct-stage 对同一窗口序列得到相同累计 history/latest window。
- 输入对象保持不变；非法窗口不产生部分 state 写入或 Agent 调用。
- 既有 pending/header/ack、重启恢复、adapter observation 与双 wire mode 回归通过。

### 验证

先运行新增/相关 Botzone 定向测试，再运行：

```text
python -m unittest discover -q
git diff --check
```

静态扫描确认没有新增网络客户端、配置读取、`.env`、真实 URL/key、live state/audit、DeepSeek 调用或 engine 私有状态依赖。

### 判定

全部行为、回归和边界通过后，唯一判定：

```text
botzone_four_event_history_rotation_contract_verified
```

完成后建立只含允许源码/测试的独立检查点。既有 active state 保持未读、未改、未清理；后续必须另设 state 处置与人工桌准入步骤。本结果不追认 L5-A2b16，也不证明 live、DeepSeek、动作质量或胜率。
