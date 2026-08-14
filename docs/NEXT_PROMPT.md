# 下一步实施提示词

## Step L5-A2b3c：历史测试桌清理确认

本任务只完成项目所有者人工桌面门槛，并在确认后准备 L5-A2b4 的授权问题。不得检查环境、运行测试/preflight、创建 state/audit、启动 connector、poll Botzone 或调用 DeepSeek。

### 已确认基线

- L5-A2b2 检查点：`37bdd0d`；八种 envelope shape detail 与 audit v3 已封存。
- L5-A2b3/L5-A2b3a 的预算前置失败均未启动 connector，历史 live 授权未消耗。
- 当前新进程的 URL/key/endpoint/model/timeout/retries 六项门槛全部通过。
- 检查点、工作区、24 项定向测试、diff check 和残留进程门槛通过。
- 唯一零网络 preflight：约 171 ms、exit 0、stdout=`preflight_ready`、stderr 空、state 空并删除、无残留。
- 子进程显式 60/0 的 `AppConfig.from_env()` 固定探测返回 `deepseek_budget_ready`。
- 实际顺序为：严格环境数值门槛 → 唯一 preflight → 补充 AppConfig 固定探测；未重跑 preflight。preflight 自身同样经过现有 AppConfig/Agent 本地组合路径。
- Botzone GET、DeepSeek request、DNS/socket/HTTP、connector cycle、`suggest_action_id()` 均为 0。

规范化判定：

```text
botzone_deepseek_connector_v3_preflight_ready
```

该判定只覆盖零网络本地准入，不追认任何历史 live。

### 当前人工门槛

请项目所有者明确回复：

```text
我已结束或关闭所有历史 Botzone 本地 AI 测试桌；下一次只会在 connector 显示已连接后创建一个全新的“需要进贡=否”测试桌，不会同时保留或创建第二个活动桌。
```

收到确认前不得进行任何工具调用或请求 live 授权。

### 确认后的唯一动作

收到上述确认后，只向项目所有者提出以下授权问题，不在同一步执行 L5-A2b4：

```text
已确认全部历史本地 AI 测试桌均已结束或关闭。是否明确授权执行 L5-A2b4：启动一个 Botzone DeepSeek connector，并仅在连接后创建一个全新无贡测试桌；允许将本家未公开手牌、公开历史/状态、合法候选、手牌评估与记牌摘要、场景标签和本地 RAG 片段发送到 https://api.deepseek.com 的 deepseek-v4-flash？固定预算为当前 BOTZONE_LOCAL_AI_URL 最多 100 次 GET、Botzone poll timeout 120 秒、DeepSeek timeout 60 秒、零重试、一个 connector、最长 3600 秒、完成一局即停；全新临时 state/audit，不重跑、不补采、不启动第二进程。若外层信封失败，audit 只记录固定父诊断和八种安全 detail 之一。
```

只有项目所有者在后续新回复中明确授权后，才能另行执行 L5-A2b4。

### 结论边界

当前结果不证明 Botzone 信封已兼容、DeepSeek 可达、模型返回有效动作、动作质量或胜率提升。
