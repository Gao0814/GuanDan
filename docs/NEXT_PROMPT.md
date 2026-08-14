# 下一步实施提示词

## Step L5-A2b2：Botzone 外层信封安全子分类

本任务只做离线诊断能力加固，不连接 Botzone，不调用 DeepSeek，不读取真实 URL、密钥、`.env`、历史 audit 原文或任何对局内容。

### 已确认基线

- L5-A1/L5-A1a 已封存，DeepSeek connector 离线组合与规则降级契约成立。
- L5-A2a1 零网络 preflight 已通过。
- L5-A2b1 已获得完整敏感出站授权，并按固定预算启动恰好一个前台 connector。
- 用户确认 Botzone 页面显示“已连接”后，connector 在用户确认新桌开始前自行退出。
- 唯一 live 结果：

```text
botzone_deepseek_connector_no_tribute_smoke_invalid
```

- 脱敏 audit：schema/version=`botzone_local_smoke_audit/2`，299 bytes，SHA-256 `94fd082013712b4d2c8c700735725a4bc1e772d195b756b1e491b15bd36c04e4`。
- 聚合：exit 5、`diagnostic_failure`、cycles=1、requests=1、responses=0、headers=0、finished=0、transport failures=0、diagnostic=`envelope_shape_invalid`。
- state 为空，无残留 connector。
- 请求在 Bot JSON 外层信封校验处失败，未进入 adapter、Agent、RuleBased fallback 或 DeepSeek 动作选择。
- 本次授权已消耗，不得重跑、补采或复用。

### 目标

在保持现有顶层公开诊断 `envelope_shape_invalid` 不变的同时，为外层信封失败增加固定、低基数、脱敏的内部子分类，使下一次审计能够区分失败发生在哪一项结构门槛，而不记录原始请求。

至少区分：

1. 顶层不是 JSON object 或 key 不是字符串；
2. 缺少 `requests` / `responses`；
3. 出现未知顶层字段；
4. 可选字段不是 JSON-compatible 值；
5. `requests` 不是 list；
6. `responses` 不是 list；
7. `requests` 为空；
8. `len(requests) != len(responses) + 1`。

子分类名称必须是固定枚举，不得包含字段值、长度、异常正文或任何请求片段。

### 实现边界

- 优先扩展 `BotEnvelopeError` 的固定 detail，而不是保存输入。
- `PollRequest` 可携带独立的安全 detail；现有 `diagnostic="envelope_shape_invalid"` 保持兼容。
- connector/runner 只聚合 detail 计数；不得保留逐 match、逐请求或顺序记录。
- audit schema 如需升级必须显式版本化，并保持旧字段语义不变。
- 合法 envelope、inner request、historical response、replay、digest、pending/ack、finished、RuleBased/DeepSeek adapter 行为不得变化。
- detail 不得进入 Header、session 文件、Agent observation、prompt、RAG 或模型请求。
- 不修改 `engine/`、`agents/`、CLI、RAG、evaluation、上传 ZIP 或 Botzone 规则能力。
- 不新增依赖。

### 测试要求

新增或更新测试，至少覆盖：

- 上述八种外层结构失败各映射到唯一固定 detail；
- 顶层公开诊断仍为 `envelope_shape_invalid`；
- 合法信封没有 detail；
- inner/history/replay 失败不被误分为 envelope-shape detail；
- connector cycle 和 audit 只输出聚合 detail 计数；
- detail mapping 不包含输入值、牌、match ID、异常正文或任意高基数字符串；
- 现有 Botzone envelope、poll、connector、runner、session、adapter 与 DeepSeek runtime 回归保持通过。

最低验证：

```text
python -m unittest tests.test_botzone_request_diagnostics tests.test_botzone_poll tests.test_botzone_connector tests.test_botzone_runner -q
python -m unittest discover -q
git diff --check
```

### 验收

通过时唯一判定：

```text
botzone_envelope_shape_subdiagnostics_verified
```

本步骤不请求 live 授权。完成后只更新实际改动、测试计数、audit schema 兼容性与下一步；不得宣称 Botzone 协议闭环、DeepSeek 可达、动作质量或胜率提升。
