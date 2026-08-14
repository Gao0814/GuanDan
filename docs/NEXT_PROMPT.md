# 下一步实施提示词

## Step L5-A2b6：v4 画像恢复准入与新授权准备

本任务只封存上一阶段实现并执行一次零网络 preflight；不得启动 live connector、不得连接 Botzone、不得调用 DeepSeek，也不得读取或输出 URL、密钥、Header、match、牌、历史请求、prompt 或模型响应。

### 已确认基线

- 当前基线 HEAD：`e1b9abce0214baef982eb5cc4f495a7336ce48bd`。
- L5-A2b4 永久判定为 `botzone_deepseek_connector_no_tribute_smoke_invalid`；该授权已消耗，不得重跑或补采。
- 失败请求未进入 session、adapter、Agent、RuleBased fallback 或 DeepSeek。
- L5-A2b5 已实现六种固定 profile：
  - `required_requests_missing`
  - `required_responses_missing`
  - `required_both_missing_empty_object`
  - `required_both_missing_inner_stage_candidate`
  - `required_both_missing_optional_only`
  - `required_both_missing_other_object`
- audit schema 已升级为 `botzone_local_smoke_audit` v4；v3 的 `diagnostics` 与 `diagnostic_details` 字段和语义保持不变，仅新增聚合 `diagnostic_profiles`。
- 已复核 36 项扩展定向测试和 574 项全量测试通过，`git diff --check` 通过；静态扫描仅命中普通列表操作，没有新增网络或敏感配置路径。
- L5-A2b5 的七个源码/测试文件目前尚未形成独立 Git 检查点。规划任务无权替实现任务提交非 docs 文件。

### 第一门槛：独立实现检查点

先确认以下七个文件已由实现任务单独提交，且提交不包含 docs 或其他文件：

```text
integrations/botzone/bot_io.py
integrations/botzone/poll.py
integrations/botzone/connector.py
integrations/botzone/runner.py
tests/test_botzone_request_diagnostics.py
tests/test_botzone_live_preflight.py
tests/test_botzone_finished_provenance.py
```

若工作区不干净、提交不存在或提交范围不精确，唯一结果为：

```text
precondition_failed: required_fields_profile_checkpoint_missing
```

此时不得运行 preflight、不得联网、不得请求 live 授权。

### 离线复核

实现检查点成立后，运行：

```text
python -m unittest tests.test_botzone_request_diagnostics tests.test_botzone_poll tests.test_botzone_connector tests.test_botzone_runner tests.test_botzone_live_preflight tests.test_botzone_finished_provenance -q
python -m unittest discover -q
git diff --check
```

同时只做静态边界复核：profile 不能进入 Header、session、Agent observation、prompt、RAG 或模型调用；audit 不得包含输入 key/value、长度、hash、match、牌或异常正文。

### 唯一零网络 preflight

仅在检查点、工作区和回归全部通过后：

1. 只检查 `BOTZONE_LOCAL_AI_URL` 与 DeepSeek key 为 present，不读取值；endpoint/model/timeout/retries 只输出是否匹配锁定值。
2. 锁定 DeepSeek 为 `https://api.deepseek.com`、`deepseek-v4-flash`、timeout 60 秒、retries 0。
3. 使用全新、仓库外、初始为空的系统临时 state 目录。
4. 在同一显式子进程环境中恰好运行一次：

```text
python -m integrations.botzone --agent deepseek --preflight-only --state-dir <fresh-state-dir>
```

5. 30 秒硬上限；不得重试。
6. 成功门槛：exit 0、stdout 规范化后精确为单行 `preflight_ready`、stderr 空、state 前后为空并删除、无残留 Python connector。
7. Botzone GET、DeepSeek request、DNS/socket/HTTP、connector cycle、`suggest_action_id()` 均必须为 0。

任一门槛失败时按阶段报告 `precondition_failed` 或 `botzone_deepseek_connector_v4_preflight_invalid`，不得继续。

### 通过后的动作

preflight 通过时唯一判定：

```text
botzone_deepseek_connector_v4_preflight_ready
```

随后只更新 docs，并向项目所有者提出新的 L5-A2b7 live 授权问题。授权问题必须再次完整列出：

- 将本家未公开手牌、公开局面、合法候选、评估/记牌摘要、场景标签和 RAG 片段发送到 DeepSeek；
- 当前 Botzone URL 最多 100 次 GET；
- DeepSeek 60 秒、零重试；
- 一个 connector、一个全新无贡桌、最长 3600 秒、完成一局即停；
- 所有旧测试桌已关闭，且只能在页面显示已连接后创建唯一新桌。

未获得新的明确授权前，不得启动 live connector。本步骤不形成 Botzone 协议闭环、DeepSeek 可达性、动作质量或胜率结论。
