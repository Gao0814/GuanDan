# 下一步实施提示词

## Step L5-A2b12a：仓库外 state 权限恢复与零网络 preflight

L5-A2b12 的唯一结果为：

```text
precondition_failed: temporary_state_directory_unavailable
```

检查点、工作区、配置元数据和无残留进程门槛均已通过，但当前沙箱权限无法在系统临时目录创建全新 state 目录，因此 preflight 子进程没有启动。全部 Botzone/DeepSeek/DNS/socket/HTTP/transport/connector/Agent 计数为 0。该结果不是 runtime、配置或 connector 失败。

本步骤不修改代码、不增加诊断、不重复测试或配置复核。唯一目标是在获得明确的仓库外文件写入批准后，完成原 L5-A2b12 的同一个零网络 preflight。

### 固定执行方式

1. 复用已通过的元数据结论；只快速确认工作区仍干净、无残留 connector。
2. 对单个受限命令请求提升权限，理由仅为：
   - 在系统临时目录创建一个全新、随机命名、空的 state 目录；
   - 使用项目 `.venv\Scripts\python.exe` 运行一次 `--agent deepseek --preflight-only`；
   - 检查目录仍为空并删除。
3. 提升权限不得用于网络放宽、读取 `.env`、读取配置值或启动 live connector。
4. 子进程环境必须设置 `PYTHON_DOTENV_DISABLED=1`；不得继承或打印敏感值。
5. 只启动一次：

```text
python -m integrations.botzone --agent deepseek --preflight-only --state-dir <approved-fresh-temp-state>
```

6. 30 秒硬上限；不重试、不调用 runmatch，不发送 Botzone/DeepSeek 请求。
7. 若权限请求被拒绝、目录仍无法创建或目录不为空，立即返回 `precondition_failed`，不得改用仓库内目录或历史 state 目录。

### 准入判定

只有 exit 0、stdout 规范化为单行 `preflight_ready`、stderr 空、state 前后为空并删除、无残留进程且全部网络/模型计数为 0，才能判定：

```text
botzone_long_poll_deepseek_local_preflight_ready
```

否则按现有固定类别报告并停止；不得修改代码、增加载体或重跑。

### ready 后

若准入通过，提出新的 L5-A2b13 完整 live 授权问题，不在本步骤联网。授权问题继续锁定上一轮三个非本家 Bot ID、`me=0`、旧桌关闭、一次 runmatch GET、最多 100 次 local-AI GET、DeepSeek 60/0、单 connector/单对局/3600 秒、无贡 fail-closed、敏感手牌发送授权和 v5 聚合审计边界。
