# 下一步实施提示词

## Step L5-A2b13：long-poll v5 单局 DeepSeek live 授权

宿主机零网络准入已通过：

```text
preflight_ready
preflight_exit=0
state_empty=True
audit_empty=True
stderr=空（终端未显示）
```

当前判定：

```text
botzone_long_poll_deepseek_local_preflight_ready
```

该结果只证明本地配置、DeepSeek Agent 组合和 state 文件操作可构造；preflight 未启动 transport、connector 或网络。旧 live 授权均已消耗，不能自动延续。

### 项目所有者需一次性确认

```text
复用上一轮三个非本家 GuanDan Bot ID：是
me 座位仍为 0：是
所有旧本地 AI 测试桌均已关闭：是
接受省略 X-Initdata，并在非零 tribute 或 tribute/return 时立即停止且不重试：是
```

Bot ID 只从先前项目所有者消息读取并在内存中使用，不写入仓库、docs、audit 或普通日志。

### 必须同时给出的明确授权

项目所有者必须在同一回复中提供：

```text
我明确授权执行 L5-A2b13：向由当前 BOTZONE_LOCAL_AI_URL 在内存中派生的 runmatch endpoint 发送最多 1 次 GET，并向当前 local-AI endpoint 发送最多 100 次 GET；允许将本家未公开手牌、公开局面、engine 合法候选、手牌评估、记牌摘要、场景标签和本地 RAG 片段发送到 https://api.deepseek.com 的 deepseek-v4-flash。DeepSeek timeout 为 60 秒、retries 为 0；只启动一个 connector，只创建一个 runmatch 对局，最长 3600 秒，qualified finished=1 即停。省略 X-Initdata；若首个请求显示非零 tribute，或出现 tribute/return，立即停止且不重试。v5 audit 只保存聚合 timeout、固定 transport failure category 和 finished provenance，不保存任何敏感内容。
```

### 授权后的固定执行顺序

1. 快速确认工作区干净、无残留 connector，固定 state/audit 目录仍存在且为空；不重复 80/587 测试或 preflight。
2. 使用项目 `.venv` 和 `PYTHON_DOTENV_DISABLED=1` 启动唯一 DeepSeek connector；state 使用既有空目录，audit 写入独立 audit 目录下的新文件。
3. connector 建立 local-AI 长轮询后，仅发送一次 runmatch GET：`X-Game=GuanDan`、座位 0 为 `me`、其余三席使用先前 Bot ID；不发送 `X-Initdata`。
4. direct-stage 与 envelope 均按已封存 wire mode 处理；response 必须来自 engine 原始合法 action ID/provenance。
5. 长轮询 timeout 只计 idle，不触发退避或 failure limit；其他 transport category 保持失败预算。
6. DeepSeek 异常、timeout、空值或非法 action ID 仅允许现有 RuleBased fallback，不得伪造动作。
7. qualified finished=1、达到预算或出现固定失败后停止；不创建第二局、不启动第二进程、不补采。
8. 确认 connector 退出、state 只剩允许的最小 tombstone 或完成清理、audit v5 合规且无敏感形态。

### 验收结论

只有 runmatch 成功、非零 request/response/Header、qualified finished=1、finished 分类守恒、非 timeout transport failure=0、协议 diagnostics/detail/profile 为空、无非法动作/决策超时、state/audit 合规且无残留进程，才能判定：

```text
botzone_deepseek_runmatch_no_tribute_smoke_verified
```

其他结果只能是对应 `invalid` / `precondition_failed`，且不得重试。该结论不证明 DeepSeek 每手参与、动作质量或胜率提升。
