# 下一步实施提示词

## Step L5-A2b6：v4 profile 零网络恢复准入

本任务只复核已封存实现并执行恰好一次零网络 DeepSeek connector preflight。不得启动 live connector、连接 Botzone、调用 DeepSeek、创建测试桌或复用任何历史 live 授权。

### 已确认基线

- L5-A2b5a 实现检查点：`8e8d639011bd095bcf0af74816609c63e8c6199f`。
- 提交信息：`Add safe Botzone required fields profiles`。
- 提交范围精确为四个 runtime 文件和三个测试文件，工作区已确认干净。
- 定向 36 项、全量 574 项和 `git diff --check` 已通过。
- audit schema 为 `botzone_local_smoke_audit` v4；v3 的 `diagnostics`、`diagnostic_details` 语义保持不变，仅新增 allowlist 聚合 `diagnostic_profiles`。
- L5-A2b4 永久保持 `botzone_deepseek_connector_no_tribute_smoke_invalid`；旧授权已消耗，不得重跑或补采。

### 前置复核

1. 确认 HEAD 包含 `8e8d639011bd095bcf0af74816609c63e8c6199f`，且该提交范围仍精确为七个文件。
2. `git status --short` 必须为空。
3. 运行：

```text
python -m unittest tests.test_botzone_request_diagnostics tests.test_botzone_poll tests.test_botzone_connector tests.test_botzone_runner tests.test_botzone_live_preflight tests.test_botzone_finished_provenance -q
python -m unittest discover -q
git diff --check
```

4. 只检查以下配置元数据，不输出值，不读取 `.env`：
   - `BOTZONE_LOCAL_AI_URL`：present；
   - DeepSeek API key：present；
   - endpoint 精确匹配 `https://api.deepseek.com`；
   - model 精确匹配 `deepseek-v4-flash`；
   - timeout 为非 bool 数值 60；
   - retries 为非 bool 整数 0。
5. 确认没有残留 Botzone connector Python 进程。

任一前置失败时返回明确 `precondition_failed`，不得创建 preflight 子进程、不得联网或请求 live 授权。

### 唯一 preflight

前置全部通过后：

1. 在系统临时目录创建一个全新、随机、仓库外、初始为空的 state 目录。
2. 在显式锁定 timeout=60、retries=0 的同一子进程环境中，恰好运行一次：

```text
python -m integrations.botzone --agent deepseek --preflight-only --state-dir <fresh-state-dir>
```

3. 硬上限 30 秒，零重试。
4. 成功门槛：
   - exit code 0；
   - stdout 规范化后精确为单行 `preflight_ready`；
   - stderr 为空；
   - state 目录结束后仍为空并删除；
   - 无残留 Python connector 进程；
   - Botzone GET、DeepSeek request、DNS/socket/HTTP、connector cycle、`suggest_action_id()` 均为 0。
5. 审计只保留布尔门槛、退出码、规范化 stdout 类别、耗时和零网络计数；不得保留路径、URL、key、Header、Cookie、牌、请求、prompt、RAG、reasoning 或模型响应。

preflight 一旦启动，任何门槛失败都判定：

```text
botzone_deepseek_connector_v4_preflight_invalid
```

不得重试、换目录或继续 live。

### 通过后的动作

通过时唯一判定：

```text
botzone_deepseek_connector_v4_preflight_ready
```

随后只更新 docs，并向项目所有者提出 L5-A2b7 的新授权问题。授权问题必须重新明确：

- 允许把本家尚未公开的手牌牌面与张数发送给 DeepSeek；
- 允许发送公开历史/状态、engine 合法候选、手牌评估、记牌摘要、场景标签及本地 RAG 片段；
- 目标固定为 `https://api.deepseek.com` / `deepseek-v4-flash`；
- 当前 Botzone URL 最多 100 次 GET；DeepSeek timeout 60 秒、retries 0；
- 恰好一个 connector、一个全新“需要进贡=否”测试桌、最长 3600 秒、完成一局即停；
- 所有历史测试桌必须先关闭，只能在 Botzone 显示已连接后创建唯一新桌。

未获得新的完整授权和旧桌清理确认前，不得执行 L5-A2b7。本步骤不形成协议闭环、DeepSeek 可达性、动作质量或胜率结论。
