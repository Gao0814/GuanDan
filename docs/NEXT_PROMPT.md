# 下一步实施提示词

## Step L5-A2b9：direct-stage DeepSeek connector 零网络准入

前置实现已封存：

```text
2cd208b9b8f7306decf3182318fb55278c09d641
Support Botzone direct stage wire mode
```

唯一实现判定为 `botzone_local_ai_direct_stage_wire_contract_verified`。双模式定向 68 项、全量 583 项和 `git diff --check` 已通过，提交后工作区干净。本步骤不重复全量回归，不修改代码，只执行一次零网络本地准入。

### 固定边界

- 只读复核上述检查点存在且提交范围精确为 3 个 integration 文件和 4 个测试文件。
- 确认工作区干净、无残留 Botzone connector 进程。
- 只检查配置元数据：Botzone URL/key 为 present，DeepSeek endpoint/model/timeout/retries 精确匹配；不得输出值、URL、key 或路径。
- 使用项目 `.venv\Scripts\python.exe`，并在子进程环境中设置 `PYTHON_DOTENV_DISABLED=1`；不得读取仓库 `.env`。
- 使用系统临时目录下全新、空、仓库外 state 目录；结束后确认仍为空并删除。
- 只启动一次：

```text
python -m integrations.botzone --agent deepseek --preflight-only --state-dir <fresh-temp-state>
```

- 30 秒硬上限；不重试、不修代码、不启动 connector、不调用 runmatch。
- Botzone GET、DeepSeek request、DNS/socket/HTTP、transport、connector cycle、Agent action、`suggest_action_id()` 必须全部为 0。

### 结果分类

只有 exit 0、stdout 规范化为单行 `preflight_ready`、stderr 空、state 前后为空、无残留进程且全部网络/模型计数为 0，才能判定：

```text
botzone_direct_stage_deepseek_local_preflight_ready
```

否则按现有固定 preflight 分类报告 `precondition_failed` 或 `invalid`，不得添加新诊断载体或重跑。

### ready 后的动作

若且仅若准入通过，报告检查点、耗时、固定输出、state/进程和零网络计数，然后提出新的 L5-A2b10 完整授权问题。该授权问题必须再次锁定：

- 复用项目所有者上一轮提供的三个非本家 GuanDan Bot ID，`me=0`；Bot ID 仍不得落盘。
- 旧桌全部关闭；只允许一个 runmatch 对局。
- runmatch GET 最多 1 次、local-AI GET 最多 100 次。
- DeepSeek `deepseek-v4-flash`，timeout 60 秒、retries 0。
- 单 connector、最长 3600 秒、finished=1 即停。
- 省略 `X-Initdata`；非零 tribute 或 `tribute/return` 立即停止且不重试。
- 明确允许本家未公开手牌及现有 prompt/RAG 内容发送到 DeepSeek。

本步骤不得替项目所有者推定授权，也不得在同一步执行 live。
