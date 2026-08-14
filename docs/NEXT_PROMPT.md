# 下一步实施提示词

## Step L5-A2b3：v3 audit 恢复准入与单次 live 授权

本任务先做零网络恢复准入；未通过全部门槛、未确认旧桌已清理、未获得新的完整授权前，不得启动 live connector。

### 已确认基线

- L5-A2b1 唯一 live 结果永久保持：

```text
botzone_deepseek_connector_no_tribute_smoke_invalid
```

- 失败发生在用户确认新桌开始前：request=1、response/header/finished=0、`envelope_shape_invalid=1`；未进入 Agent 或 DeepSeek。
- L5-A2b2 已封存为 `37bdd0d`，唯一判定：

```text
botzone_envelope_shape_subdiagnostics_verified
```

- audit schema 升级为 `botzone_local_smoke_audit` v3；旧 `diagnostics` 字段语义不变，新增 `diagnostic_details`。
- 固定 detail 只有八种：
  - `envelope_top_level_invalid`
  - `envelope_required_fields_missing`
  - `envelope_unknown_field`
  - `envelope_optional_value_invalid`
  - `envelope_requests_not_list`
  - `envelope_responses_not_list`
  - `envelope_requests_empty`
  - `envelope_length_mismatch`
- 定向 24 项、全量 572 项、`git diff --check` 已通过；实现未联网、未读取真实配置或历史 audit。

### 本轮边界

本轮只能：

1. 复核检查点、工作区、24 项定向测试与配置元数据；
2. 执行恰好一次 `--agent deepseek --preflight-only` 零网络子进程；
3. 要求项目所有者人工确认所有历史 Botzone 本地 AI 测试桌均已结束或关闭；
4. preflight 和人工桌面门槛全部通过后，提出新的完整 live 授权问题。

本轮不得直接启动 live、不得 poll Botzone、不得调用 DeepSeek、不得创建 runner、不得读取 `.env` 或输出任何配置值。

### 检查点门槛

1. HEAD 必须包含 `37bdd0d`，其七个实现/测试文件相对检查点无差异。
2. `git status --short` 必须为空。
3. 运行：

```text
python -m unittest tests.test_botzone_request_diagnostics tests.test_botzone_poll tests.test_botzone_connector tests.test_botzone_runner -q
git diff --check
```

4. 只以布尔值确认 Botzone URL、DeepSeek key present；endpoint/model 精确匹配 `https://api.deepseek.com` / `deepseek-v4-flash`。
5. 无本项目残留 connector；不得终止归属不明的 Python 进程。

任一失败输出 `precondition_failed`，不得继续。

### 唯一零网络 preflight

- 使用系统临时目录中的全新随机 state 目录，初始必须为空；audit 不需要创建。
- 只运行一次：

```text
python -m integrations.botzone --agent deepseek --preflight-only --state-dir <fresh-temp-state>
```

- 30 秒硬上限，不重试。
- 必须 exit 0、stdout 规范化为单行 `preflight_ready`、stderr 为空、state 最终为空并删除、无残留进程。
- Botzone GET、DeepSeek request、DNS/socket/HTTP、connector cycle 和 `suggest_action_id()` 均为 0。

失败判 `botzone_deepseek_connector_v3_preflight_invalid`，不得请求授权。

通过判：

```text
botzone_deepseek_connector_v3_preflight_ready
```

### 人工桌面门槛

preflight 通过后，请项目所有者明确确认：

```text
我已结束或关闭所有历史 Botzone 本地 AI 测试桌；下一次只会在 connector 显示已连接后创建一个全新的“需要进贡=否”测试桌，不会同时保留或创建第二个活动桌。
```

未获得该确认，不得请求 live 授权。

### 后续 live 固定预算

- 当前 `BOTZONE_LOCAL_AI_URL`，最多 100 次 GET；
- `https://api.deepseek.com` / `deepseek-v4-flash`；
- 允许发送本家未公开手牌、公开历史/状态、合法候选、评估/记牌、场景标签和 RAG 片段；
- DeepSeek timeout 60 秒、retries 0；Botzone poll timeout 120 秒；
- 一个前台 connector、一个全新无贡桌、最长 3600 秒、完成一局即停；
- 全新系统临时 state/audit；不重试、不补采、不启动第二进程。

### 必须提出的新授权问题

只有前述门槛全部通过后，才向项目所有者请求等价于以下内容的授权：

```text
我明确授权执行 L5-A2b4：在已清理全部历史测试桌的前提下，启动一个 Botzone DeepSeek connector，并在连接后创建一个全新无贡测试桌；允许将本家未公开手牌及已列明的决策上下文发送到 https://api.deepseek.com 的 deepseek-v4-flash。预算为当前 BOTZONE_LOCAL_AI_URL 最多 100 次 GET、DeepSeek 单次超时 60 秒、零重试、一个 connector、最长 3600 秒、完成一局即停。我理解若外层信封再次失败，审计只会记录固定父诊断和八种安全 detail 之一。
```

本任务收到授权前结束，不得顺带执行 L5-A2b4。

### 结论边界

preflight ready 只证明 v3 代码在真实进程环境可本地构造，不证明 Botzone 信封已兼容、DeepSeek 可达、模型有效决策、动作质量或胜率提升。
