# 下一步实施提示词

## Step L5-A2b8：local-AI 直接 stage wire mode 适配

上一轮唯一 live 结论永久记录为：

```text
botzone_deepseek_runmatch_no_tribute_smoke_invalid
```

runmatch 已创建成功，但唯一 connector 在第二个 cycle 以 exit 5 / `diagnostic_failure` 结束。聚合结果为 requests/responses/headers=`1/0/0`、finished=`0`、transport failure=`1`；协议诊断为 `envelope_shape_invalid → envelope_required_fields_missing → required_both_missing_inner_stage_candidate`。请求未进入 session、adapter、RuleBased fallback 或 DeepSeek，state 与进程已清理，且没有重试。

该证据已足以确认 connector 收到了带 `stage` 的 GuanDan 内层请求，而 `poll._parse_request()` 当前无条件要求 Bot JSON 的 `requests/responses` 外层信封。停止继续扩展诊断画像；本步骤直接实现双 wire mode。

### 允许修改

- `integrations/botzone/poll.py`
- `integrations/botzone/connector.py`
- `integrations/botzone/bot_io.py` 或现有协议编码模块中确有必要的最小响应规范化辅助
- 与上述行为直接对应的 `tests/test_botzone_*.py`

禁止修改 `engine/`、`agents/`、DeepSeek client/prompt、RAG、CLI、transport、runner、runtime config、上传 Bot、真实配置和 docs。不得联网、读取 `.env` 或历史 live 请求正文。

### 实现契约

1. 为每个 `PollRequest` 增加固定 wire mode，例如 `bot_envelope` / `direct_stage`；必须是不可变、低基数状态，不保留原始字段画像。
2. JSON object 同时具备 `requests` 与 `responses` 时，继续严格走现有 `parse_bot_envelope()`，replay 与 `{"response":...}` 编码行为逐字段不变。
3. JSON object 不具备 Bot 信封字段、但具有 `stage` 时，严格调用现有 `parse_stage_request()`：
   - 合法 `deal/play/unsupported stage` 进入现有流程，`replay=None`；
   - malformed stage 固定归类 `inner_request_invalid`；
   - 不得把任意缺字段 object 当作 direct stage 接受。
4. direct `deal` 依靠现有 session 初始化本家实体手牌与座位；后续 direct `play` 依靠同 match 的 durable session。冷启动 direct `play` 必须继续 `play_without_state`，不得猜测手牌。
5. response 编码必须绑定 wire mode：
   - `bot_envelope`：保留 canonical `{"response":...}`；
   - `direct_stage`：Header value 为经过同等严格校验和 canonical JSON 序列化的 GuanDan 原始 response（deal `[]`；play `[action,claim]`），不得添加 `response` 外层。
6. 两种模式都必须拒绝换行注入、错误 deal response、malformed action/claim、非法实体 ID 和 provenance 缺失。
7. pending response 在写入 session 前已经是最终 wire bytes；transport failure、重启、重发和 ack 不得重复调用 Agent、重复扣牌或改变 wire mode。
8. 现有 envelope、Bot replay、required-fields 诊断、v4 audit、finished qualification 与 DeepSeek RuleBased fallback 契约保持兼容。

### 必须新增或更新的测试

- poll 同批解析 envelope 与 direct deal/play，顺序及 mode 稳定。
- live 观测形态的合法 direct `deal` 不再产生 `required_both_missing_inner_stage_candidate`。
- direct malformed stage 仍 fail-closed 为 `inner_request_invalid`，普通缺字段 object 仍是 envelope shape failure。
- direct `deal → Header [] → ack → play → Header [action,claim] → ack` 完整 mock 链。
- direct pass、自然牌和配子 response 的 canonical 原始 JSON；envelope 对照仍带 `response` 包装。
- direct 冷启动 play、重复请求、transport failure、重启 pending resend、多 match 隔离、unsupported tribute/return。
- Agent 只被调用一次，最终动作仍来自原始 legal action ID/provenance。
- 既有 envelope、session、adapter、DeepSeek runtime 和 runner 回归保持通过。

### 验证与交付

先运行新增定向测试，再运行：

```text
python -m unittest discover -q
git diff --check
```

通过后建立独立实现检查点；提交只包含允许的 integration/test 文件。报告测试数量、提交 hash、双模式行为和剩余风险。唯一成功判定：

```text
botzone_local_ai_direct_stage_wire_contract_verified
```

本步骤不运行 preflight、runmatch、connector 或 DeepSeek，不请求 live 授权。成功后下一步才是一次最小本地准入和新的单次 live 授权。
