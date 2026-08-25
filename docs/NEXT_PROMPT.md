# 下一任务提示词

## Step L5-A4f7：复用已验证建桌表单的 Codex 自动 RuleBased pilot

L5-A4f6 唯一判定：

```text
botzone_guandan_table_ui_selector_contract_verified
```

### 已锁定 UI 契约

- 状态序列：主页 → 游戏选择浮层 → 人工验证码门槛 → GuanDan 建桌表单。
- 游戏选择浮层不是 accessibility `dialog`；以唯一可见的游戏选择控件作为作用域。
- GuanDan 通过选择控件定位，当前选项可证明 selected 状态。
- 浮层内没有“确认”，实际是唯一“创建”按钮；该动作受人工验证码保护。
- 验证通过后进入建桌表单；`载入上次配置` 与 `开始游戏！` 各自唯一可见，并位于共同页面作用域。
- L5-A4f6 未点击 `开始游戏！`，connector/local-AI/DeepSeek/runmatch/table-submit 均为 0。
- 当前 Browser 标签页已保留在 GuanDan 建桌表单，下一步必须复用该页；不得返回主页重新走游戏选择或验证码。

### 目标

在当前已验证的 GuanDan 建桌表单中配置并完成一局 Codex 自动 RuleBased pilot。使用全新 seed `35001`，先完成表单 readback，再启动持续 connector；页面显示已连接并再次 readback 后，只点击一次 `开始游戏！`。进入对局后 Browser 完全只读。

### 固定参数

- seed：`35001`
- seat：`0`
- agent：`rule`
- run token：`cbff43bcd63c9b5ca86b1279b4d97a5f`
- 根目录：`D:\VsCodeProject\BotzoneVerifiedUiPilot-35001`
- state：根目录下全新空 `state`
- audit：根目录下不存在的 `audit\completion.json`
- GuanDan、需要进贡=`否`、级牌=`2`、上轮头游/末游=`0/3`
- 目标 Bot ID：只与项目所有者在当前任务消息中提供的值做内存匹配，不落盘、不输出
- local-AI GET 上限 100、poll timeout 120 秒、wall 3600 秒、finished 1
- 一个 connector、一个桌、零 runmatch、零 DeepSeek、零重试

### 权限与安全

- 项目计划内操作沿用常驻默认授权，不再询问项目授权。
- 仓库外写入和真实网络直接调用 `require_escalated`；不要先发文字授权问题。
- `开始游戏！` 会创建外部对局，浏览器平台仍要求点击前进行一次即时确认；这是唯一保留确认。
- 若验证码重新出现，Codex 不得代为求解；必须由项目所有者完成后再继续。
- 不读取或输出 `.env`、URL、连接密钥、API key、Header、Cookie、账号、Bot/match ID、牌或动作内容。

### 浏览器写操作白名单

提交前仅允许：

1. 当前表单的唯一 `载入上次配置`；
2. 固定本局设置所需的 input/select/radio；
3. 最终且唯一的 `开始游戏！`。

禁止返回主页、重新创建游戏桌、重新选择 GuanDan、点击验证码、关闭/取消/退出/结束/刷新/后退、页面 `×`、坐标猜测或任何对局内动作。

### 执行顺序

1. 只读确认 L5-A4f6 保留的标签页仍为 GuanDan 建桌表单，且 `载入上次配置`/`开始游戏！` 各唯一可见。若标签页丢失、刷新、退回主页或验证码重现，直接 `precondition_failed`；不得自行重走 UI 流程。
2. 确认无残留 connector、无活动测试桌，新 `35001` root 不存在。不得修改或清理 `32001`、`33001` 或其他历史 evidence。
3. 点击唯一 `载入上次配置` 一次，读取 DOM 验证设置已加载。目标 Bot ID 只做内存相等判断，输出仅为 `target_bot_match=true/false`。
4. 通过语义 input/select/radio 设置本局参数，读取第一份完整 readback：game=GuanDan、tribute=否、seed=35001、seat=0、level=2、first/last=0/3、target_bot_match=true、三个 opponent_selected=true、local_ai_replacement=true。
5. 字段不符时允许通过对应表单控件纠正一次；第二次仍不符则停止。不得点击 `开始游戏！`。
6. 表单保持不动。以系统扩展权限创建全新空 state/audit 目录，并用现有 rule `--preflight-only` 验证；必须 exit 0、stdout=`preflight_ready`、stderr/state 空。
7. 在受系统权限的统一 TTY session 中直接运行现有 `.venv\Scripts\python.exe -m integrations.botzone`，传入 rule、绝对 state/audit、固定 token、timeout/cycle/wall/finished 参数。必须返回 session ID 且无 exit code；禁止 launcher、Start-Process、detached/background 或第二 connector。
8. 等待 Botzone 页面显示本地 AI 已连接，并轮询同一 session。若 connector 在提交前退出或 completion audit 提前出现，立即 invalid，不提交、不重试。
9. 页面显示已连接后读取第二份完整 readback；必须与第一份及固定参数完全一致。
10. 全部匹配后，在唯一 `开始游戏！` 点击前请求浏览器平台要求的即时确认；确认后只点击一次。
11. 点击后立即进入 Browser 只读冻结：只允许 DOM snapshot、URL/title、screenshot 与 connector session polling。browser click/fill/type/press/select/reload/back/forward/close/CUA 写操作全部禁止。
12. 只读确认页面进入目标对局，且没有“房主关闭”提示。connector 自行结束前不得主动中断。
13. connector 结束后只读验收 v8 audit、v4 tombstone、固定 token、RuleBased 来源和请求/结果守恒；不删除 tombstone，不修改仓库。

### 通过门槛

唯一通过判定：

```text
botzone_codex_verified_ui_rule_pilot_verified
```

必须同时满足：

- 复用了 L5-A4f6 保留的建桌表单，没有重新走游戏选择/验证码；
- 两次 readback 精确匹配固定字段；
- connector 在最终提交前持续运行且没有 completion audit；
- `开始游戏！` 只点击一次，之后 Browser write count=`0`；
- 页面进入目标对局且未出现房主关闭；
- connector exit `0`、stop reason=`finished_target`；
- requests=responses=Headers 且大于 0；
- qualified finished=`1`、normal result=`1`；
- transport failures=`0`，timeout 只按 idle/timeout 守恒；
- 无其他 diagnostics/detail/profile；
- agent mode=rule、全部决策为 rule primary、model/fallback=`0`；
- v8 audit、v4 最小 tombstone与固定 token 一致；
- 无 active state 或残留 connector；未调用 runmatch、DeepSeek 或第二桌。

任一门槛失败：

```text
botzone_codex_verified_ui_rule_pilot_invalid
```

失败后停止，不重试、不补采、不复用 `35001`/root，不新增诊断载体。

### 后续边界

本步骤只验证已锁定 UI 契约下的自动 RuleBased 闭环。通过后才使用全新 seed/root 规划 Codex 自动 RuleBased/DeepSeek 单对，不形成策略收益或胜率结论。
