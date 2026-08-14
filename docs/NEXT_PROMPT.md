# 下一步实施提示词

## Step L5-A2a：Botzone DeepSeek connector 真实环境零网络 preflight

本轮只执行一次受监督的真实环境 `--preflight-only`。不得启动 connector 主循环，不得发送 Botzone GET，不得调用 DeepSeek，不得创建或加入测试桌，也不得读取、输出、复制、散列或持久化 API key、本地 AI URL、Header、Cookie、prompt、模型响应或 `.env` 内容。

### 已确认基线

- L5-A1 实现检查点：`71d9119`。
- L5-A1a 加固检查点：`aac59d5`（`Harden Botzone DeepSeek connector startup`）。
- L5-A1a 已锁定：
  - 默认 handler 的 `agent_failure`、`invalid_agent_action_id`、`missing_provenance`；
  - DeepSeek 路径的一次 RuleBased fallback，以及 `rule_fallback_failure`、`invalid_rule_fallback_action_id`、`missing_provenance`；
  - deepseek 本地组合先于 Botzone transport 构造；
  - `--preflight-only --agent deepseek` 不构造 transport、不调用 `suggest_action_id()`、不 poll。
- 规划复核已再次运行定向 23 项、全量 569 项和 `git diff --check`，全部通过。
- 当前唯一判定：

```text
botzone_deepseek_connector_hardening_verified
```

### 本轮目标

在真实本机进程环境中证明以下本地链路可以完成，但网络调用计数仍为 0：

```text
Botzone runtime config shape
  -> fresh repository-external state-directory file preflight
  -> DeepSeek config presence/shape
  -> DeepSeekClient construction (no request)
  -> local RAG load
  -> disposable DeepSeekAIAgent construction (no select_action)
  -> preflight_ready
```

### 前置门槛

1. 当前 HEAD 必须精确包含 `aac59d5`，且 L5-A1/L5-A1a 文件相对检查点无差异。
2. `git status --short` 必须为空；不允许 stash、还原、提交或清理用户改动来满足门槛。
3. 重新运行：

```text
python -m unittest tests.test_botzone_deepseek_agent_runtime tests.test_botzone_action_provenance tests.test_botzone_runner tests.test_botzone_preflight_output -q
python -m unittest discover -q
git diff --check
```

4. 只检查以下元数据，不输出值：
   - `BOTZONE_LOCAL_AI_URL`：present/missing；
   - `DEEPSEEK_API_KEY`：present/missing；
   - `DEEPSEEK_BASE_URL`：只允许报告是否精确匹配 `https://api.deepseek.com`；
   - `DEEPSEEK_MODEL`：只允许报告是否精确匹配 `deepseek-v4-flash`。
5. 不直接打开 `.env`。应用既有配置入口可能按项目契约加载环境配置，但任务不得读取、打印或复制文件内容；若上述显式进程环境元数据缺失，判定 precondition failed，不依赖查看 `.env` 补齐。
6. 确认不存在本项目残留 connector/Python 进程；不得终止无法确认归属的进程。

任一前置失败，立即输出固定失败原因并停止，不创建 preflight 子进程。

### 受监督 preflight

1. 在 `%LOCALAPPDATA%` 下创建一个全新、随机命名、仓库外的空 state 目录；不得复用任何历史 Botzone state 目录。
2. 不使用 `BOTZONE_STATE_DIR` 的既有值；通过 `--state-dir` 显式传入本轮新目录。
3. 只执行一次：

```text
python -m integrations.botzone --agent deepseek --preflight-only --state-dir <fresh-absolute-directory>
```

4. 使用 30 秒硬上限。不得重试、提高上限或启动第二个进程。
5. 必须完整捕获并规范化：exit code、stdout 单行类别、stderr 是否为空、运行时长、state 目录前后是否为空，以及进程是否退出。
6. 成功门槛必须全部满足：
   - 30 秒内自行退出；
   - exit code 0；
   - stdout 规范化后精确为单行 `preflight_ready`；
   - stderr 为空；
   - state 目录最终为空；
   - 无残留进程；
   - Botzone GET、DeepSeek request、DNS/socket/HTTP、connector cycle、`suggest_action_id()` 均为 0。
7. preflight 结束后只删除本轮新建且确认为空的 state 目录；不得操作其他目录。

### 证据与隐私

- 可以在仓库外新建脱敏 summary，内容仅限上述布尔值、计数、exit code、耗时和固定分类。
- 不得记录 URL、key、环境变量值、路径中的敏感片段、Header、match ID、牌、request/response、prompt、reasoning 或异常正文。
- stdout/stderr 若不满足固定类别，只记录 `unexpected_stdout` / `unexpected_stderr`，不要在报告中复述原文。
- 不修改仓库文件，不创建 runner 源码，不联网，不提交仓库外证据。

### 判定

全部成功门槛通过时，唯一判定：

```text
botzone_deepseek_connector_live_preflight_ready
```

任一门槛失败时，使用以下唯一判定并报告失败阶段：

```text
botzone_deepseek_connector_live_preflight_invalid
```

不得重试或用推测补齐证据。

### 结论边界

`ready` 只证明真实本机配置、state 文件操作、RAG 与 DeepSeek Agent 的零网络构造可用。它不证明：

- Botzone 本地 AI URL 当前在线；
- connector 能完成 GET/Header 协议闭环；
- DeepSeek endpoint 可达或模型能返回；
- 单回合延迟可接受；
- 动作质量或胜率提升。

本轮结束时不得启动 live connector，也不得请求模型。若 preflight 通过，下一步只更新 docs，形成 L5-A2b 的固定请求预算与明确授权问题。

完成后请报告：

1. HEAD、工作区和回归结果；
2. 四项配置元数据门槛；
3. preflight exit/stdout/stderr/耗时/state 结果；
4. 零网络与零残留进程证据；
5. 唯一判定；
6. 未解决风险。
