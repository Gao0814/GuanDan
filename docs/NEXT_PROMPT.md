# 下一步实施提示词

## Step L4-A3d1：Botzone finished target 同局来源加固

本轮只做离线实现与测试，不连接 Botzone，不读取真实 URL 或 `.env`，不创建测试桌，也不申请或使用 live 授权。

### 背景

- L4-A3c1 实现检查点：`1924db4a398db2641c4ba8e9dcf8a71a79a9388f`，工作区干净。
- 最近一次唯一 live 仍判定：

```text
botzone_no_tribute_local_ai_smoke_invalid
```

- 聚合为 exit 0、`finished_target`、`cycles=1`、`finished_seen=1`，但 request/response/header 全为 0。
- 当前 `MockConnector` 把 poll 中所有 finished rows 直接计入 `finished_seen`；`ForegroundRunner` 只按该总数停止，没有验证 finished 是否属于本进程参与并成功回传 play response 的 match。
- 这说明平台可能返回历史、未知或重复 finished 通知；当前结果不是 deal/play 闭环。

### 目标

把“网关观察到的 finished 行数”和“本次 connector 可作为 smoke 目标的合格完成数”分开。只有同一 match 的当前进程响应链完整时，runner 才能以 `finished_target` 和 exit 0 停止。

### 推荐修改范围

- `integrations/botzone/connector.py`
- `integrations/botzone/runner.py`
- 如传递待发送 response 的 stage provenance 确有必要，可最小修改 `integrations/botzone/session.py`
- 对应 Botzone connector/runner/live-preflight/session 测试；可新增 `tests/test_botzone_finished_provenance.py`
- 五份规划 Markdown 文档

禁止修改 poll/envelope/protocol、adapter、transport、runtime config、engine、agents、CLI、RAG 或 evaluation。不得为此新增依赖。

### 核心契约

1. 保留 `finished_seen` 作为网关原始 finished 行总数；新增独立、不可混淆的合格完成计数，例如 `finished_qualified`。
2. runner 的 `stop_after_finished` 只能比较合格完成计数，不能再比较原始 `finished_seen`。
3. 一条 finished 只有同时满足以下条件才合格：
   - `player_count == 4`，不是 aborted 或其他人数；
   - 同一 match 在当前 `MockConnector` 实例中已解析并处理合法 `PlayRequest`；
   - 该 play 已生成合法、非空的 pending Bot response；
   - 该 response 后续确实作为 `X-Match-*` Header 进入一次成功 transport poll，并完成既有 acknowledge；
   - finished row 在该成功 poll 中或之后到达，并由 session cleanup 成功处理；
   - 同一 match 最多合格一次。
4. 资格必须按 match 在内存中关联，不能用全局 `requests>0/responses>0/headers>0` 代替，避免不同 match 的计数拼接成假成功。
5. 不把 match ID 写入 summary、audit、异常、测试名称或诊断文本；内存关联可以使用 match ID，但不得新增明文持久化。
6. 未知、历史、重复、aborted、只有 deal、play response 尚未发送、transport 失败或 session cleanup 失败的 finished：
   - 可计入原始 `finished_seen`；
   - 不计入合格完成；
   - 不触发 exit 0；
   - 仍按既有安全规则清理当前确实存在的 session。
7. 若扩展 `PendingDelivery` 携带 stage，只允许固定 `deal/play` provenance，不得增加请求正文、牌、history 或 match 明文到 audit。
8. `RunnerSummary` 与 audit 明确同时输出 raw/qualified 两个聚合字段；audit schema/version 按兼容规则升级，并更新快照测试。
9. `exit_code_for()` 只有 `finished_target` 且合格计数达到目标时才允许返回 0；不可能构造 `finished_target + qualified=0` 的摘要。

### 必测场景

- 首个 poll 仅含未知 finished：raw=1、qualified=0，runner 继续，最终按 cycle/wall 未完成退出且非 0。
- 历史 tombstone 或重复 finished：不重复合格。
- aborted finished（`player_count=0`）：不合格。
- 其他非四人 finished：不合格。
- 同 match 只有 deal response 已发送：不合格。
- play response 已准备但 Header 尚未成功发送：不合格。
- 携带 play Header 的 transport 失败：恢复 pending，不合格。
- 同一 match 的合法 play response 在成功 poll 中发送/ack，随后四人 finished：raw=1、qualified=1，停止为 `finished_target`、exit 0。
- 一个 stale finished 与另一个合格 finished 同批到达：raw=2、qualified=1，只完成一个目标。
- 多 match 不能把 A 的 play response 与 B 的 finished 拼接为合格完成。
- session cleanup 失败时维持诊断失败优先级，不得成功停止。
- audit 只含聚合计数，不含 match、Header、请求、手牌或 history。
- 既有 pending/ack、重启恢复、finished tombstone、诊断优先级与合法 E2E 回归保持通过。

### 验证

运行新增定向测试、相关 Botzone 回归、全量测试和：

```text
git diff --check
```

执行边界扫描，确认没有真实网络、`.env`、URL、Cookie、DeepSeek、引擎私有状态或敏感字段进入实现/fixture/audit。

### 判定

全部通过：

```text
botzone_finished_target_provenance_verified
```

任一同局关联、ack 顺序、重复计数、audit 或回归门槛失败：

```text
botzone_finished_target_provenance_invalid
```

### 后续边界

- 本步不得执行 preflight 或 live，不得请求用户授权。
- 通过后仍需独立封存检查点和零网络准入，才能再次请求 live 授权。
- 所有历史 smoke invalid 保持不变；本步不形成对抗能力或胜率结论。

### 最终报告

报告修改文件、raw/qualified 契约、同 match provenance、测试数量、audit schema、边界扫描、工作区状态和唯一判定；明确声明未联网、未创建对局、未读取真实配置。
