# 下一步实施提示词

## Step L4-A2c5a：Botzone 可审计零网络 preflight 契约

请在 GuanDan 项目中执行 Step L4-A2c5a。由于有效合成矩阵无法复现 L4-A2c3a 的 30 秒超时，本步不再重复黑盒诊断，而是新增一个轻量、分阶段、原子落盘的专用 preflight 入口，使未来真实环境检查即使超时也能保留最后完成阶段。本步只实现和测试契约，不消费真实 Botzone 配置、不联网。

### 已封板事实

- L4-A2c2 检查点：`30d9b5897d97939f64dab32b97772118c72ef3d1`；
- L4-A2b 与 L4-A2c3a 的 invalid 永久保留；
- L4-A2c4a 的 inconclusive 永久保留；
- L4-A2c4b 判定：`botzone_preflight_timeout_diagnosis_recovery_inconclusive`；
- 两次 harness qualification 的 cwd/path/spec/origin 全部为 true；
- 八阶段与阶段 8 复验全部在 1 秒内退出 0；
- 规范化根因：`not_reproduced`；
- request/GET/network/connector/live-launcher count 均为 0。

L4-A2c4b 证据目录 `C:\Users\86166\AppData\Local\Temp\guandan-botzone-preflight-recovery-1cb88ed2b01c4edaaf4396d8ad55ac17` 必须只读保持：

- `runpy_probe.py`：5,797 bytes / `87a385bfad4728bd8b55420f1de4cce99f20b2e8a6f2f3b6f0cc7e0abddcdb7b`；
- `driver.py`：3,941 bytes / `51e5fb9604f1eadb66e4c20e2f2c3af1ab0057ba8fdea0224444a22718e20012`；
- `summary.json`：2,432 bytes / `38d7bda0f0a32907632c59ff92948a47a2037e016dedd344aae73b60925fbd3e`；
- `manifest.json`：1,425 bytes / `30f01deb4a9cbf67dec55dd7520db9ab12fd1cf2da33cf240c65b8b730a08376`。

### 启动前门槛

1. 工作区干净；
2. `30d9b589...` 是当前 HEAD 的祖先，其后只允许规划 docs 提交；
3. L4-A2c3a、L4-A2c4a、L4-A2c4b 证据 metadata/hash 全部不变；
4. 没有 connector、live launcher 或 diagnosis 子进程。

任一失败即 `precondition_failed`，不得修改代码或证据。

### 允许修改范围

仅允许：

- 新增 `integrations/botzone/live_preflight.py`；
- 新增 `tests/test_botzone_instrumented_preflight.py`；
- 为暴露逐文件操作阶段，最小修改 `integrations/botzone/runtime_config.py` 及其对应 `tests/test_botzone_runtime_config.py`。

不得修改 `__main__.py`、live launcher、transport、runner、session、adapter、protocol、engine、agents 或 docs。不得新增依赖。

### 专用入口契约

生产调用形式：

```text
python -m integrations.botzone.live_preflight --audit-file <仓库外新文件>
```

要求：

1. `live_preflight.py` 顶层只导入标准库；先解析/验证仓库外绝对 audit path 并原子写入 `bootstrapping`，之后才延迟导入 `runtime_config`。
2. 只从既有 `load_runtime_config()` 消费当前进程的 `BOTZONE_LOCAL_AI_URL` / `BOTZONE_STATE_DIR`；不得接受 `--url`、`--state-dir`、任意透传参数或 `.env`。
3. 不导入 `integrations.botzone.__main__`、runner、transport、connector、session、adapter 或 Agent；不得构造 opener/socket/request。
4. audit 采用 frozen/slots 结果对象或等价严格结构，schema/version 固定；每个阶段原子覆盖写入，并保留到当前为止的规范化 stage tuple。
5. audit 只能包含 status、stages、exit code、规范 diagnostics，以及 request/GET/network/connector count=0；不得包含 URL、state/audit path、环境值、PID、命令行、异常正文、match ID 或手牌。
6. 配置错误、audit 写入错误、state preflight 错误、KeyboardInterrupt 和未预期异常使用稳定、互异退出码；所有异常整体脱敏。
7. 成功必须输出单行固定 `instrumented_preflight_ready`，退出 0，并在 audit 中以 `completed` 结束。

### state 阶段回调

最小扩展 `preflight_state_directory()`，增加可选 keyword-only stage callback；默认 `None` 时现有行为和签名调用保持兼容。回调只接收固定枚举阶段，不接收路径或异常：

```text
resolve
boundary_checked
directory_ready
temporary_opened
written
flushed
synced
replaced
cleaned
```

live preflight 在每个回调后更新 audit。回调异常必须 fail-closed，并由 preflight 入口规范化；不得留下 probe/replacement 文件。现有 `--preflight-only` 行为不改变。

### 测试要求

使用注入式 loader/prober/writer 或等价 seam，覆盖：

- 首次 audit 在 runtime import/loader 前已经存在；
- 正常完整阶段顺序、固定输出和退出 0；
- 每个 state 阶段均可在 audit 中观察；
- config、import、每个 file-op、callback、audit write、中断和未知异常分类；
- audit 路径相对、仓库内、已存在、目录冲突和非法参数 fail-closed；
- audit 原子替换，失败不产生半 JSON；
- callback 默认关闭时原 runtime config 测试快照不变；
- audit/to_dict/repr/异常不含合成 URL/path；
- 边界扫描确认不导入 transport/runner/connector/Agent，不读取 dotenv。

新增一次完全合成的子进程测试：显式提供合成环境变量和仓库外临时 state/audit，运行专用 module；必须在 10 秒内退出 0、输出固定文本、state dir 为空、audit 阶段完整。不得使用真实环境值。

### 验证命令

```text
python -m unittest tests.test_botzone_instrumented_preflight tests.test_botzone_runtime_config -q
python -m unittest tests.test_botzone_live_launcher tests.test_botzone_live_preflight tests.test_botzone_runner tests.test_botzone_runtime_config tests.test_botzone_instrumented_preflight -q
python -m unittest discover -q
git diff --check
```

### 判定

全部契约、合成子进程、回归和边界扫描通过：

```text
botzone_instrumented_live_preflight_contract_verified
```

任一门槛失败：

```text
botzone_instrumented_live_preflight_contract_invalid
```

通过只允许进入 L4-A2c5b 的真实环境零网络 preflight。不得在本步读取真实配置、运行真实 preflight、执行 launcher probe、请求 live 授权或联网。

### 最终报告

报告必须包含修改文件、阶段/退出码契约、定向/相关/全量测试、合成子进程结果、边界扫描、`git diff --check`，并明确 request/GET/network/connector/live-launcher count=0。若通过，下一步仍是单独的 L4-A2c5b，不得直接 live。
