# 下一步实施提示词

## Step L5-A4d3：容量布局与双模式零网络 preflight

L5-A4d2d 已完成，唯一判定：

```text
botzone_paired_policy_capacity_manifest_recovery_verified
```

### 固定前置

- 容量根目录：`D:\VsCodeProject\BotzonePairedCapacity-25001-25002`。
- 根目录当前只包含 `capacity-manifest.json`，不得存在其他文件或目录。
- manifest：3256 bytes，SHA-256 `3af862cf31f9600746812b0534c4d0b66ce6c8fbd6fdc94c1331f19451b2607e`。
- 赛程：seed `25001/25002`、8 对/16 局、rule/deepseek 各 8 局、AB/BA 各 4 对、四个本家座位各 2 对。
- L5-A4a/L5-A4b 检查点与 L5-A4d1 的定向 8 项、全量 612 项、`git diff --check` 证据继续有效，本步骤不重复测试。
- 既有 `README.md` 改动属于项目所有者，本步骤不得触碰或提交。

本步骤已由项目所有者指定为下一动作，不再请求目录布局或零网络 preflight 授权。它不得启动 live connector、创建 Botzone 对局或调用 DeepSeek。

### 执行边界

1. 只读复核 HEAD、工作区、无残留 connector，以及容量根目录当前精确只有固定 manifest。任一不符立即停止，不清理、不修正。
2. 重新读取 manifest，严格验证 bytes、SHA-256、schema/version、固定 profile、seed、seat、pair/game 序号、策略顺序、AB/BA、相对 state/audit 名称与全部守恒。不得信任未验证路径。
3. 所有 manifest 相对路径必须为 canonical、安全、无 `..`、无绝对路径，解析后仍位于容量根目录；重复、冲突或未知布局立即停止。
4. 只创建 manifest 预注册的 16 个独立 state 目录及其 audit 父目录。state 必须初始为空；每局 audit 目标必须不存在。不得创建未列入布局的 game artifact。
5. 使用项目 `.venv\Scripts\python.exe`，并在两个独立子进程中设置 `PYTHON_DOTENV_DISABLED=1`；不得读取 `.env`，不得输出 URL、key 或环境值。
6. 配置只做低敏元数据门槛：Botzone URL/key present；DeepSeek key present；endpoint=`https://api.deepseek.com`、model=`deepseek-v4-flash`、timeout=60、retries=0。任何不匹配在子进程前停止。
7. 从 manifest 中固定选择 game 1 的 rule state 与 game 2 的 deepseek state；分别恰好运行一次：

```text
python -m integrations.botzone --agent rule --state-dir <game-01 state> --preflight-only
python -m integrations.botzone --agent deepseek --state-dir <game-02 state> --preflight-only
```

8. 每次 preflight 都必须在 30 秒内自行 exit 0，stdout 规范化后精确为单行 `preflight_ready`，stderr 为空，所用 state 前后为空且无残留 Python/connector 进程。
9. 两次 preflight 的 Botzone GET、DeepSeek request、DNS/socket/HTTP、transport、connector cycle、Agent action 与 `suggest_action_id()` 均必须为 0。不得用网络探针验证配置。
10. rule preflight 失败时不得启动 deepseek preflight；任一步失败都停止，保留已创建的预注册空布局，不删除 manifest、不重跑、不改参数、不进入 live。
11. 两次都通过后，复核 16 个 state 目录仍为空、16 个 game audit 目标仍不存在、manifest bytes/hash 不变，并写出只含固定布尔值、计数、退出码、耗时类别和 manifest hash 的脱敏 preflight 汇总；不得包含路径、配置值、stdout 原始 bytes 或异常正文。

### 判定

全部通过时唯一判定：

```text
botzone_paired_policy_capacity_recovery_preflight_ready
```

否则唯一判定：

```text
botzone_paired_policy_capacity_recovery_preflight_invalid
```

### 成功后的下一动作

ready 后不得直接 live。只输出 L5-A4d4 的完整批量授权文本，等待项目所有者明确回复；由于届时唯一缺项是授权，不得修改 `NEXT_PROMPT.md` 或其他文档，也不得创建 Git 提交。

L5-A4d4 授权必须明确覆盖：按 manifest 串行执行 16 局人工无贡桌；每局一个 connector、一个 state、一个 v7 audit；最多 1600 次 Botzone GET、最多 800 次 DeepSeek 请求；DeepSeek timeout 60 秒、retries 0；任一局失败全批停止且不得补采；禁止额外测试桌、runmatch、CLI DeepSeek 对局和第二 connector；允许向 DeepSeek 发送此前已授权的本家手牌与公开决策上下文。
