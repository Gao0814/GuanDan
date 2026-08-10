# 下一步实施提示词

## Step U0-A2：Botzone 上传环境 DeepSeek 人工准入验收

本任务属于“**无需 connector 的 Botzone DeepSeek 完整体 Bot**”支线。本轮不修改代码，不调用本机 connector，不由 Codex 读取或处理真实 API key；由用户在 Botzone 页面完成人工上传和一次无贡测试，Codex 只负责前置复核、操作说明和结果判定。

### 已完成前置

- 规划检查点：`838669fc0cef05e5ec9774469027e6059b63f943`。
- U0-A1 实现检查点：`085162972363e634fe224c9f1725063b3cd13686`。
- 探测 ZIP：`dist/guandan_deepseek_probe_py36.zip`。
- ZIP 大小：4,982 bytes。
- SHA-256：`82ba5fd18b333b7a389316478042d53b07a22e0d4e4c00f992ade010fedf239c`。
- 稳定规则 ZIP 保持不变：SHA-256 `29e7ec827abf0ff6673bfeafab254cb9cc2174edc37bf1c802dcc15a346de351`。
- 定向 12 项、全量 556 项和 `git diff --check` 已通过。
- DeepSeek 只执行最小探测；实际 `response` 与规则 Bot 相同，不参与动作选择。

### 本轮目标

用一次人工 Botzone 测试确认：

1. 上传 Bot 能读取用户存储中的 `data/deepseek_credentials.json`；
2. Botzone 评测机能访问 `https://api.deepseek.com`；
3. `deepseek-v4-flash` 能在探测包 3 秒超时内返回最小响应；
4. 无论探测结果如何，Bot 仍输出规则动作，不出现决策超时或非法动作。

本轮不评估 DeepSeek 动作质量、胜率、RAG 或长时运行。

### Codex 前置复核

只读检查以下项目：

- HEAD 包含 U0-A1 检查点，工作区干净；
- 探测 ZIP 存在且大小/hash 精确匹配；
- ZIP 根目录只有 `__main__.py`；
- 稳定规则 ZIP hash 未变化；
- 不读取 `.env`、Botzone 账号、用户存储内容或 API key。

任何前置失败都停止，不指导用户上传错误产物。

### 用户人工操作

#### 1. 准备 Botzone 用户存储

1. 在仓库外创建 `deepseek_credentials.json`。
2. 文件必须是一个 JSON object，只包含字段 `api_key`，字段值为用户自己的真实 DeepSeek API key。
3. 不要把文件放入仓库，不要提交 Git，不要把内容发送给 Codex，也不要截取包含 key 的图片。
4. 在 Botzone“管理存储空间”中上传该文件，确保运行时路径为：

```text
data/deepseek_credentials.json
```

若 Botzone 存储页面会自动改变文件名或目录，先停止并报告页面行为，不猜测路径。

#### 2. 创建独立探测版本

在现有 Bot 下新增版本或创建独立测试 Bot：

- 游戏：GuanDan；
- 源代码：上传 `dist/guandan_deepseek_probe_py36.zip`；
- 编译器：Python 3.6.5；
- 使用 JSON 交互，不勾选“简单交互”；
- 不勾选“允许长时运行”；
- 不勾选“开源”；
- 不复用稳定规则版本作为覆盖目标，确保可以随时回退。

#### 3. 运行一次新无贡测试

1. 新建测试桌，不复用历史桌。
2. “需要进贡”明确选择“否”。
3. 只放入这个探测版本一次；其他座位使用已知可运行的规则 Bot。
4. 完成至少探测 Bot 的首个输出；如整局可继续则完成一局，但不要因探测失败自动重跑。
5. 在 Botzone 对局日志中只查看探测 Bot 的 `debug` 固定状态和平台显示的该回合运行时间。

### 只允许回报的信息

用户只需回报：

- 固定状态码之一；
- 是否出现 Botzone 决策超时；
- 是否输出了合法规则动作；
- 平台显示的该回合运行时间（若页面提供）；
- 对局是否完成。

不得回报 API key、Authorization Header、用户存储文件正文、DeepSeek 响应正文、完整手牌、完整 request/response 或账号信息。

### 固定状态解释

| 状态 | 含义 | 本轮判定 |
|---|---|---|
| `probe_ok` | 凭据可读、HTTPS/API 最小响应形状成功 | 若同时无 Botzone 超时且规则动作合法，则 verified |
| `credential_unavailable` | 用户存储路径、文件或 JSON 契约不可用 | blocked，不重跑 |
| `probe_timeout` | 3 秒内未返回 | blocked；长时运行不能解决单回合 API 延迟 |
| `probe_dns_or_connect_failed` | 沙箱 DNS/连接失败 | blocked |
| `probe_tls_failed` | TLS 建连失败 | blocked |
| `probe_http_4xx` | 认证、模型权限或请求被拒绝 | invalid；用户自行检查存储/key 状态，Codex 不读取 key |
| `probe_http_5xx` | 服务端失败 | inconclusive，本任务不自动重试 |
| `probe_response_invalid` | API 返回但不是预期最小 JSON 形状 | invalid |
| `probe_unexpected_failure` | 未知运行异常 | invalid |

### 验收门槛

唯一通过条件：

- `debug == probe_ok`；
- Botzone 未判决策超时；
- `response` 被裁判接受，未出现非法动作；
- 稳定规则 Bot 基线未被覆盖；
- 用户没有暴露任何凭据或敏感正文。

通过判定：

```text
botzone_deepseek_egress_admission_verified
```

其他状态按上表分别归类为 blocked、invalid 或 inconclusive，不得把规则动作正常输出误判为 DeepSeek 出网成功。

### 后续边界

- 本任务只允许一次人工测试，不自动重试、不修改探测包。
- `probe_ok` 只证明最小 API 请求可达，不证明真实牌局 prompt 能在时限内完成。
- 通过后下一步进入 U1：Python 3.6 完整无贡合法动作与公开状态 parity；DeepSeek 仍不参与动作。
- U1 完成后再迁移本地策略；真实动作选择和长时运行分别在 U3、U4 才开放。
- 若 U0-A2 blocked，则完整体支线停在平台能力阻塞，不回退到 connector，除非用户重新决定架构。

### 最终报告

报告 U0-A1 完整检查点、ZIP hash、人工固定状态、是否超时、动作是否合法、可用的运行时间、是否完成对局和唯一判定。明确声明未读取/输出 key，DeepSeek 未参与动作选择，也未形成动作质量或胜率结论。
