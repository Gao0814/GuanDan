# 下一步实施提示词

## Step L5-A3d：observed live 成功局 finished tombstone 清理

L5-A3c 已完成，唯一判定：

```text
botzone_deepseek_observed_live_smoke_verified
```

唯一人工无贡桌完成协议闭环，v6 audit 为 619 bytes，SHA-256：

```text
f29029e9b6dfe0dc8cfcf96b85e7b3a917270eaf4c6f357846d78060c8e60ac9
```

聚合观测显示 11 次 Agent 决策中 `local_shortcut=1`、`model=10`；10 次模型尝试均为 `success`，RuleBased fallback 为 0。该结果证明本次小样本中有 10 次合法模型动作进入最终 Botzone 响应，但不证明动作优于 RuleBased、因果收益或胜率提升。

当前 state 目录只保留一份严格最小 finished tombstone。本步骤只处理该 tombstone，不修改代码，不运行测试、preflight、connector、runmatch 或任何网络请求。

### 项目所有者确认

执行前必须由项目所有者明确回复：

```text
我确认 L5-A3c 对局已经结束且无需恢复，并授权 L5-A3d 在严格验证后删除唯一 finished tombstone。
```

没有该确认时只报告：

```text
precondition_failed: observed_live_tombstone_cleanup_not_authorized
```

不得读取或删除 state 文件。

### 固定执行范围

1. 确认 HEAD 包含 `0c51c5ff85f4edbe980dc1b5e63397da6f5747cc` 与当前文档检查点，工作区干净且没有残留 `integrations.botzone` connector 进程。
2. 只读复核 L5-A3c v6 audit 的 619 bytes、锁定 SHA-256、schema/version、固定字段集合、协议/模型守恒和敏感形态扫描；不得输出 audit 路径、URL、密钥、Header、match、玩家、牌、history、prompt、response、reasoning、action ID 或异常正文。
3. 只允许 state 目录中恰好存在一个普通文件。严格验证它属于 state 根目录、文件名格式合法，并且是当前 session schema 允许的最小 finished tombstone；不得保留 match key、座位、手牌、history、request/response、digest、pending、effect、handler 或缓存字段。
4. 文件归属、类型、schema、字段或 v6 audit 任一不匹配时 fail-closed，不删除任何内容，判定：

```text
botzone_observed_live_tombstone_cleanup_invalid
```

5. 仅删除这一个已验证 tombstone。不得递归清理、删除 state 目录、覆盖或修改任何既有 audit，也不得处理未登记文件。
6. 删除后验证 state 文件数 `1 → 0`、目录仍存在且为空；L5-A3c v6 audit 与此前 v5/cleanup audit 的 bytes/SHA-256 均不变；无残留 connector。
7. 新建一份仓库外脱敏 cleanup audit，仅记录固定 schema/version、删除前后文件计数、严格验证布尔值、既有 audit 不变布尔值、network/connector/test/code-change 零计数和规范化判定；不得记录路径、文件名、match 或牌局内容。

### 验收判定

全部门槛通过时唯一判定：

```text
botzone_observed_live_tombstone_cleanup_verified
```

本步骤不运行测试、不修改仓库、不联网，也不形成新的协议、DeepSeek、动作质量或胜率结论。

### 后续边界

L5-A3d 完成后进入 L5-A4a：先离线设计 RuleBased 与 DeepSeek 的可比较对抗评估协议，包括固定桌设置、座位轮换、样本量、完成率、模型成功/fallback、团队胜负与名次指标，以及不依赖单局结果的判定门槛。L5-A4a 只做设计和离线载体，不直接启动新的 Botzone live。
