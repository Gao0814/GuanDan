# 下一任务提示词

## Step L5-A4f4：修正 UI 顺序的 Codex 自动 RuleBased pilot

L5-A4f3 唯一判定保持：

```text
botzone_codex_automated_rule_pilot_invalid
```

### 已封存证据

`32001` 根目录只读核验完成，源文件不得修改、删除或复用：

- v8 audit：771 bytes，SHA-256 `6bde11f5f71f1af5244874eac30d0bf18ad6ca493ce992113da9bac5bf4e45e3`；
- exit `0`、stop reason=`finished_target`；
- requests/responses/Headers=`33/33/33`，qualified finished=`1`；
- transport failures=`0`，long-poll timeout=`2` 且只产生对应 timeout 诊断；
- agent mode=`rule`，模型尝试=`0`；
- 唯一 state 为 v4 finished tombstone，115 bytes，SHA-256 `e2b1b430d7501a986829debd15da60963915af30fe24a20a5c2637279abaf0a5`，token 与 audit 一致。

该对局在浏览器设置 readback 和最终提交前已经结束，无法归属于 Codex 自动创建且已核对 `seed=32001` 的桌。上述 evidence 只作为未知来源/旧队列完成记录封存，不进入任何 pilot、capacity 或策略聚合。

### 项目所有者确认的正确网页流程

必须严格按以下顺序操作：

1. 在 Botzone 主页面点击“创建游戏桌”；
2. 选择 `GuanDan`；
3. 点击该游戏选择阶段的“确认”；
4. 页面加载后点击“载入上次配置”；
5. 在内存中确认目标 Bot ID 与项目所有者在当前任务消息中提供的值一致；不得把该 ID 写入文档、Git、audit 或最终报告；
6. 在页面右下角完成本局设置；
7. 只有 connector 显示已连接且所有字段 readback 通过后，点击“开始游戏”。

此前计划错误地先启动 connector、再逐步进入建桌页面，给旧队列/未知桌事件留下了提前完成窗口。本步骤先把网页表单准备到最终提交前，再启动 connector。

### 固定参数

- seed：`33001`
- seat：`0`
- agent：`rule`
- run token：`dc6cffeb1a8764b1851b21100f573be7`
- 根目录：`D:\VsCodeProject\BotzoneCorrectedUiPilot-33001`
- state：根目录下全新空 `state`
- audit：根目录下不存在的 `audit\completion.json`
- 需要进贡：`否`
- 级牌：`2`
- 上轮头游/末游：`0/3`
- 使用项目所有者提供的目标 Bot 配置；Bot ID 仅在当前任务内存中使用
- local-AI GET 上限：100
- poll timeout：120 秒
- wall：3600 秒
- 完成 1 局即停
- 一个 connector、一个网页桌、零 runmatch、零重试

### 权限规则

- 项目计划内操作沿用常驻默认授权，不再询问项目授权。
- 仓库外写入和真实网络直接通过工具请求 `require_escalated`；不要先发文字授权问题。
- 最终“开始游戏”属于代表用户创建外部对局，浏览器平台仍要求点击前进行一次即时确认；这是唯一保留确认。
- 不读取或输出 `.env`、URL、连接密钥、API key、Header、Cookie、账号、Bot ID、match ID、牌或动作内容。

### 执行顺序

1. 只读确认 `32001` audit/state 的 bytes/SHA-256 未变化；确认其 connector 已退出。不得清理该 root。
2. 确认新 `33001` 根目录不存在、无残留 connector、Botzone 没有活动测试桌。若旧桌存在，只报告阻塞，不自动结束。
3. 使用 Browser 扩展 claim 已登录的 Botzone 页面。先按项目所有者给出的正确流程进入 GuanDan 建桌页面并“载入上次配置”。此时尚未启动 connector。
4. 用 DOM 控件完成表单设置，并读取一份内存 readback：
   - game=`GuanDan`
   - tribute=`否`
   - seed=`33001`
   - seat=`0`
   - level=`2`
   - first/last=`0/3`
   - target bot ID match=`true`
   - 三个对手槽 selected=`true`
   - local-AI replacement configured=`true`
5. 只允许输出上述非敏感字段；Bot ID/名称不得输出。字段不符时自动纠正一次并重新读取；仍不符则停止，不启动 connector。
6. 表单保持在最终“开始游戏”按钮前。以系统扩展权限创建唯一新 state/audit 目录，并用现有 rule `--preflight-only` 验证 state；必须 `preflight_ready`、state 空。
7. 通过受系统权限的统一 TTY session 直接运行 `.venv\Scripts\python.exe -m integrations.botzone`：rule、固定绝对 state/audit/token、timeout 120、cycles 100、wall 3600、finished 1。必须返回 session ID 且无 exit code；禁止 launcher、Start-Process、detached/background shell 或第二进程。
8. 立即重新读取页面连接状态并轮询同一 connector session。若 connector 在显示“已连接”前退出，按真实 audit 判 invalid，不提交、不重试。
9. 页面显示“已连接”后，再次核对完整 readback。全部匹配后，在“开始游戏”最终点击前请求唯一即时浏览器确认；确认后只点击一次。
10. 提交后持续监督页面和同一 session，直至 connector 自行结束。不得把提交前收到的 finished 记录计入目标桌；如果 connector 在提交前产生 completion audit，本次立即 invalid。
11. 完成后只读验收 v8 audit、v4 tombstone、token、RuleBased 来源和请求/结果守恒；不删除 tombstone，不修改仓库。

### 通过门槛

唯一通过判定：

```text
botzone_codex_corrected_ui_rule_pilot_verified
```

必须同时满足：

- 网页步骤和两次 readback 均符合固定流程；
- completion audit 只能在点击“开始游戏”之后产生；
- connector exit `0`、stop reason=`finished_target`；
- requests=responses=Headers 且大于 0；
- qualified finished=`1`、normal result=`1`；
- transport failures=`0`；timeout 仅按 idle/timeout 守恒；
- 无其他 diagnostics/detail/profile；
- `agent_mode=rule`，全部决策为 rule primary，模型/fallback=`0`；
- v8 audit、v4 最小 tombstone与固定 token 一致；
- 无 active/pending/effect/handler/cache state，无残留 connector；
- 未调用 runmatch、DeepSeek 或第二桌。

任一门槛失败：

```text
botzone_codex_corrected_ui_rule_pilot_invalid
```

失败后停止，不重试、不补采、不复用 seed `33001` 或该 root，不新增诊断载体。

### 后续边界

本 pilot 只验证正确 UI 顺序下的自动运行与建桌。通过后才使用全新 seed/root 自动执行 RuleBased/DeepSeek 单对；不形成策略收益或胜率结论。
