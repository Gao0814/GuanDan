# 下一步实施提示词

## Step L4-A3b1：preflight stdout 契约与独立恢复准入

请在 GuanDan 项目中执行 Step L4-A3b1。本轮只验证 `preflight_ready` 的控制流和跨平台 stdout 捕获契约，不读取真实配置、不运行真实环境 preflight、不启动 connector、不发送 GET，也不创建 Botzone 对局。

### 已封板事实

- L4-A3a 检查点：`2ac51fb2c80a5a0ae4b7dabd4f2aa161e11f1498`，提交范围精确为 19 个 allowlist 文件。
- L4-A3a 回归：定向 50、全量 532 项通过，`git diff --check` 通过。
- L4-A3b 唯一判定：`botzone_envelope_live_smoke_preflight_invalid`。
- L4-A3b 的唯一真实环境 preflight 恰好运行一次：30 秒内 exit 0、stderr 空、state 前后为空、request/GET/network/connector 全为 0。
- 唯一未通过项是监督结果 `stdout_is_preflight_ready=false`；没有合格的原始 stdout bytes，因此不得追认或改写 L4-A3b。
- 当前入口中，preflight exit 0 分支在 `print("preflight_ready")` 后立即 return 0；下一步必须用测试锁定该控制流和字节输出，不依赖人工推测。
- L4-A2b、旧 malformed-request smoke、L4-A3b 及全部既有 invalid/inconclusive 结论永久保留。

### A. 前置门槛

1. HEAD 必须包含 L4-A3a 检查点，工作区必须干净。
2. 只读复核 `integrations/botzone/__main__.py`、`runtime_config.py` 和现有 runtime/runner/preflight 测试。
3. 不读取 `.env`、`BOTZONE_LOCAL_AI_URL`、`BOTZONE_STATE_DIR` 或任何真实环境值；不检查其 presence。
4. 不查找、修改或补写 L4-A3b 的仓库外证据；原 invalid 保持不变。
5. 本轮只允许修改：

```text
tests/test_botzone_preflight_output.py
docs/BOTZONE_INTEGRATION_PLAN.md
docs/NEXT_PROMPT.md
docs/PLAN.md
docs/PROJECT_STATUS.md
docs/TESTS.md
```

存在其他差异即 `precondition_failed`。

### B. 固定输出契约测试

新增 `tests/test_botzone_preflight_output.py`，至少覆盖：

1. **直接 main 调用**
   - 显式传入合成 HTTPS URL、临时 state 目录和 `--preflight-only`；
   - `environ={}`，不继承或读取真实 Botzone 环境；
   - return code 精确为 0；
   - 捕获文本精确为 `preflight_ready\n`；
   - state 目录最终为空；
   - patch transport/opener 构造为一旦调用即失败，证明零网络路径。

2. **真实 module 子进程二进制捕获**
   - 从仓库根用当前 Python 执行 `python -m integrations.botzone`；
   - 通过命令参数传入合成 URL、全新临时 state 和 `--preflight-only`；
   - 子进程环境删除所有 `BOTZONE_*` 变量，不设置 `PYTHONPATH`；
   - stdout/stderr 使用标准库 binary PIPE 直接捕获，不经过 PowerShell 重定向、文本文件或 shell 解码；
   - exit code 0、stderr bytes 精确为空；
   - stdout bytes 只允许 `b"preflight_ready\n"` 或 Windows 合法的 `b"preflight_ready\r\n"`；
   - UTF-8 严格解码后，`splitlines()` 必须精确等于 `['preflight_ready']`；拒绝 BOM、NUL、前后空格、额外行或其他文本；
   - state 目录最终为空。

3. **确定性**
   - module 子进程使用两个全新临时目录独立运行两次；
   - 两次 normalized line、exit、stderr 和目录结果完全一致；
   - 原始 bytes 可因 LF/CRLF 合法差异而不同，但不得放宽其他字符。

测试只能使用 `example.invalid` 或等价保留域，不得包含真实 URL、密钥、match ID、Header 或手牌。

### C. 控制流结论边界

只有同时满足以下条件，才能形成独立恢复准入：

- 直接 main 输出契约通过；
- 两次 module binary capture 通过；
- transport/opener 未构造；
- state 临时目录均为空；
- 当前入口仍保持“打印固定文本后 return 0”的单一 preflight 成功路径；
- 全部 Botzone 回归与全量测试通过。

这只能说明 L4-A3b 的 `stdout_is_preflight_ready=false` 与当前程序输出契约不一致，合理归类为监督/捕获假阴性；不得声称已恢复原始 stdout bytes，也不得改写 L4-A3b invalid。

### D. 验证

运行：

```text
python -m unittest tests.test_botzone_preflight_output -q
python -m unittest tests.test_botzone_runtime_config tests.test_botzone_runner tests.test_botzone_live_preflight tests.test_botzone_instrumented_preflight -q
python -m unittest discover -q
git diff --check
```

同时扫描新增测试，确认不存在真实配置、`.env` 读取、网络请求、Cookie、DeepSeek 或 live 数据。

### E. 判定与提交

任一完整性、输出、确定性、零网络或回归门槛失败：

```text
botzone_preflight_stdout_contract_invalid
```

全部通过：

```text
botzone_live_smoke_recovery_authorization_ready
```

通过后只提交上述 allowlist，提交信息：

```text
Verify Botzone preflight output contract
```

提交后工作区必须干净。

### F. 后续 live 预算

本步不得执行 live。只有唯一判定为 ready 时，最终报告末尾才能原样请求：

```text
已完成 L4-A3b1 独立 stdout 契约恢复审计。拟使用当前已配置的 BOTZONE_LOCAL_AI_URL，启动一次前台 RuleBasedAI 无贡 smoke：全新测试桌、全新 LocalAppData state/audit，最多 100 次 GET，timeout 120 秒，最长 900 秒，完成 1 局即停，不重试。是否明确授权执行本次 L4-A3c 真实 Botzone 请求？
```

用户未明确授权前不得读取真实配置或联网。

### 最终报告

报告必须包含：

- 执行 HEAD、工作区和 L4-A3a 检查点；
- 新增测试文件；
- 直接 main 与两次 module 捕获的 exit、stdout bytes 分类、normalized lines、stderr 和 state empty；
- transport/opener/request/GET/network/connector count；
- 定向、相关、全量测试与 `git diff --check`；
- 提交 hash 与精确文件列表；
- 唯一判定；
- 对 L4-A3b invalid 不追认声明；
- ready 时的固定授权问题。
