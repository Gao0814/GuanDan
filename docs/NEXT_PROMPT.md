# 下一步实施提示词

## Step U0-A3：Botzone 上传 Bot 架构分流决策

本任务只做架构决策与规划更新，不修改代码、不重新上传探测包、不再次探测网络，也不读取用户存储或 API key。

### 已确认结果

- U0-A1 实现检查点：`085162972363e634fe224c9f1725063b3cd13686`。
- U0-A2 用户已完成一次新无贡对局。
- 探测 Bot 固定状态：

```text
probe_dns_or_connect_failed
```

- Botzone verdict 为 OK，没有决策超时。
- 探测 Bot 的规则动作被裁判接受，对局完整结束。
- 首个探测输出的平台运行时间约 61 ms，属于快速连接失败，不是 3 秒模型响应超时。
- 状态不是 `credential_unavailable`，按探测包契约说明 `data/deepseek_credentials.json` 已通过路径、读取和 JSON 格式门槛。
- 没有获得任何 HTTP 状态或模型响应，不能声称 DeepSeek API 已被访问。

唯一判定：

```text
botzone_deepseek_egress_admission_blocked
```

### 结论边界

1. 当前证据只能确认 DNS/连接阶段失败，不能进一步断言是 Botzone 全局禁网、域名限制、出口策略还是其他平台网络原因。
2. 不能用长时运行解决该问题。长时运行减少进程冷启动，不会建立原本失败的外部连接，也不会放宽单回合 API 网络能力。
3. 用户存储可以提供文件，但不能在沙箱无法连接 DeepSeek 时充当实时模型服务。
4. 不允许通过硬编码 key、代理 URL、IP 地址、关闭 TLS 校验或增加重试绕过阻塞。
5. 按 U0 预注册门槛，当前“上传 Bot 直接实时调用 DeepSeek”支线不得进入 U1/U2/U3 实施。

### 需要项目所有者选择的架构

#### 方案 A：上传版完整本地 AI（推荐）

保留“无需 connector”的部署目标，但移除实时 DeepSeek 要求：

- U1：迁移完整无贡合法动作，包括逢人配；
- U2：迁移统一阶段、开局、记牌、策略路由、剪枝和确定性 RuleBased fallback；
- U4 子集：可启用长时运行和本地 RAG/经验库，语料从用户存储读取；
- 不进行任何外部网络调用。

新支线名称建议：

```text
无需 connector 的 Botzone 完整本地 AI
```

优点：符合 Botzone 上传执行环境、可复现、不会被 API 延迟或网络阻塞影响。缺点：不包含实时 DeepSeek。

#### 方案 B：恢复本地 connector + DeepSeek

- Botzone 使用“本地 AI”入口；
- 本机 connector 负责 Botzone GET/Header；
- 本机可以调用 DeepSeek，并继续使用 Python 3.11 的完整 agents/RAG；
- 需要重新处理 connector live 稳定性和本机持续在线问题。

优点：能保留实时 DeepSeek 和当前完整 AI 主链。缺点：需要 connector，违背当前“无需 connector”部署目标。

#### 方案 C：暂停 Botzone 完整体

- 保留当前已能完成对局的 `guandan_rule_ai_py36.zip`；
- 不继续迁移完整规则或策略；
- 主项目继续做本地 AI 质量优化。

### 本任务输出要求

1. 用户只需明确选择 A、B 或 C。
2. 未获得选择前，不修改代码或创建下一阶段实现提示词。
3. 选择 A：下一提示词改为 U1-A1“Python 3.6 完整合法动作 parity 基线”。
4. 选择 B：新开 connector 恢复任务，不复用本次上传 Bot 网络探测授权。
5. 选择 C：将 Botzone 支线标记暂停，不安排实现任务。

### 安全边界

- 不要求用户提供 key、凭据文件或 Botzone 对局全文。
- 已上传的真实 key 建议由用户根据个人安全策略保留、撤销或轮换；Codex 不读取也不操作。
- 本任务不联网、不重试探测、不修改稳定规则 Bot，不形成动作质量或胜率结论。
