# 下一步实施提示词

## Step L5-A2b14：失败 live 的只读本地证据审计

L5-A2b13 已永久判定：

```text
botzone_deepseek_runmatch_no_tribute_smoke_invalid
```

已知事实仅限：唯一 connector 启动、唯一 runmatch GET 已发送、Botzone 页面未显示对局、connector 随后被终止、没有可用完成 audit、state 目录非空且尚未读取或清理、工作区干净。不得从这些事实推断 runmatch 是否创建成功、local-AI 是否收到请求、DeepSeek 是否被调用，或 state 属于哪个阶段。

本步只做零网络、只读、脱敏的本地证据审计。不得修改代码，不得重跑 preflight/live，不得启动 connector，不得发送 runmatch/local-AI/DeepSeek 请求，不得读取 `.env` 或连接配置值。

### 前置

1. 确认当前 HEAD 包含文档检查点 `51a63d0a1b16d54d099861fb7953215d69a4a264`，实现检查点 `220c648a4629453621f534beaeb95e52d85656ce` 为祖先，工作区干净。
2. 确认没有命令行匹配 `integrations.botzone` 的残留进程；不得因无关 Python 进程阻塞，只报告布尔结果，不输出完整命令行、环境或路径。
3. 将 L5-A2b13 的 invalid 结论和已消耗授权视为不可改写；本步没有任何联网授权。

### 只读审计

1. 仅检查本次固定 state 与 audit 目录，不扫描其他用户目录。
2. 先记录 state/audit 的文件数量、总字节数和目录级 SHA-256；不得输出或保存文件名、match ID、request digest、Header、手牌、history、response、Bot ID、URL、key 或原始 JSON。
3. audit 若为空或缺少 v5 完成文件，只记录固定类别 `completion_audit_missing`；不得补写、伪造或根据终端描述重建 audit。
4. state 若非空，只允许用现有 session schema 做本机内存解析，并输出以下聚合字段：
   - `state_file_count`
   - `session_parse_valid_count` / `session_parse_invalid_count`
   - `stage_counts`（仅 `deal` / `play` / `unknown`）
   - `delivery_state_counts`（仅 `idle` / `pending` / `inflight` / `finished` / `unknown`）
   - `handler_completed_count`
   - `pending_response_present_count`
   - `pending_effect_present_count`
   - `cached_response_present_count`
   - `finished_present_count`
   - `own_hand_count_min/max`
   - `history_count_min/max`
5. 解析器必须 fail-closed：未知 schema、字段或非法值只增加 `session_parse_invalid`，不得输出异常正文或部分敏感内容。
6. 审计前后重新计算目录文件数、总字节数和目录级 SHA-256，必须完全一致；不得删除、重命名、修复或 tombstone 化 state。
7. 脱敏结果只能写入仓库外 audit 目录中的一个全新 JSON；如果无法安全创建该文件，则只返回 `precondition_failed`，不得改用仓库或 state 目录。
8. 对新 JSON 做敏感形态扫描；报告仅给固定聚合计数、前后不变性和文件自身 bytes/SHA-256，不回显任何受保护值或路径。

### 判定

- 完成 audit 缺失且 state 合法可解析、前后完全不变：`botzone_live_residual_state_audit_verified`。
- state 不可安全解析、前后发生变化或审计证据不完整：`botzone_live_residual_state_audit_invalid`。
- 目录、进程、工作区或新 audit 文件前置不满足：对应 `precondition_failed`。

无论结果如何，本步都不得形成 runmatch 成功、协议闭环、DeepSeek 调用、动作质量或胜率结论。完成后只更新 `docs/`；是否清理 state、修复 launcher/audit 生命周期或重新 live 必须另开步骤。
