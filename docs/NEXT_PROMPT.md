# 下一步实施提示词

## Step L5-A4e4：带 provenance token 的新容量批次准入

L5-A4e3 已完成并封存：

```text
botzone_paired_policy_run_provenance_contract_verified
```

实现检查点：`45d34f0d443847aea527929e2a7c0ebf9e4bdd5a`，精确包含 6 个实现/测试文件。定向 34 项、兼容 35 项、全量 617 项与 `git diff --check` 均通过。

### 固定边界

- 旧 seed `24001/24002`、`25001/25002` 及其容量根目录永久只读封存；不得读取、清理、迁移或复用任何 audit/state。
- 新 seed 固定为 `26001/26002`。
- 新容量根目录固定为 `D:\VsCodeProject\BotzonePairedCapacity-26001-26002`。
- 赛程仍为 2 seed × 4 seat × rule/deepseek，共 8 对/16 局；AB/BA 各 4 对。
- 项目所有者常驻默认授权有效。本步骤不得询问目录、manifest、preflight 或后续 live 授权。
- 既有 `README.md` 改动不得触碰或提交。

### 本步骤目标

创建带 16 个唯一 `run_token` 的新 canonical manifest、隔离 state/audit 布局，并分别完成一次 rule/deepseek 零网络 preflight。本步骤不启动 live connector、不创建 Botzone 对局、不调用 DeepSeek。

### 执行要求

1. 只读复核 HEAD 包含 L5-A4e3 检查点、提交范围准确、工作区除既有 `README.md` 外无改动，并用仅枚举 `python.exe/pythonw.exe` + 独立 `-m integrations.botzone` 参数的方式确认无残留 connector。
2. 新容量根不存在时允许创建一次；已存在时必须严格为空。目录不可创建、非空、是链接、位于仓库内或与旧容量根重合时立即停止，不清理、不换路径。
3. 使用现有 `BenchmarkConditions` 与 `build_paired_schedule((26001, 26002), conditions)` 在内存生成赛程，严格断言 8 对/16 局、rule/deepseek 各 8、AB/BA 各 4、四座位各 2 对。
4. 每局 token 使用固定公式：

```text
sha256("botzone-capacity-run-token/v1|<game_index>|<seed>|<seat>|<strategy>").hexdigest()[:32]
```

   `game_index` 使用 manifest 中 1..16 的十进制值；编码为 ASCII。必须验证 16 个 token 均为 32 位小写十六进制且互不重复。token 不从 match/player、URL/key、牌或其他敏感值派生。
5. manifest 升级为新的固定版本，除既有非敏感赛程字段外，每局新增 `run_token`。相对 state/audit 路径必须 canonical、无绝对路径/`..`/重复/冲突，解析后仍位于新根目录。
6. 通过同目录临时文件、flush/fsync 与 `os.replace()` 原子写入唯一 `capacity-manifest.json`；拒绝覆盖已有目标。写后验证 schema、全部守恒、bytes 与 SHA-256，不输出 manifest 正文或 token 列表。
7. 只按 manifest 创建 16 个独立空 state 目录和 audit 父目录；16 个 game audit 目标必须不存在。不得创建旧批次 artifact 或未预注册 game 文件。
8. 低敏配置门槛保持：Botzone local-AI URL present；DeepSeek key present；endpoint=`https://api.deepseek.com`、model=`deepseek-v4-flash`、timeout=60、retries=0。不得输出配置值，不读取 `.env`。
9. 使用项目 `.venv\Scripts\python.exe`，显式设置 `PYTHON_DOTENV_DISABLED=1`。从 manifest 选择 game 1 rule 与 game 2 deepseek，分别恰好执行一次 `--preflight-only --run-token <对应 token>`；rule 失败时不得执行 deepseek。
10. 每次 preflight 必须 30 秒内 exit 0、stdout 规范化为单行 `preflight_ready`、stderr 为空、所用 state 前后为空、audit 目标不存在、无残留 connector。
11. 两次 preflight 的 Botzone GET、DeepSeek request、DNS/socket/HTTP、transport、connector cycle、Agent action 与 `suggest_action_id()` 均为 0。
12. 两次通过后复核 manifest 不变、16 个 state 为空、16 个 audit 目标不存在，并写一个不含路径/token/配置值的脱敏 preflight summary，只记录 schema/version、manifest bytes/hash、固定计数、退出码、布尔门槛和零网络计数。
13. 任一步失败立即停止，不重跑、不改 seed/token 公式/参数、不清理已创建的新根内容、不进入 live。

### 判定

全部通过时：

```text
botzone_paired_policy_tokenized_capacity_preflight_ready
```

否则：

```text
botzone_paired_policy_tokenized_capacity_preflight_invalid
```

### ready 后的人工桌执行边界

ready 后直接按常驻授权进入 L5-A4e5，不再请求授权。每局必须：

1. 使用 manifest 对应的唯一 state、audit 和 `--run-token` 启动一个 connector；
2. 持有并监控该 Python 子进程句柄，不以命令行模糊搜索替代；
3. Botzone 页面显示已连接且子进程仍存活后，才提示项目所有者创建唯一无贡桌；这是操作提示，不是授权请求；
4. 提示建桌前再次确认 audit 不存在、state 为空、进程存活；等待人工操作期间持续监控进程；
5. 子进程在“已进入对局”确认前退出时立即停止整批，并提示不要建桌或关闭刚创建的桌；不得重启该局；
6. 对局完成后必须同时验证 exit 0、`finished_target`、v8 audit、v4 tombstone，以及二者 token 与 manifest 精确相等，随后才进入下一局。

L5-A4e4 本身不得执行上述 live 流程。
