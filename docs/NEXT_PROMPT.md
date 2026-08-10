# 下一步实施提示词

## Step L4-A3c2：Botzone 安全诊断检查点与零网络恢复准入

本轮只封存 L4-A3c1 实现并执行零网络 preflight，不启动 connector、不发送 GET、不创建测试桌，也不请求或使用旧授权。

### 已确认基线

- L4-A3c1 唯一判定：`botzone_malformed_request_safe_diagnostics_verified`。
- 实现前 HEAD：`9bdd53494723eb77e3ec6266c2cded1eec4c27c7`。
- 允许的未提交实现精确为：
  - `integrations/botzone/bot_io.py`
  - `integrations/botzone/poll.py`
  - `tests/test_botzone_request_diagnostics.py`
  - `tests/test_botzone_poll.py`
  - `tests/test_botzone_connector.py`
- 已报告验证：新诊断 4 项、相关 Botzone 22 项、全量 538 项、`git diff --check` 与边界扫描通过。
- L4-A3c 的 `botzone_no_tribute_local_ai_smoke_invalid` 永久保留，原授权已消耗。

### A. 检查点封存

1. 核对当前工作区除五个实现/测试文件外没有任何未提交内容；若有额外文件，判定 `precondition_failed`，不得暂存、还原或清理。
2. 复核差异只包含固定错误分类与测试，不得读取真实 URL、`.env`、请求正文或历史 live state。
3. 重新运行：

```text
python -m unittest tests.test_botzone_request_diagnostics -q
python -m unittest tests.test_botzone_request_diagnostics tests.test_botzone_poll tests.test_botzone_connector tests.test_botzone_bot_io tests.test_botzone_session tests.test_botzone_rule_agent_e2e -q
python -m unittest discover -q
git diff --check
```

4. 只暂存并提交上述五个文件，提交信息使用 `Add safe Botzone request diagnostics`；不得把 docs 或其他文件混入检查点。
5. 提交后确认工作区干净，并报告检查点完整 SHA-1 与精确文件列表。

任一回归、范围或提交门槛失败时停止，不得进入 preflight。

### B. 零网络恢复准入

仅在检查点成功且工作区干净后执行：

1. 只确认 `BOTZONE_LOCAL_AI_URL` 在当前进程为 `present/missing`，不得输出、复制、散列、拆解或记录其值，不读取 `.env`。
2. 确认没有正在运行的 `integrations.botzone` connector，只报告 `running/not_running`，不得记录命令行。
3. 在 `%LOCALAPPDATA%\GuanDan` 下创建本任务独占、全新、空的 state 目录；不得使用仓库内目录或历史 state。
4. 恰好运行一次现有零网络 preflight：

```text
python -m integrations.botzone --state-dir <fresh-state> --preflight-only
```

5. 设 30 秒硬上限且不重试。严格验证 exit 0、stderr 为空、stdout 规范化后精确为单行 `preflight_ready`。
6. preflight 前后 state 均为空；结束后只删除本任务创建的空目录。
7. request/GET/network/connector count 必须均为 0，不构造 transport/opener，不启动 live launcher。
8. 工作区在 preflight 后仍须干净。

### C. 判定

检查点和全部零网络门槛通过：

```text
botzone_diagnostic_live_smoke_authorization_ready
```

任一门槛失败：

```text
botzone_diagnostic_live_smoke_preflight_invalid
```

失败后不得重试 preflight、启动 connector 或申请 live 授权。

### D. 授权请求

只有 ready 时，最终向用户提出一条明确请求：

```text
请先确认 Botzone 中所有旧的本地 AI 测试桌均已结束，当前没有进行中的旧桌。拟执行一次新的前台 RuleBasedAI 无贡 smoke：使用当前已配置的 BOTZONE_LOCAL_AI_URL、全新 LocalAppData state/audit、最多 100 次 GET、单次 timeout 120 秒、最长 900 秒、完成 1 局即停、不重试。connector 显示已连接后，我会再提示你创建全新测试桌并把“需要进贡”设为“否”。是否确认旧桌已清理并明确授权？
```

不得把文档转述视为授权。必须等待用户在该任务之后明确确认“旧桌已清理”并授权。

### 最终报告

报告检查点、精确提交范围、测试数量、preflight 原始类别而非敏感正文、state 清理、零网络计数、工作区状态和唯一判定。明确说明未联网、未启动 connector、未创建对局，也未形成胜率结论。
