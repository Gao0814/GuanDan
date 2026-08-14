# 下一步实施提示词

## Step L5-A2b12：long-poll v5 DeepSeek connector 零网络准入

前置实现已独立封存：

```text
220c648a4629453621f534beaeb95e52d85656ce
Harden Botzone long-poll provenance
```

唯一实现判定为 `botzone_long_poll_transport_contract_verified`。定向相关 80 项、全量 587 项和 `git diff --check` 已通过，提交后工作区干净。本步骤不重复测试、不修改代码，只运行一次零网络 preflight。

### 固定执行边界

1. 只读复核检查点存在，提交范围精确为 3 个 integration 文件和 5 个测试文件。
2. 确认工作区干净且无残留 Botzone connector/Python 进程。
3. 只检查配置元数据：Botzone local-AI URL 与 DeepSeek key 为 present；endpoint/model/timeout/retries 精确为锁定值。不得输出值、URL、key 或路径。
4. 使用项目 `.venv\Scripts\python.exe`，并在子进程环境设置 `PYTHON_DOTENV_DISABLED=1`；不得读取仓库 `.env`。
5. 在系统临时目录创建全新、空、仓库外 state 目录；运行后必须仍为空并删除。
6. 只启动一次：

```text
python -m integrations.botzone --agent deepseek --preflight-only --state-dir <fresh-temp-state>
```

7. 30 秒硬上限；不重试、不启动 connector、不调用 runmatch、不发送 Botzone/DeepSeek 请求。
8. Botzone GET、DeepSeek request、DNS/socket/HTTP、transport、connector cycle、Agent action 和 `suggest_action_id()` 必须全部为 0。

### 准入判定

只有 exit 0、stdout 规范化为单行 `preflight_ready`、stderr 空、state 前后为空、无残留进程且全部网络/模型计数为 0，才能判定：

```text
botzone_long_poll_deepseek_local_preflight_ready
```

否则按现有固定 preflight 类别报告 `precondition_failed` 或 `invalid`，不得新增诊断载体、修改代码或重跑。

### ready 后的新授权问题

若且仅若准入通过，报告检查点、固定输出、耗时、state/进程与零网络计数，并提出 L5-A2b13 的完整授权问题。不得在本步骤联网或推定授权。

授权问题必须要求项目所有者确认：

- 复用上一轮三个非本家 GuanDan Bot ID，`me=0`；Bot ID 只在内存使用。
- 所有旧本地 AI 测试桌已关闭。
- runmatch endpoint 最多 1 次 GET，local-AI endpoint 最多 100 次 GET。
- DeepSeek `https://api.deepseek.com` / `deepseek-v4-flash`，timeout 60 秒、retries 0。
- 允许发送本家未公开手牌、公开局面、engine 合法候选、手牌评估、记牌摘要、场景标签和本地 RAG 片段。
- 单 connector、单 runmatch 对局、最长 3600 秒、qualified finished=1 即停。
- 省略 `X-Initdata`；非零 tribute 或 `tribute/return` 立即停止且不重试。
- v5 audit 只保存聚合 timeout/failure category/finished provenance；不得保存敏感内容。

下一次 live 仍必须使用全新 state/audit，且不得因 timeout 重启第二个 connector；timeout 只作为 idle，其他 transport failure 继续受固定失败上限约束。
