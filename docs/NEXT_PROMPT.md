# 下一步实施提示词

## Step L4-A2c4b：Botzone preflight 超时诊断载体修复与独立恢复

请在 GuanDan 项目中执行 Step L4-A2c4b。本步修复上一轮临时诊断载体的 import-path 缺口，并在全新仓库外目录重新执行合成分阶段矩阵。不得修改旧证据、仓库代码或文档，不得接触真实 Botzone URL/state，不得启动 launcher、connector 或网络请求。

### 已封板事实

- L4-A2c2 检查点：`30d9b5897d97939f64dab32b97772118c72ef3d1`；
- L4-A2b：`botzone_no_tribute_local_ai_smoke_invalid`，永久保留；
- L4-A2c3a：`botzone_live_launcher_recovery_preflight_invalid`，永久保留；
- L4-A2c4a：`botzone_preflight_timeout_diagnosis_inconclusive`；
- L4-A2c4a 仅完成 `python_startup`；`runtime_config_import` 因临时脚本子进程没有仓库根 import path 而出现 `ModuleNotFoundError`；
- 该失败不是项目 import 行为的有效复现，根因类别保持 `unknown`；
- 后续阶段未执行，request/GET/network/connector/live-launcher count 均为 0。

旧 L4-A2c4a 证据目录 `C:\Users\86166\AppData\Local\Temp\guandan-botzone-preflight-diagnosis-5f8ae9fd8d4c4872ad0ce5e8bfebf177` 必须只读保持。文件 metadata：

- `phase_probe.py`：5,122 bytes / `d794c5a23e9c7151560a7055ed55c266c85ae4b7a518df8c00d6debc18b58c4f`；
- `driver.py`：2,757 bytes / `0eedb86a6b814454eaf4435e86c6bbad5b420ef54e0307e4a3ced2d4cf41cfb9`；
- `diagnosis.json`：575 bytes / `d479ea2f51a2f9010b513e3e1ae808cdbd46e090a48cf317ca8a66a82647b718`；
- 两份 heartbeat：62 / 106 bytes，hash 为 `4771e2d7b89850634318cd7f17d885e6ae914dcc4117b031da893bbe641b145c`、`13d3e64686e674055efb5e2128e8887e1da846fe24a2b131eb7c4e621653890d`。

### 启动前门槛

1. 工作区干净，`30d9b589...` 是当前 HEAD 的祖先，其后只允许规划 docs 提交；
2. L4-A2c3a summary 与上述 L4-A2c4a 证据 bytes/hash 全部不变；
3. 没有 `integrations.botzone`、`live_launcher` 或旧 diagnosis 子进程；
4. 新建全新的仓库外诊断目录，初始为空。

任一失败即 `precondition_failed`，不得修复或清理旧证据。

### 安全边界

- 只使用固定 `.invalid` 合成 URL和全新临时 state 目录；
- 不读取 `.env`、真实 `BOTZONE_*` 值、Cookie、Header、账号信息或实际 state dir；
- 不构造 transport/opener/socket，不调用 session、adapter、Agent 或 connector；
- 不修改仓库，不将诊断脚本提交到仓库；
- 子进程输出不得包含绝对用户路径、环境值、URL 全文、命令行或未脱敏 traceback。

### A. harness qualification

正式阶段前，先独立运行两次 qualification；两次均使用全新子目录，不计入八阶段配额。

固定调用方式：

- 父进程以仓库根作为 `cwd`；
- 子进程必须使用 `python -c`，通过 `runpy.run_path()` 执行仓库外 probe；不得直接执行临时 `.py` 文件；
- 不设置或修改 `PYTHONPATH`；
- 子进程先验证 `cwd` 为仓库根、`sys.path` 可从当前目录解析包、`importlib.util.find_spec("integrations.botzone.runtime_config")` 非空且 origin 位于预期仓库根；
- 只输出 `cwd_ok`、`path_ok`、`spec_ok`、`origin_ok` 四个布尔值，不输出实际路径。

两次 qualification 必须逐字段相等且全部为 true。否则判定 `diagnostic_harness_invalid`，不得执行正式阶段。

### B. 正式合成矩阵

qualification 通过后，在同一新任务中按顺序执行八阶段。每阶段使用独立 Python 子进程、独立临时 state 目录、原子 heartbeat、10 秒上限和脱敏 faulthandler；每个阶段最多一次：

1. `python_startup`
2. `runtime_config_import`
3. `main_import`
4. `config_load`
5. `state_preflight_steps`：`resolve → boundary → mkdir → tempfile → write → flush → fsync → replace → unlink → exit`
6. `state_preflight_function`
7. `main_function`：显式合成 URL/state、空 environment mapping、`--preflight-only`
8. `module_subprocess`：从仓库根执行 module，显式合成 URL/state、`--preflight-only`

每个正式子进程也必须使用已通过 qualification 的 `python -c + runpy.run_path` 形状，且在执行目标阶段前重复四个布尔自检；自检失败属于 `diagnostic_harness_invalid`，不归因项目。

只有 1–8 全部成功时，才允许用全新目录把阶段 8 再运行一次；两次都应在 10 秒内退出 0，输出精确为 `preflight_ready`。

### 根因与判定

允许的项目根因类别沿用：startup、runtime import、main import graph、config、各 state file-op、main function、module exit、parent wait。harness qualification/self-check 失败必须单独归类 `diagnostic_harness_invalid`。

若有效矩阵定位到项目阶段并有足够证据：

```text
botzone_preflight_timeout_diagnosis_recovery_verified
```

若有效矩阵全部通过，原 30 秒问题仍无法复现：

```text
botzone_preflight_timeout_diagnosis_recovery_inconclusive
```

若 qualification 或阶段自检失败：

```text
botzone_preflight_timeout_diagnostic_harness_invalid
```

三种结果均不得形成 preflight ready、提高 timeout、请求 live 授权或运行 launcher probe。

### 最终证据

仓库外保存：qualification 双运行、八阶段结果、heartbeat、规范化 diagnostics、canonical summary 和 manifest。报告必须包含：

- HEAD/工作区与两个 invalid、一次 inconclusive 保留声明；
- 旧证据 bytes/hash 前后不变；
- qualification 两次四布尔结果；
- 八阶段状态、退出码、耗时范围和最后 heartbeat；
- 阶段 8 是否执行确定性复验；
- 新证据文件 bytes/SHA-256；
- request/GET/network/connector/live-launcher count=0；
- 下一步只能依据有效诊断另行规划，不得直接 live。
