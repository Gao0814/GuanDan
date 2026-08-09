# 下一步实施提示词

## Step L4-A2c1：Botzone launcher 环境纯离线诊断

请在 GuanDan 项目中执行 Step L4-A2c1。本步只诊断上一轮唯一 `Start-Process` 调用为何在 connector 进程创建前返回 `launcher_environment_error`。不得启动 Botzone connector、不得联网、不得调用 Botzone URL、不得创建或加入对局，也不得修改仓库文件。

### 已封板事实

- L4-A1a 实现检查点：`029b8d6034e55c70b83d2b1c8d4b052626895bd2`；
- L4-A2a：`botzone_live_smoke_authorization_ready`；
- L4-A2b 唯一正式判定：`botzone_no_tribute_local_ai_smoke_invalid`；
- L4-A2b 启动前门槛全部通过；
- 唯一 `Start-Process` 调用返回 `launcher_environment_error`；
- 未创建 connector 进程，GET=0，未产生 live audit 或 state 证据；
- 未重试、未启动第二进程，仓库代码未修改。

L4-A2b 的 invalid 结论永久保留。本步不是 live 重试，也不继承上一轮联网授权；后续任何真实 Botzone 请求必须重新取得用户明确授权。

### 安全边界

1. 不读取、输出、散列或传递 `BOTZONE_LOCAL_AI_URL` 的值；不读取 `.env`、Cookie、Header、账号信息或浏览器存储。
2. 不运行 `python -m integrations.botzone`，不导入 connector、transport、session、adapter 或 Agent。
3. 只使用仓库外新建临时目录、标准库无网络子脚本和合成变量，例如 `CODEX_LAUNCH_SENTINEL`；合成值不得类似 URL、密钥或真实凭据。
4. 不修改仓库文件，不提交代码，不删除或清理 `D:\VsCodeProject\BotzoneState`。
5. 不把此前没有留存的 traceback、exit code 或具体根因当成已知事实。

### 启动前检查

只读确认：

- 工作区干净；
- `029b8d6034e55c70b83d2b1c8d4b052626895bd2` 是当前 HEAD 的祖先；
- 从该检查点到 HEAD 的变化仅限既有五份规划文档；
- 没有正在运行的 `python -m integrations.botzone` 进程。

任一项失败即停止，判定 `precondition_failed`。不得联网或修复仓库。

### 离线诊断矩阵

在仓库外本次专用临时目录创建最小标准库子脚本。子脚本只能输出以下脱敏布尔/枚举结果：

- 是否收到合成 sentinel；
- 当前工作目录是否等于调用方指定目录；
- 参数是否按预期到达；
- stdout/stderr 标记；
- 固定退出码。

依次验证并记录每一步是否成功：

1. 当前 PowerShell 版本/edition，以及 `Start-Process`、`-WindowStyle`、`-PassThru`、`-Wait`、`-WorkingDirectory`、`-RedirectStandardOutput`、`-RedirectStandardError` 是否可用；只报告版本和参数支持布尔值。
2. 当前解释器可执行文件能否以前台方式运行该无网络子脚本；不得输出解释器绝对路径。
3. `Start-Process` 能否以隐藏窗口、指定工作目录、`-PassThru -Wait` 启动同一脚本。
4. 合成 sentinel 能否由父进程继承到子进程；只报告 present/missing，不输出值。
5. stdout 与 stderr 分别重定向到两个不同文件时能否正常完成；不得把两个流定向到同一文件。
6. 使用与 L4-A2b 相同的参数传递形状，但把目标替换为无网络子脚本，验证参数引用、工作目录和退出码收集。

每个子进程必须有短超时；超时只终止该诊断子进程。所有失败必须记录规范化 stage、异常类型和脱敏消息，不保留命令行、环境值或绝对用户路径。不得为了获得成功而跳过失败步骤或改用网络目标。

### 根因与修复边界

- 只有某个诊断步骤可稳定复现失败，且修正后的无网络启动方式连续成功两次，才能把根因类别标为 verified。
- 根因类别只能从以下集合选择：`powershell_capability`、`python_resolution`、`argument_quoting`、`working_directory`、`environment_inheritance`、`stream_redirection`、`process_permission`、`unknown`。
- 不得仅凭 `launcher_environment_error` 名称猜测是环境变量问题。
- 本步不修改 runner 或 launcher。若确认需要仓库代码修复，只输出最小修复范围和应新增的离线测试，留给后续 L4-A2c2。

### 判定

若根因类别已由纯离线证据定位，且修正后的等价无网络启动连续成功两次：

```text
botzone_launcher_environment_diagnosis_verified
```

若证据不足、无法复现、不同运行结果不一致或安全边界无法满足：

```text
botzone_launcher_environment_diagnosis_inconclusive
```

不得在本步形成 `botzone_no_tribute_local_ai_smoke_verified`，也不得申请或消耗新的 live 授权。

### 最终报告

报告必须包含：

- HEAD 与工作区状态；
- L4-A2b invalid 保留声明；
- 诊断目录位置及非敏感文件的 bytes/SHA-256；
- 六步矩阵的 success/failure、规范化 stage 和根因类别；
- 修正方式的两次离线复验结果；
- request/GET/network/connector count 均为 0；
- 是否需要后续代码修改及最小文件/测试范围；
- 明确说明下一次 live 运行必须使用新任务、新预算和新的用户授权。
