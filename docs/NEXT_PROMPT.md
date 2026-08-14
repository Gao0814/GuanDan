# 下一步实施提示词

## Step L5-A2b1：补充对局数据出站授权后恢复单局 smoke

本任务包含把本地对局决策上下文发送到外部 DeepSeek endpoint。未获得项目所有者对“具体数据类别 + endpoint + 模型 + 固定预算”的明确授权前，不得启动 connector 或发送任何网络请求。

### L5-A2b 首次启动结果

- 项目所有者已授权 Botzone/DeepSeek endpoint、模型和运行预算。
- 启动前检查点、工作区、定向 23 项、配置元数据和残留进程门槛均通过。
- 全新临时 state/audit 资格通过。
- 外部执行安全审查在进程创建前拒绝启动：现有授权没有明确覆盖将本家手牌与对局上下文发送给 DeepSeek。
- connector 未启动；Botzone GET、DeepSeek request 和全部网络请求均为 0。
- 临时 state 保持为空并已删除；audit 未创建；无残留进程。

规范化结果：

```text
precondition_failed: sensitive_outbound_authorization_missing
```

原 L5-A2b 授权未被用于联网运行，但其表述不足，不能直接复用。

### DeepSeek 实际会接收的数据

在需要模型决策且未命中本地快捷路径的回合，当前 `DeepSeekAIAgent` 会把以下内容组成 prompt，发送到 `https://api.deepseek.com` 的 `deepseek-v4-flash`：

- 本家当前手牌的规范化牌面 token 与手牌张数；
- 当前级牌、轮次、桌面领出动作与可压制约束；
- 已公开历史动作、pass、各玩家公开剩余张数、队伍/完赛信息；
- 当前 engine 生成并经剪枝的合法候选动作，包括牌型、声明牌、承载牌和逢人配公开描述；
- 基于本家手牌与公开历史形成的手牌评估、记牌摘要、场景标签；
- 从仓库本地规则库/经验库检索出的相关 RAG 文本片段。

这些数据包含本家尚未公开的手牌，属于本次对局的敏感游戏信息。数据离开本机后受 DeepSeek 服务的数据处理规则约束。

### 不发送的数据

adapter/runtime 契约禁止把以下内容放入模型 prompt：

- `BOTZONE_LOCAL_AI_URL` 及其中的连接密钥；
- DeepSeek API key 正文（仅作为 HTTPS Authorization Header 发送给 DeepSeek 服务）；
- Botzone match key、request digest、session record 或原始 envelope；
- Botzone 108 实体牌 ID；
- Botzone Header、Cookie、账号信息；
- engine 私有 state 或其他玩家隐藏手牌；
- 本机 `.env` 文件内容。

当前 confidence prompt 与 strategy-intent prompt 默认关闭；本次不额外启用。

### 固定网络预算

- Botzone endpoint：当前已配置的 `BOTZONE_LOCAL_AI_URL`，不得输出值。
- DeepSeek endpoint/model：`https://api.deepseek.com` / `deepseek-v4-flash`。
- 一个前台 connector；一个全新“需要进贡=否”测试桌。
- Botzone poll：最多 100 cycles，单次 timeout 120 秒。
- DeepSeek：单次 timeout 60 秒，retries 0。
- 最长运行 3600 秒，完成 1 个 qualified match 即停。
- 进程重启/补采/第二次运行：0。
- 全新系统临时 state/audit。

当前 runtime 没有独立模型请求总计数器。在只有一个活动测试桌、每次 poll 至多一个该桌待决策请求的前提下，每次需要模型决策最多发送一次 DeepSeek physical request；不能宣称精确模型调用总数。

### 必须获得的明确授权

只有用户在当前任务中明确回复等价于以下完整内容，才允许恢复执行：

```text
我明确授权执行 L5-A2b1：在一个全新无贡 Botzone 测试桌中，将本家当前手牌牌面、公开对局历史和状态、engine 生成的合法候选动作、手牌评估与记牌摘要、场景标签以及本地 RAG 检索片段发送到 https://api.deepseek.com 的 deepseek-v4-flash，用于选择合法 action_id。我理解这些信息包含本家尚未公开的手牌，并会离开本机。授权预算为：当前 BOTZONE_LOCAL_AI_URL 最多 100 次 GET，DeepSeek 单次超时 60 秒、零重试，一个 connector 进程，最长 3600 秒，完成一局即停。
```

历史授权或只授权 endpoint/次数的回复不满足本门槛。

### 授权后快速门槛

不重复全量回归，只确认：

1. HEAD 包含 `aac59d5`，实现文件无差异，工作区干净；
2. 23 项定向测试与 `git diff --check` 通过；
3. Botzone URL/key present，DeepSeek endpoint/model/timeout/retries 匹配；只报告布尔值；
4. 无残留 Botzone connector；
5. 用户确认只创建一个新无贡桌。

任一失败判 `precondition_failed`，不启动进程。

### 唯一 live 运行

授权后使用新的随机系统临时 state/audit，按原 L5-A2b 参数启动恰好一个前台进程。进程运行后通知用户检查 Botzone“已连接”，用户确认后再创建新无贡桌。

不得重试、延长、启动第二进程或在失败后补采。

成功门槛保持：exit 0、`finished_target`、qualified finished、非零 request/response/header、零 transport failure、空 diagnostics、Botzone 无非法动作/决策超时、state/audit 安全且无残留进程。

成功判定：

```text
botzone_deepseek_connector_no_tribute_smoke_verified
```

任一门槛失败：

```text
botzone_deepseek_connector_no_tribute_smoke_invalid
```

### 结论边界

即使通过，也只证明显式 deepseek 模式下的 Botzone 协议闭环和安全降级可以完成一局。当前 audit 不统计模型调用成功/fallback，因此不能证明 DeepSeek 实际返回有效 action，也不形成动作质量或胜率结论。

完成后报告固定聚合，不复述任何手牌、prompt、模型响应、URL、key、Header、match ID 或原始请求。
