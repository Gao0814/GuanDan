# 下一步实施提示词

## Step L4-A3c1：Botzone `malformed_request` 分层脱敏诊断契约

本轮只做离线代码加固和测试，不连接 Botzone，不读取真实 `BOTZONE_LOCAL_AI_URL` 或 `.env`，不创建测试桌，也不复用 L4-A3c 的授权。

### 背景

- L4-A3a 检查点：`2ac51fb2c80a5a0ae4b7dabd4f2aa161e11f1498`。
- L4-A3b1 检查点：`28de0cb36f7356bc35ade874fa8f75fa63b1f331`。
- L4-A3c 唯一真实 smoke 已结束，判定永久保持：

```text
botzone_no_tribute_local_ai_smoke_invalid
```

- 聚合结果：`cycles=1`、`requests_seen=1`、`responses_prepared=0`、`headers_sent=0`、`finished_seen=0`、`transport_failures=0`，唯一诊断为 `malformed_request=1`，exit 5。
- 请求在用户确认新建无贡测试桌之前已到达，因此不能证明它来自全新测试桌，也不能排除旧 match 重放。
- 当前 `poll._parse_request()` 把 JSON 解码和全部 Bot envelope 解析错误统一压缩为 `malformed_request`，证据不足以区分外层信封、内层 GuanDan 请求、历史 response 或重放状态。

### 目标

建立稳定、固定白名单、无敏感内容的请求失败分类，使下一次 live smoke 只凭聚合 audit 就能定位协议层级，同时保持合法请求、response wrapper、pending/ack 和 Agent 边界不变。

### 允许修改

- `integrations/botzone/bot_io.py`
- `integrations/botzone/poll.py`
- 与上述契约直接相关的 Botzone 测试；可新增 `tests/test_botzone_request_diagnostics.py`
- 五份规划 Markdown 文档

除非测试证明职责确实位于 connector 聚合边界，否则不要修改 `connector.py`。禁止修改 `engine/`、`agents/`、`cli/`、`rag/`、`evaluation/`、配置、transport、runner、session 和 adapter。

### 实施要求

1. 为 envelope 解析错误提供固定机器码；不得把 `str(exc)`、`repr(exc)`、原始 JSON、字段值、索引、牌 ID、match ID 或完整手牌写入诊断。
2. `poll` 至少区分下列稳定类别：
   - `request_json_invalid`
   - `envelope_shape_invalid`
   - `inner_request_invalid`
   - `historical_response_invalid`
   - `replay_history_invalid`
   - 未知异常保守回退 `malformed_request`
3. 可以在 `bot_io.py` 内保留更细的固定子码，但对外必须经过集中 allowlist 映射；禁止动态拼接错误码。
4. `ProtocolValidationError` 只能映射到有限固定类别。不得将其当前英文错误正文直接暴露到 poll、connector audit 或 runner 摘要。
5. 合法 envelope 的 `stage`、`replay`、digest、response wrapper 与后续 connector 行为逐字段不变。
6. 任何非法输入仍 fail-closed：不调用 Agent、不准备 response、不发送 Header、不伪造 pass。
7. audit 继续只保存聚合计数；本步不增加请求结构快照、长度指纹、hash 或样本级记录。
8. 不复制此前真实请求或 27 张真实手牌到 fixture。使用完全人工合成的最小结构测试各错误类别。

### 必测场景

- 非法 JSON 文本映射为 `request_json_invalid`。
- 顶层非对象、字段缺失/多余、requests/responses 类型或基数错误映射为 `envelope_shape_invalid`。
- 当前 deal/play 的 global、history、done、pass_on、无贡字段或牌 ID 错误映射为 `inner_request_invalid`。
- 历史 deal/play response 的 wrapper、action/claim、手牌扣减错误映射为 `historical_response_invalid`。
- 首条非 deal、重复 deal、level 漂移、历史阶段或累计重放无法对齐映射为 `replay_history_invalid`。
- 人工构造未知异常只落入 `malformed_request`，且不泄露异常正文。
- connector 聚合 exact safe code，并以既有 `diagnostic_failure` 停止；response/header/Agent 调用均为 0。
- 合法 deal、首个 play、历史 replay、pass、自然牌和配子 response 的既有快照与行为保持不变。
- 输出与 audit 扫描不含原始 payload、match ID、牌 ID 列表、手牌、history、URL、Header、Cookie、密钥、异常正文。

### 验证

先运行新增/修改的定向测试，再运行：

```text
python -m unittest discover -q
git diff --check
```

同时执行边界扫描，确认未增加真实网络、`.env`、DeepSeek、私有 engine state 或敏感数据读取。

### 判定

全部契约与回归通过：

```text
botzone_malformed_request_safe_diagnostics_verified
```

任一分类不稳定、存在原文泄露、合法路径变化、测试失败或修改越界：

```text
botzone_malformed_request_safe_diagnostics_invalid
```

### 后续边界

- 本步通过不等于 live connector 可用，不得在同一任务重跑 Botzone。
- 下一次真实 smoke 必须另行准入、使用全新 state/audit、取得新授权，并要求用户在 connector 明确进入连接状态后再创建全新“需要进贡=否”测试桌。
- L4-A3c 及全部历史 invalid/inconclusive 结论永久保留。

### 最终报告

报告修改文件、固定诊断表、合法路径兼容性、测试数量、边界扫描、工作区状态和唯一判定；明确声明未联网、未读取真实配置、未创建对局，也未形成胜率结论。
