# 下一步实施提示词

## Step L5-A2b22：成功 smoke 的 finished tombstone 清理

L5-A2b21 已完成，唯一判定：

```text
botzone_manual_no_tribute_deepseek_mode_smoke_verified
```

唯一人工无贡桌已完成协议闭环：connector `exit=0`、`stop_reason=finished_target`，23 个 request 均生成 response 并发送 Header，qualified finished 精确为 1，transport failure、timeout 与全部协议 diagnostics 均为 0。v5 audit 为 449 bytes，SHA-256：

```text
6eed257558d1ddd58239b8a5d094d3ebe209895abb5c74cd323824dd44c305d4
```

当前 state 目录只保留一份最小 finished tombstone。本步骤只处理该 tombstone，不修改代码，不运行测试、preflight、connector、runmatch 或任何网络请求。

### 项目所有者确认

执行前必须由项目所有者明确回复：

```text
我确认 L5-A2b21 对局已经结束且无需恢复，并授权 L5-A2b22 在严格验证后删除唯一 finished tombstone。
```

没有该确认时只报告 `precondition_failed: finished_tombstone_cleanup_not_authorized`，不得读取或删除 state 文件。

### 固定执行范围

1. 确认 HEAD 包含当前文档检查点与 `5bb44fd4052e181d08455594ab0879c0ee305dfb`，工作区干净且没有残留 `integrations.botzone` connector 进程。
2. 只读复核 L5-A2b21 v5 audit 的 bytes、SHA-256、schema/version、固定字段集合与敏感形态扫描；不得输出 audit 路径、URL、密钥、Header、match、牌、history、prompt 或模型正文。
3. 只允许 state 目录中恰好存在一个文件。严格验证它是当前 session schema 允许的最小 finished tombstone，并且只含 schema、version 与 `finished=true`；不得保留 match key、座位、手牌、history、request/response、digest、pending、effect、handler 或缓存字段。
4. 文件名、路径归属、普通文件属性、schema 和字段集合任一不匹配时 fail-closed，不删除任何内容，判定 `botzone_finished_tombstone_cleanup_invalid`。
5. 仅删除这一个已验证 tombstone。不得递归清理、删除 state 目录、修改既有 audit，或处理任何未登记文件。
6. 删除后验证 state 文件数从 1 变为 0、目录仍存在且为空；既有 v5 audit bytes/SHA-256 不变，无残留 connector。
7. 新建一份仓库外脱敏 cleanup audit，只记录固定 schema/version、删除前后文件计数、严格验证布尔值、网络/connector/test/code-change 零计数和规范化判定；不得记录路径、文件名、match、牌局内容或异常正文。

### 验收判定

全部门槛通过时唯一判定：

```text
botzone_successful_smoke_tombstone_cleanup_verified
```

本步骤不运行测试、不修改仓库、不联网，也不形成新的协议、DeepSeek 调用、动作质量或胜率结论。

### 后续边界

L5-A2b21 只证明以 `deepseek` 模式运行的人工无贡桌完成 Botzone 协议闭环。现有 v5 audit 没有模型调用、成功、fallback 或本地快捷路径计数，因此不得宣称 DeepSeek 实际参与了任何一手。

L5-A2b22 完成后，下一任务应进入 L5-A3a：设计低基数、脱敏、可守恒的 DeepSeek runtime 聚合可观测性。该任务必须先离线实现和测试，只允许统计调用尝试、成功、timeout、异常、非法 suggestion、RuleBased fallback、本地 shortcut 与最终合法动作来源；不得保存 prompt、response、reasoning、手牌、match、action ID 或异常正文，也不得直接恢复 live。
