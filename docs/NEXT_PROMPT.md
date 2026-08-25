# 下一步实施提示词

## Step L5-A4e6：tokenized capacity launcher 兼容性封板

L5-A4e5 已停止，唯一判定：

```text
botzone_paired_policy_tokenized_capacity_invalid
```

### 固定事实

- 失效批次根目录为 `D:\VsCodeProject\BotzonePairedCapacity-26001-26002`；manifest 仍为 3635 bytes，SHA-256 `f1793c836670378e03de2269232faaa845931eff296d9d81e6a8fecc85663241`。
- `capacity-progress.json` 已原子标记 `batch_invalid_before_table`，completed=0、next game=1；game 1 state 为空、v8 audit 不存在，game 2--16 未启动。
- 唯一 connector 在提示人工建桌前退出；没有保留合格的 connector exit code、stdout、stderr 或启动阶段证据，因此不能归因于 Botzone GET、DeepSeek、协议、run token、配置或 state 文件操作。
- 该批次永久无效，不得重试、补采、继续后续局或复用 seed `26001/26002`。
- 既有 connector 本体已经分别完成过人工无贡协议闭环和 DeepSeek 观测闭环；本步不得重写 connector、adapter、协议或 Agent。
- 当前 `integrations/botzone/live_launcher.py` 只支持通用时限/audit/stream 参数，不能显式传递容量运行需要的 `--agent`、`--state-dir` 与 `--run-token`。L5-A4e5 因而没有复用已验证的流捕获 launcher，外层启动失败也没有留下可分类证据。

项目所有者常驻默认授权继续有效；本步为纯离线实现，不询问授权。

项目所有者另已明确授权后续 live 任务使用 Codex 桌面/浏览器控制监督 Botzone 页面。完成一次登录并打开本地 AI/测试桌页面后，Codex 应自行确认“已连接”、创建唯一无贡桌、填写预注册 seed/seat/profile、确认进入对局并监控结束，不再要求项目所有者逐局回复“已连接”或“已进入对局”。仅登录、验证码、平台安全确认、浏览器控制不可用或页面状态无法可靠识别时暂停请求人工处理；不得读取、回显或持久化连接密钥、local-AI URL、Cookie 或账号信息。

### 目标

只加固现有 Windows live launcher，使它能安全、显式地启动 tokenized rule/deepseek connector，并在 connector 进入任何网络路径前就具备可审计的进程退出码及独立 stdout/stderr。不得新增另一套 connector、诊断 runner 或进程树。

### 允许修改

- `integrations/botzone/live_launcher.py`
- `tests/test_botzone_live_launcher.py`
- 如现有 launcher 测试边界确有需要，可最小更新一份直接相关 Botzone launcher 测试；不得修改 `engine/`、`agents/`、protocol/session/runner、DeepSeek client、CLI 或 evaluation。

### 实现契约

1. launcher 新增并严格要求 `--agent rule|deepseek`、仓库外绝对 `--state-dir`、严格 32 位小写十六进制 `--run-token`；继续要求既有 timeout/cycle/wall/finished/audit/stdout/stderr 参数。
2. `connector_argv()` 必须把 agent、state dir 与 run token 原样传给现有 `integrations.botzone.__main__.main()`，不得自行读取环境配置、构造 transport、Agent 或 session。
3. launcher 仍在同一 Python 进程内调用既有入口，不创建第二个 connector 子进程；PowerShell 只负责创建并持有这一 launcher 进程。
4. stdout/stderr 使用拒绝覆盖的仓库外独立文件；任何 parse、stream open、entrypoint 或返回类型错误都保持固定低基数退出分类。
5. token 只允许存在于进程内参数和现有 provenance 路径；不得进入 `repr`、异常文本、stdout/stderr、launcher summary、测试 snapshot 或文档示例。state/audit 路径同样不得写入错误文本。
6. 现有无 token launcher 行为若仍有外部使用者，需明确选择：保持兼容的旧入口，或用测试证明本 launcher 仅服务 tokenized capacity。不得静默改变普通 `python -m integrations.botzone` 的 v3/v7 默认行为。
7. 不得读取 `.env`、真实 URL、API key、旧容量 artifact 或真实 state；不得执行 preflight、connector、Botzone GET、DeepSeek 请求或 DNS/socket/HTTP。

### 测试

- 合法 rule/deepseek 参数均生成精确 connector argv。
- 非法/缺失/重复 agent、state、token、stream 参数整体拒绝。
- token 的大写、长度错误、非 hex、bool/非字符串输入均拒绝。
- state 必须绝对且仓库外；三个输出文件继续满足独立、仓库外、拒绝覆盖边界。
- fake entrypoint 精确收到 agent/state/token；固定 exit code、stdout/stderr 分流与异常分类保持稳定。
- 测试中只使用合成 token 和临时目录；扫描确认 token 值不进入 repr、错误输出或持久测试 artifact。
- 现有 Windows PowerShell 合成 probe 继续通过，且 network/connector/Agent/model count 为 0。
- 运行 launcher 定向测试、相关 Botzone 回归、全量回归和 `git diff --check`。

### 判定

全部通过：

```text
botzone_tokenized_live_launcher_contract_verified
```

任一实现、兼容、脱敏或测试门槛失败：

```text
botzone_tokenized_live_launcher_contract_invalid
```

通过后独立提交最小实现检查点。下一步使用全新 seed/root 先做一次可见前台单局启动资格：Codex 持有 launcher 进程句柄并通过桌面/浏览器控制确认 Botzone 页面显示“已连接”，随后自行创建唯一无贡桌并确认进入对局，同时保留固定 stream/exit 证据。该单局成功后再规划新的 16 局批次；不得恢复 `26001/26002`。
