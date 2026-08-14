# 下一步实施提示词

## Step L5-A2b5：缺失必需字段的安全形状画像

本任务只做离线诊断加固，不连接 Botzone，不调用 DeepSeek，不读取或保存历史原始请求、URL、密钥、match ID、牌或异常正文。

### 已确认基线

- L5-A2b2 检查点：`37bdd0d`；父诊断、八种 detail 和 audit v3 已封存。
- L5-A2b3b 零网络准入通过。
- 项目所有者确认全部旧测试桌已结束/关闭，并明确授权 L5-A2b4。
- L5-A2b4 启动恰好一个 connector，Botzone 页面显示“已连接”。
- connector 在项目所有者确认新桌开始前自行退出，没有重跑或补采。
- audit：`botzone_local_smoke_audit` v3，361 bytes，SHA-256 `8dbfd4e700b41c0d9c5a0ecca3b08a40a460f13a022f904e5ea0cf995906fbc1`。
- 聚合：exit 5、`diagnostic_failure`、cycles=1、requests=1、responses=0、headers=0、finished=0、transport failures=0。
- 父诊断：`envelope_shape_invalid=1`。
- 固定 detail：`envelope_required_fields_missing=1`。
- state 为空，无残留 connector；请求未进入 session、adapter、Agent、RuleBased fallback 或 DeepSeek。

唯一判定：

```text
botzone_deepseek_connector_no_tribute_smoke_invalid
```

L5-A2b4 授权已消耗，不得重跑、补采或复用。

### 目标

在保持现有父诊断和八种 detail 完全兼容的前提下，仅为 `envelope_required_fields_missing` 增加一个固定、低基数、安全 profile，使后续 audit 能回答：

1. 只缺 `requests`；
2. 只缺 `responses`；
3. 两者都缺，且顶层为空 object；
4. 两者都缺，但形状像单条 GuanDan inner stage；
5. 两者都缺，且只包含已允许的 optional Bot 字段；
6. 两者都缺，属于其他 object。

profile 只能是固定枚举，不得包含 key 名列表、字段值、字段数量、长度、hash、match、牌、请求片段或异常正文。

### 推荐固定 profile

```text
required_requests_missing
required_responses_missing
required_both_missing_empty_object
required_both_missing_inner_stage_candidate
required_both_missing_optional_only
required_both_missing_other_object
```

`inner_stage_candidate` 只允许依据固定布尔形状判断，例如存在字符串 `stage` 且没有 `requests/responses`；不得解析、复制或记录 stage 值和其他字段。

### 实现边界

- `BotEnvelopeError.code/detail` 保持现有语义；新增独立 profile 字段或等价不可变契约。
- `PollRequest` 只携带 allowlist profile；非 required-fields detail 的 profile 必须为 `None`。
- connector/runner 仅聚合 allowlist profile，audit 如升级到 v4 必须保留 v3 所有字段和语义。
- 合法 envelope、inner request、history/replay、pending/ack、finished provenance、RuleBased/DeepSeek adapter 行为不得变化。
- profile 不得进入 Header、session、Agent observation、prompt、RAG 或模型调用。
- 不修改 `engine/`、`agents/`、CLI、RAG、evaluation、上传 ZIP 或规则能力。
- 不新增依赖，不联网，不请求 live 授权。

### 测试要求

至少覆盖：

- 六种 profile 各自唯一映射；
- 父诊断仍为 `envelope_shape_invalid`，detail 仍为 `envelope_required_fields_missing`；
- 其他七种 detail、inner/history/replay 和合法 envelope 不产生 profile；
- 未识别 profile 在 connector 与 runner 两层均被 allowlist 丢弃；
- audit 只含聚合计数，不含输入 key/value、长度、hash、match、牌或异常正文；
- v3 旧字段兼容，现有 Botzone/DeepSeek runtime 回归通过。

最低验证：

```text
python -m unittest tests.test_botzone_request_diagnostics tests.test_botzone_poll tests.test_botzone_connector tests.test_botzone_runner tests.test_botzone_live_preflight -q
python -m unittest discover -q
git diff --check
```

### 验收

通过时唯一判定：

```text
botzone_required_fields_shape_profile_verified
```

完成后只报告实现文件、固定 profile、audit 版本兼容性、测试计数和边界扫描。本步骤不形成 Botzone 协议闭环、DeepSeek 可达、动作质量或胜率结论。
