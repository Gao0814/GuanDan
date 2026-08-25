# 下一任务提示词

## Step L5-A4f8：已验证 UI 流程下的自动单对策略 pilot

L5-A4f7 唯一判定：

```text
botzone_codex_verified_ui_rule_pilot_verified
```

### 已封板基线

- 复用已验证 GuanDan 表单，两次 readback 均匹配无贡设置与 seed `35001`；
- `开始游戏！` 仅点击一次，之后 Browser 保持只读；
- connector exit `0`、`finished_target`，requests/responses/Headers=`34/34/34`，qualified finished=`1`；
- transport failure=`0`，1 次 idle timeout 不影响完成，无协议 detail/profile；
- RuleBased 33 次决策均为 `rule_primary`，模型/fallback=`0`；
- v8 audit：771 bytes，SHA-256 `a2b1897a23292d18da98257ebdc7975caaf76843d667d0ca73fa8ec5f04561f3`；
- v4 tombstone：115 bytes，SHA-256 `28c91d1cde2851bccee55ff66b4e5f1907a4d8c88b8650a44588248a8bf3ade8`；
- provenance 一致、无 active state、无残留 connector。

该局只证明自动 UI 与 RuleBased 协议闭环，不进入策略比较。

### 目标

使用全新 seed `36001` 和已验证 UI 流程，串行完成一个 RuleBased/DeepSeek 单对：game 1 rule，game 2 deepseek。两局必须使用相同 seed、seat、三个对手和全部桌面设置；分别产生独立 v8/v4/token evidence，最后由现有 `evaluation.botzone_policy_benchmark` 在内存中聚合单对描述结果。

### 固定赛程

- pair seed：`36001`
- seat：`0`
- profile：GuanDan、需要进贡=`否`、级牌=`2`、上轮头游/末游=`0/3`
- 对手：两局复用项目所有者当前提供并已在成功 pilot 中验证的三个 Bot；仅做内存相等比较，不落盘、不输出
- game 1：`rule`，run token=`4b5edb708945eaf84841eae0d4ac77e4`
- game 2：`deepseek`，run token=`ba4f6b9a8d85a3520b4d76ed350af8d8`
- 每局 GET 上限 100、poll timeout 120 秒、wall 3600 秒、finished 1
- DeepSeek timeout/retries：60 秒 / 0
- 顺序固定为 rule → deepseek；不做 AB/BA 推断
- 一个时刻只允许一个 connector 和一个网页桌；零 runmatch、零重试

### 仓库外布局

```text
D:\VsCodeProject\BotzoneVerifiedUiPair-36001\pair-manifest.json
D:\VsCodeProject\BotzoneVerifiedUiPair-36001\game-01-rule\state
D:\VsCodeProject\BotzoneVerifiedUiPair-36001\game-01-rule\audit\completion.json
D:\VsCodeProject\BotzoneVerifiedUiPair-36001\game-02-deepseek\state
D:\VsCodeProject\BotzoneVerifiedUiPair-36001\game-02-deepseek\audit\completion.json
```

manifest 只保存 pair/seed/seat/order/profile/mode/token 与固定预算，不保存 Bot ID、URL、账号、match 或逐局内容。最终聚合报告不得输出 seed/token。

### 权限与隐私

- 项目计划内操作沿用常驻默认授权，不再询问项目授权。
- 仓库外写入、Botzone 和 DeepSeek 网络直接使用工具系统权限请求，不先发文字授权问题。
- 每局最终 `开始游戏！` 前仍按浏览器平台要求进行一次即时确认；共两次，不能预先合并或省略。
- 项目所有者已授权 DeepSeek 接收本家未公开手牌、公开局面、合法候选、手牌评估、记牌摘要、场景标签和本地 RAG 片段；不得额外发送或持久化其他内容。
- 不读取/输出 `.env`、URL、API key、Header、Cookie、Bot/match/player ID、手牌、prompt、RAG 原文、响应或逐手动作。

### 通用单局流程

两局都必须严格复用 L5-A4f7 的已验证顺序：

1. 从 Botzone 主页面按已验证 UI 契约进入 GuanDan 建桌表单；验证码若出现，必须由项目所有者人工完成，Codex 不得求解。
2. 点击唯一 `载入上次配置`，使用语义控件填写固定设置；读取第一份 readback：game、tribute、seed、seat、level、first/last、target_bot_match、三个 opponent_selected、local_ai_replacement。
3. readback 全部匹配后，创建该局空 state/audit 并运行相应 agent 的现有 preflight；必须 `preflight_ready`、state 空。
4. 在受系统权限的统一 TTY session 中直接运行 connector；必须取得 session ID 且无 exit code。禁止 launcher、Start-Process、detached/background 或第二进程。
5. 等待页面显示本地 AI 已连接；connector 若在提交前退出或 completion audit 提前出现，整对 invalid。
6. 读取第二份完整 readback并要求与第一份及 manifest 完全一致。
7. 在唯一 `开始游戏！` 前请求即时确认，确认后只点击一次。
8. 提交后 Browser 完全只读，只允许 snapshot、URL/title、screenshot 和 connector polling；browser write count 必须为 0。
9. connector 自行结束后验收该局 v8/v4/token、请求、结果、策略来源和无残留；未通过不得进入下一局。

### 串行边界

1. 先执行 game 1 rule。通过后保留其 tombstone/audit，不清理。
2. 确认 game 1 connector 已退出且网页桌已结束，再导航回主页并按同一 UI 契约进入 game 2 表单。不得复制 DOM 节点或复用 stale locator；每一步读取最新 DOM。
3. game 2 的第一份 readback 必须与 game 1 manifest 条件完全一致，输出仅为 `pair_conditions_equal=true/false`，不输出 Bot 信息。
4. game 2 deepseek 通过后，严格验证两份 audit，并调用现有 benchmark 聚合这一对。

### 单局验收

两局均须满足：

- 两次 readback 精确匹配，且 pair conditions equal；
- connector 在提交前持续运行且无提前 audit；
- 开始按钮只点击一次，之后 Browser write count=`0`；
- 页面进入目标对局且未显示房主关闭；
- connector exit `0`、stop reason=`finished_target`；
- requests=responses=Headers 且大于 0；
- qualified finished=`1`、normal result=`1`；
- transport failures=`0`，timeout 只按 idle/timeout 守恒；
- 无其他 diagnostics/detail/profile；
- v8 audit、v4 最小 tombstone与各自 manifest token 一致；
- 无 active state 或残留 connector。

策略验收：

- rule：agent mode=rule，全部决策为 rule primary，model/fallback=`0`；
- deepseek：agent mode=deepseek，至少一次 model success，模型 outcome 只允许 success，RuleBased fallback=`0`，decision/attempt/outcome 守恒。

### 判定

全部通过：

```text
botzone_codex_verified_ui_single_pair_capacity_verified
```

只报告该单对的两侧正常结果、score bucket、模型暴露和 existing benchmark 聚合。不得表述为统计显著性、因果增益或胜率提升。

任一局失败：

```text
botzone_codex_verified_ui_single_pair_capacity_invalid
```

立即停止，不重试失败局、不继续下一局、不复用 `36001`/root，不新增诊断载体。

### 后续边界

单对通过后，才使用全新 seed/root 规划 2 seed × 4 seat 的小容量自动恢复；本步骤不恢复历史无效批次。
