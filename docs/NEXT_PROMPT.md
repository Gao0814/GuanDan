# 下一任务提示词

## Step L5-A4f5：点击白名单保护的 Codex 自动 RuleBased pilot

L5-A4f4 唯一判定：

```text
botzone_codex_corrected_ui_rule_pilot_invalid
```

### 已封存证据

`33001` 根目录只读证据如下，必须原样保留且不得复用：

- v8 audit：695 bytes，SHA-256 `a8785d804626e074d6a4ceeda5bbc41a0f1737e80725aee6e5b400e0c488a24f`；
- exit `130`，stop reason=`interrupted`；
- cycles=`4`，transport timeout=`4`，无其他 transport failure；
- requests/responses/Headers=`0/0/0`；
- Agent/model decisions=`0/0`；
- state 文件数=`0`，无残留 connector；
- audit token 形状合法。

页面曾显示“游戏桌被房主关闭了”，但没有动作日志或目标桌完成证据，不能确认是误点、页面状态切换还是其他 UI 生命周期原因。唯一可确认的是：本次目标桌没有进入 local-AI 请求链路。不得把项目所有者的怀疑写成已证实根因。

### 目标

使用全新 seed `34001` 再做一局 Codex 自动 RuleBased pilot。新增浏览器点击白名单和“开始游戏后完全只读”边界，防止误触关闭/离开/返回/刷新等控制。

### 固定参数

- seed：`34001`
- seat：`0`
- agent：`rule`
- run token：`22b9ad674b07e69fee7b13ddfa033b17`
- 根目录：`D:\VsCodeProject\BotzoneClickFencedPilot-34001`
- state：根目录下全新空 `state`
- audit：根目录下不存在的 `audit\completion.json`
- GuanDan、需要进贡=`否`、级牌=`2`、上轮头游/末游=`0/3`
- 目标 Bot ID：仅使用项目所有者在当前任务中提供的值做内存匹配，不持久化、不输出
- local-AI GET 上限 100、poll timeout 120 秒、wall 3600 秒、finished 1
- 一个 connector、一个桌、零 runmatch、零 DeepSeek、零重试

### 权限

- 项目计划内操作使用常驻默认授权，不再询问项目授权。
- 仓库外写入和真实网络直接调用 `require_escalated`；不要先发文字授权问题。
- 最终“开始游戏”点击仍按浏览器平台规则执行唯一一次即时确认。
- 不读取或输出 `.env`、URL、连接密钥、API key、Header、Cookie、账号、Bot/match ID、牌或动作内容。

### 浏览器点击白名单

最终开始游戏前，Codex 只允许点击语义和当前 DOM 明确匹配的以下控件：

1. 主页面 `创建游戏桌`；
2. 游戏选择中的 `GuanDan`；
3. 游戏选择阶段的 `确认`；
4. 建桌页面的 `载入上次配置`；
5. 固定设置所需的 select/input/radio 控件；
6. 最终且唯一的 `开始游戏`。

禁止点击或触发任何包含以下语义的控件：关闭、取消、返回、退出、结束、终止、离开、解散、删除、重新开始、刷新、浏览器后退、页面 `×`、对局内操作按钮。禁止坐标猜测；只使用 Browser DOM/Playwright 的语义 locator。

点击每个白名单命令前必须读取最新 DOM，确认 locator 唯一、可见、启用且文字精确匹配；点击后立即读取 DOM 验证预期状态转换。无效点击不得盲目重试。

### 执行顺序

1. 只读复核 `33001` audit bytes/SHA-256、空 state 和无残留 connector；不得修改其 root。
2. 确认新 `34001` root 不存在，Botzone 页面已登录且没有活动测试桌。若存在旧桌，只报告阻塞，不自动关闭。
3. 按白名单进入 GuanDan 建桌页并载入上次配置；此时尚未启动 connector。
4. 填写设置并在内存中读取第一份 readback：game=GuanDan、tribute=否、seed=34001、seat=0、level=2、first/last=0/3、target_bot_match=true、三个 opponent_selected=true、local_ai_replacement=true。不得输出 Bot ID/名称。
5. 字段不符时允许通过对应 input/select 修正一次；再次 readback 仍不符则停止。不得点击取消/关闭/返回。
6. 表单停留在最终 `开始游戏` 前。以系统扩展权限创建全新空 state/audit 目录并完成现有 rule preflight；必须 `preflight_ready`、state 空。
7. 在受系统权限的统一 TTY session 中直接运行现有 connector；必须取得 session ID 且无 exit code。禁止 launcher、Start-Process、detached/background 或第二进程。
8. 等待页面显示本地 AI 已连接，并持续轮询同一 session。connector 若在提交前退出，立即 invalid，禁止提交。
9. 连接后读取第二份完整 readback。全部匹配后，在最终 `开始游戏` 前请求唯一即时确认；确认后只点击一次。
10. 点击成功后立即进入“浏览器只读冻结”：只允许 DOM snapshot、URL/title 读取、截图和 connector session 轮询。禁止所有 browser click/fill/type/press/select、reload/back/forward/close 和 CUA 操作。
11. 只读确认页面已进入目标对局且没有“房主关闭”提示；不与游戏页面交互。connector 自行结束前不得主动中断。
12. connector 结束后只读验收 v8 audit、v4 tombstone、token 和请求/结果守恒；不删除 tombstone，不修改仓库。

### 通过门槛

唯一通过判定：

```text
botzone_codex_click_fenced_rule_pilot_verified
```

必须同时满足：

- 所有浏览器写操作都在白名单内，并有点击前后 DOM 状态证据；
- 两次 readback 精确匹配固定字段；
- `开始游戏` 后 browser write action count=`0`；
- completion audit 在最终提交之后产生；
- connector exit `0`、stop reason=`finished_target`；
- requests=responses=Headers 且大于 0；
- qualified finished=`1`、normal result=`1`；
- transport failures=`0`；timeout 只按 idle/timeout 守恒；
- 无其他 diagnostics/detail/profile；
- agent mode=rule、全部决策为 rule primary、model/fallback=`0`；
- v8 audit、v4 最小 tombstone与固定 token 一致；
- 无 active state 或残留 connector；未调用 runmatch、DeepSeek 或第二桌。

任一门槛失败：

```text
botzone_codex_click_fenced_rule_pilot_invalid
```

失败后停止，不重试、不补采、不复用 `34001`/root，不新增诊断载体。

### 后续边界

本步骤只验证自动 UI 安全和 RuleBased 协议闭环；通过后才使用全新 seed/root 规划 Codex 自动 RuleBased/DeepSeek 单对，不形成策略收益或胜率结论。
