# 下一步实施提示词

## Step L5-A4d3a：双模式 preflight 恢复

L5-A4d3 未达到 ready，唯一判定：

```text
botzone_paired_policy_capacity_recovery_preflight_invalid
```

### 项目所有者常驻授权

项目所有者已明确：本项目后续全部计划内操作默认授权，不再逐步询问授权。该常驻授权覆盖仓库外 state/audit 写入、零网络 preflight、Botzone connector/GET、人工无贡测试桌和既定 DeepSeek endpoint/model/数据范围与预算。

后续任务不得再以“缺少用户授权”为停止原因，也不得只为申请授权修改文档或创建 Git 提交。仅在以下情况暂停并请求项目所有者执行或提供信息：

- Botzone 网页必须由用户人工创建/结束测试桌或确认连接状态；
- 缺少无法从本地安全确定的 Bot ID、座位、目录等运行输入；
- Codex/操作系统弹出不可绕过的权限审批；
- 实际技术门槛失败，需要报告结果并重新规划。

常驻授权不允许输出密钥、URL 中的连接凭据、Header、Cookie、手牌原文、prompt/response 原文，也不允许破坏性清理未知文件、越过 manifest 预算、修改 `.env` 或执行项目外任务。

### 已完成边界

- 固定 manifest：3256 bytes，SHA-256 `3af862cf31f9600746812b0534c4d0b66ce6c8fbd6fdc94c1331f19451b2607e`。
- 8 对/16 局、rule/deepseek 各 8、AB/BA 各 4、四座位各 2 对的守恒已验证。
- 16 个预注册 state 目录已创建且均为空；16 个 game audit 目标均不存在。
- manifest bytes/hash 不变；仓库未修改，既有 `README.md` 改动未触碰。
- L5-A4d3 的 rule/deepseek preflight 均未启动，网络与模型请求为 0。

### 已确认失败原因

旧残留 connector 检查在命令行文本中搜索 `integrations.botzone`，因此匹配了包含该搜索字样的检查命令自身。这是假阳性，不是 connector 残留、配置失败或 preflight 失败。

L5-A4d3 不得追认为通过；L5-A4d3a 是新的独立恢复执行，不修改 preflight 参数或 manifest。

### 执行要求

1. 只读复核 HEAD、工作区、manifest bytes/hash，以及 16 个 state 目录为空、16 个 audit 目标不存在。不得重新创建或清理布局。
2. 残留检查只枚举进程名为 `python.exe` 或 `pythonw.exe` 的进程，再检查其命令行是否包含独立参数 `-m integrations.botzone`；不得把 PowerShell/Codex/检查命令自身列为候选。
3. 记录候选 Python connector 数量，不记录完整命令行、路径、参数值或环境内容。数量非 0 时技术门槛失败并停止，不终止未知进程。
4. 使用项目 `.venv\Scripts\python.exe`；两个子进程均显式设置 `PYTHON_DOTENV_DISABLED=1`，不读取 `.env`。
5. 低敏配置门槛保持：Botzone local-AI URL present；DeepSeek key present；endpoint=`https://api.deepseek.com`、model=`deepseek-v4-flash`、timeout=60、retries=0。不得输出 URL/key。
6. 使用已预注册的 game 1 rule state，恰好运行一次 rule preflight。必须在 30 秒内 exit 0、stdout 规范化后为单行 `preflight_ready`、stderr 为空、state 前后为空、无残留 Python connector。
7. rule 通过后，使用已预注册的 game 2 deepseek state，恰好运行一次 deepseek preflight；门槛与 rule 相同。
8. 两次运行的 Botzone GET、DeepSeek request、DNS/socket/HTTP、transport、connector cycle、Agent action 与 `suggest_action_id()` 必须全部为 0。
9. 任一步失败即停止，不重跑、不改参数、不清理预注册布局、不进入 live。
10. 两次都通过后，写出原 L5-A4d3 规定的脱敏 preflight 汇总，并复核 manifest、16 个空 state 与 16 个不存在的 game audit 目标保持不变。

### 判定与衔接

全部通过时唯一判定：

```text
botzone_paired_policy_capacity_recovery_preflight_ready
```

否则唯一判定：

```text
botzone_paired_policy_capacity_recovery_preflight_invalid
```

ready 后不再请求 L5-A4d4 授权。直接按常驻授权进入容量执行准备；只有在需要项目所有者人工创建下一张无贡测试桌时，才提示具体操作，不得把人工操作提示写成授权问题。
