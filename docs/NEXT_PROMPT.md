# 下一步实施提示词

## Step L4-A2c2：Windows Botzone live launcher 离线加固

请在 GuanDan 项目中执行 Step L4-A2c2。目标是替换已验证会在 Windows PowerShell 5.1 中失败的 `Start-Process -RedirectStandardOutput/-RedirectStandardError` 编排，新增一个最小、可测试、默认不联网的 Python launcher。只实现和验证启动/流重定向边界，不执行真实 Botzone 请求。

### 已封板事实

- 当前文档基线 HEAD：`493a76443b74ed4f724c66d5879d20a920bf6894`；
- L4-A1a 实现检查点：`029b8d6034e55c70b83d2b1c8d4b052626895bd2`；
- L4-A2b 永久判定：`botzone_no_tribute_local_ai_smoke_invalid`；
- L4-A2c1 判定：`botzone_launcher_environment_diagnosis_verified`；
- PowerShell Desktop 5.1 支持 `Start-Process` 的隐藏窗口、工作目录、PassThru 和 Wait，但分流 stdout/stderr 重定向稳定在创建进程前抛出 `ArgumentException`；
- 去除 PowerShell 内建重定向后，等价无网络启动连续两次成功；
- 已验证根因类别：`stream_redirection`，不是仅由父环境继承导致；
- L4-A2c1 request/GET/network/connector count 均为 0。

L4-A2c1 证据目录 `C:\Users\86166\AppData\Local\Temp\guandan-botzone-launch-diagnosis-b7e96cb1b1ec4fbe8ec6ff497735382f` 和既有文件必须只读保持，不复制进仓库、不修改、不补写。本步不继承任何 live 授权。

### 启动前门槛

1. 工作区干净；
2. `493a76443b74ed4f724c66d5879d20a920bf6894` 是当前 HEAD 的祖先；
3. 从该基线到当前 HEAD 的变化仅限 `docs/BOTZONE_INTEGRATION_PLAN.md`、`docs/NEXT_PROMPT.md`、`docs/PLAN.md`、`docs/PROJECT_STATUS.md`、`docs/TESTS.md`；
4. L4-A2c1 三份证据的 bytes/SHA-256 仍分别为：`child_probe.py` 700 / `56f885eb44f41860e4f7ee19a843d96015e3e97e18332625f5477cd36a3f0d2b`，`sentinel_probe.py` 348 / `76da7669356e7f62ffcc46cf68f6d2434f38120a527d9ee34402857738ae4faa`，`diagnosis.json` 1,358 / `274f01535beb79b64167edcaaf63322a91961ebaf216efe7e86443691fa2489e`；
5. 没有正在运行的 `python -m integrations.botzone` 或 live launcher 进程。

只允许读取证据 metadata/hash，不读取或修改其内容。任一门槛失败即 `precondition_failed`，不得修改代码、创建 launcher、联网或清理状态。

### 允许修改范围

仅允许新增或最小修改：

- `integrations/botzone/live_launcher.py`；
- `tests/test_botzone_live_launcher.py`；
- 如 module 入口确有必要，可最小修改 `integrations/botzone/__init__.py`，但不得修改现有 `__main__.py`、runner、transport、session、adapter、engine 或 agents。

不得修改 docs；项目规划文档由后续任务统一更新。不得新增第三方依赖。

### launcher 契约

1. 生产启动方式固定为：PowerShell `Start-Process` 只负责以隐藏窗口、指定仓库工作目录创建 `python -m integrations.botzone.live_launcher`；不得再使用 PowerShell 的两个 Redirect 参数。
2. launcher 在自身进程内用 Python 标准库分别打开 stdout 与 stderr 文件，再调用既有 `integrations.botzone.__main__.main()`；不得创建第二个 connector 子进程。
3. stdout、stderr、connector audit 必须是仓库外绝对路径、三者互不相同；stdout/stderr 必须位于同一个本次专用空目录，并以拒绝覆盖既有文件的方式创建。
4. launcher 只把固定允许的 connector 参数传给既有 main：timeout、max cycles、max wall、stop-after-finished、audit file。不得接受或转发 `--url`、`--state-dir`、preflight 或任意未知参数。
5. URL 和 state dir 仍只能由子进程继承的现有环境提供；launcher 不读取、记录、输出、复制、散列或持久化其值。
6. stdout/stderr 必须在正常返回、异常和中断路径 flush/close；launcher 返回既有 connector exit code。launcher 自身验证失败使用独立稳定退出码和固定脱敏错误类别，不输出路径、命令行、环境值或异常链。
7. launcher 不改变 foreground runner、audit schema、session 持久化或 Botzone 协议行为。
8. 不实现自动重启、runmatch、DeepSeek、daemon 管理、第二进程或 live retry。

### 可测试性

核心执行函数必须支持注入 entrypoint 或等价无网络 seam，使单元测试无需导入/运行真实 connector transport，即可验证：

- 合成环境变量可见性只以 present/missing 表示；
- stdout/stderr 分别进入不同文件；
- 参数、工作目录和固定退出码保持；
- entrypoint 异常被规范化且两个流关闭；
- 路径相同、仓库内路径、相对路径、已存在文件、非法参数和 bool 冒充整数均 fail-closed；
- 输入 argv/mapping 不被修改；
- 错误、repr、审计和测试 fixture 不包含真实 URL、密钥、Header、match ID 或手牌。

### Windows 平台离线回归

新增一项仅使用合成子脚本的 Windows PowerShell 5.1 回归：

1. 在仓库外临时目录创建无网络 probe；
2. 用 `Start-Process` 的隐藏窗口、工作目录、PassThru 和 Wait 启动 launcher，但不使用 PowerShell Redirect 参数；
3. 由 launcher 内部创建两个独立流文件；
4. 验证合成 sentinel present、参数和工作目录正确、stdout/stderr 分流、固定退出码正确；
5. 连续执行两次，每次使用全新目录，结果结构一致；
6. 明确记录 network/GET/connector count 为 0。

非 Windows 平台可以按明确原因 skip 该平台测试，但通用单元测试必须运行。不得为了测试读取真实 `BOTZONE_*` 变量值；平台 probe 不得导入 connector 或网络模块。

### 验证

至少运行：

```text
python -m unittest tests.test_botzone_live_launcher -q
python -m unittest tests.test_botzone_runtime_config tests.test_botzone_runner tests.test_botzone_live_preflight tests.test_botzone_live_launcher -q
python -m unittest discover -q
git diff --check
```

边界扫描必须确认新模块和测试没有 `.env`/dotenv、真实 URL、API key、Cookie、Header 值、DeepSeek、runmatch、ground truth、`game._state` 或额外网络客户端依赖。

### 判定

全部通用和 Windows 离线测试通过，且两次平台 probe 均证明环境继承与分流正确：

```text
botzone_windows_live_launcher_hardening_verified
```

任一实现、平台、隐私、流关闭或回归门槛失败：

```text
botzone_windows_live_launcher_hardening_invalid
```

不得在本步启动真实 connector、请求 live 授权或形成 smoke 通过结论。通过只允许进入 L4-A2c3a 的零网络准入审计；L4-A2b invalid 永久保留。

### 最终报告

报告需列出：

- 修改文件与 launcher 契约；
- PowerShell 调用中已移除的 Redirect 参数；
- 定向、相关、全量测试结果；
- 两次 Windows 合成平台 probe 结果；
- network/GET/connector count=0；
- 边界扫描与 `git diff --check`；
- 未修改 engine、agents、协议、runner/session/transport；
- 下一步仍是零网络 L4-A2c3a，不得直接 live。
