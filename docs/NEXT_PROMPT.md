# 下一步实施提示词

## Step U0-A1：Botzone 上传 Bot 的 DeepSeek 出网与时限探测包

本任务属于新支线“**无需 connector 的 Botzone DeepSeek 完整体 Bot**”。本轮只实现离线可测试的 Python 3.6.5 探测包，不调用真实 DeepSeek、不读取真实用户存储、不连接 Botzone，也不修改现有规则 Bot 基线。

### 背景

- 当前 HEAD：`cf35a205131cfc9b94c28491e0a8b092abdc0d30`。
- 已有上传产物：`dist/guandan_rule_ai_py36.zip`，ZIP 根目录为 `__main__.py`，兼容 Botzone Python 3.6.5。
- 用户已将该规则 Bot 在 Botzone 完整运行两局，未发现协议或出牌错误；这只证明当前无贡、自然牌规则子集可运行，不代表完整合法动作覆盖或 DeepSeek 可用。
- Botzone 上传 Bot 由平台直接运行，不需要本地 connector。connector 支线保留，但暂停作为当前下一步。
- Botzone 官方文档确认：多文件 Python ZIP 根目录需要 `__main__.py`；数据文件通过用户存储上传并以 `data` 路径访问；长时运行可减少冷启动，但不会取消每回合时限。
- DeepSeek 官方文档当前列出 `https://api.deepseek.com` 与模型 `deepseek-v4-flash`。
- **仍未确认**：Botzone 评测沙箱是否允许出站 HTTPS，以及一次 `deepseek-v4-flash` 请求能否在 Botzone Python 单回合时限内返回。

### 目标

制作一个独立的 Python 3.6.5 上传 ZIP，用一次人工 Botzone 对局安全验证：

1. 能否从 Botzone 用户存储读取 DeepSeek 凭据文件；
2. 能否从 Botzone 沙箱访问 DeepSeek HTTPS API；
3. 在严格短超时、零重试下，请求是成功、超时还是被网络/认证策略拒绝；
4. 无论探测结果如何，实际出牌始终由现有规则 Bot 决定，不能让探测影响动作合法性或导致超时后无输出。

本步不实现 DeepSeek 动作选择，不宣称“完整体 Bot”已完成。

### 允许修改范围

- 新增 `botzone_deepseek_probe_py36/__main__.py`；如确有必要，可在该目录增加少量 Python 3.6 模块。
- 新增 `tests/test_botzone_deepseek_probe_py36.py`。
- 新增 `dist/guandan_deepseek_probe_py36.zip`。
- 如需复用当前规则 Bot，只能复制后做隔离演进；不得修改：
  - `botzone_upload_py36/__main__.py`
  - `dist/guandan_rule_ai_py36.zip`
  - `engine/`
  - `agents/`
  - `integrations/botzone/`
  - `cli/`、`rag/`、`evaluation/`
  - `.env`、`.env.example` 和任何 `docs/` 文件

不得新增第三方依赖。运行时代码只能使用 Python 3.6.5 标准库。

### 用户存储与密钥边界

1. 凭据只从 Botzone 用户存储的固定 `data` 子路径读取；代码和测试中只能出现路径契约，不能出现真实 key、示例 key 或 key 摘要。
2. 缺少文件、空文件、格式错误或不可读时，记录固定状态 `credential_unavailable`，立即使用规则动作。
3. key 不得进入 `debug`、`data`、`globaldata`、stdout、stderr、异常正文、测试快照或 ZIP 内文件。
4. 不读取仓库 `.env`、进程 `DEEPSEEK_*` 环境变量、Botzone connector URL 或本机配置。
5. 不把用户存储描述为专用 secrets manager；它只是当前 Botzone 官方提供的文件存储能力。

### DeepSeek 探测契约

1. 使用 `urllib.request` 直接调用官方 OpenAI-compatible `chat/completions` 接口，不依赖 OpenAI SDK。
2. endpoint 和模型固定为官方值：
   - base URL：`https://api.deepseek.com`
   - model：`deepseek-v4-flash`
3. 只发送最小非流式探测请求，限制输出 token；不发送手牌、history、Botzone request、玩家信息或真实动作候选。
4. 单次短超时，默认不超过 3 秒；零重试。实现必须确保网络调用结束后仍有时间生成并输出规则动作。
5. 每局最多探测一次。传统 JSON 交互下使用非敏感 `data` 标志避免每回合重复探测；不得依赖仅存在于单次进程内的全局变量。
6. 探测结果只允许以下固定分类：
   - `probe_ok`
   - `credential_unavailable`
   - `probe_timeout`
   - `probe_dns_or_connect_failed`
   - `probe_tls_failed`
   - `probe_http_4xx`
   - `probe_http_5xx`
   - `probe_response_invalid`
   - `probe_unexpected_failure`
7. 不记录 URL、Header、Authorization、HTTP 正文、模型正文、异常正文或动态状态码；如需保留结果，只能通过不含敏感内容的 `debug`/`data` 固定分类。
8. API 返回是否成功都不得改变 Botzone `response`。本步 DeepSeek 返回正文必须被忽略。

### 动作与失败降级

1. `response` 必须与同一输入下现有 `botzone_upload_py36` 规则 Bot 的输出逐字段相同。
2. deal、play、pass、历史重放和输入失败行为保持当前规则 Bot 契约。
3. 网络探测必须在规则动作已经计算完成后执行；任何探测异常都回到已计算的规则动作。
4. 不允许 DeepSeek 直接生成 Botzone 牌 ID、`[action, claim]` 或绕过规则动作生成。
5. 本步不启用 Botzone 长时运行标记；先用传统交互验证出网和单次延迟，避免同时引入会话状态变量。

### 必测场景

- Python 3.6 grammar 解析通过，运行时代码仅使用标准库。
- ZIP 根目录存在 `__main__.py`，不覆盖规则 Bot ZIP，大小不超过 Botzone 页面限制。
- 凭据缺失、空、格式错误、读取异常：零网络调用，规则动作正常输出。
- fake opener 成功：只探测一次，分类为 `probe_ok`，模型正文不进入任何输出。
- fake timeout、DNS/connect、TLS、HTTP 4xx、HTTP 5xx、非法 JSON、未知异常：分类稳定且规则动作不变。
- fake opener 捕获请求，确认使用 HTTPS、固定模型、非流式、短超时、零重试；Authorization 值只在内存请求 Header 中出现。
- 同一局后续回合携带 `data` 时不再次探测。
- 所有 fixture 使用合成 key 和合成牌局；测试失败信息不得包含 key。
- 现有 `tests.test_botzone_upload_py36` 继续通过，且同一组合法输入下 baseline/probe 的 `response` 完全相同。
- 全量测试和 `git diff --check` 通过。
- 测试期间不得产生真实 DNS、socket 或 HTTP 请求。

### 验证命令

```text
python -m unittest tests.test_botzone_upload_py36 tests.test_botzone_deepseek_probe_py36 -q
python -m unittest discover -q
git diff --check
```

### 判定

全部离线契约通过：

```text
botzone_deepseek_probe_package_verified
```

任何 baseline 动作变化、真实联网、密钥泄露、重复探测、Python 3.6 不兼容或降级失败：

```text
botzone_deepseek_probe_package_invalid
```

### 后续边界

- 通过后先独立提交探测包，再由用户人工上传到一个新 Bot 版本。
- 人工上传时由用户自行把真实凭据放入 Botzone 用户存储；不得在对话、仓库或调试日志中提供凭据内容。
- 只有人工结果为 `probe_ok` 且延迟留有稳定余量，才进入 U1“完整合法动作与当前策略能力的 Python 3.6 迁移”。
- 若出网被禁止或稳定超时，则该支线必须判定受平台能力阻塞；长时运行不能被当作放宽单回合 API 时限的替代方案。
- 本步不修改或恢复 connector 支线，不形成动作质量或胜率结论。

### 最终报告

报告修改文件、ZIP 路径与 SHA-256、Python 3.6 兼容性、固定诊断分类、baseline/probe response 等价性、测试数量、边界扫描、工作区状态和唯一判定；明确声明未联网、未读取真实用户存储或密钥、DeepSeek 未参与动作选择。
