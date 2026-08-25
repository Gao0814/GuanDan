# 下一任务提示词

## Step L5-A4f3：Codex 自动运行与建桌的 RuleBased pilot

L5-A4f2 已停止，唯一判定：

```text
botzone_owner_operated_single_pair_capacity_invalid
```

第 1 局的 connector、v8 audit、v4 tombstone、RuleBased 决策和正常团队胜均严格有效；唯一失败是项目所有者网页实际填写的随机 seed 不是预注册 `31001`。因此该局不能作为 pair 样本，第 2 局不得启动，原 manifest/audit/state 必须原样保留，seed/root 不得复用。

### 目标

使用全新 seed `32001`，由 Codex 自动持有一个 RuleBased connector 的持续前台 session，并通过已经绑定的 Edge Browser 标签页自动填写一个人工无贡 GuanDan 测试桌。提交前必须读取网页控件值并逐字段核对，避免人工 seed 输入偏差。

该步骤只验证自动运行与建桌链路，不进入 RuleBased/DeepSeek 比较。

### 权限规则

- 项目所有者已对本项目计划内的 Botzone/DeepSeek、仓库外 state/audit 创建、connector 启动和浏览器操作给予常驻默认授权；不要再在聊天中询问项目授权。
- 需要仓库外写入或真实网络时，直接通过工具请求 `require_escalated` 系统权限；该工具确认不是项目授权，不要先发一轮文字询问。
- Botzone 最终“创建/提交”属于代表用户创建外部对局。即使项目已默认授权，浏览器平台仍要求在点击前进行一次即时确认；这是唯一保留的用户确认。不要在更早阶段询问。
- 不读取或输出 `.env`、URL、连接密钥、API key、Header、Cookie、账号、Bot ID 或其他敏感值。

### 固定参数

- seed：`32001`
- seat：`0`
- agent：`rule`
- run token：`eb533b1a510ae5808655c105fdfd30ac`
- 根目录：`D:\VsCodeProject\BotzoneAutomatedPilot-32001`
- state：`D:\VsCodeProject\BotzoneAutomatedPilot-32001\state`
- audit：`D:\VsCodeProject\BotzoneAutomatedPilot-32001\audit\completion.json`
- 需要进贡：`否`
- 级牌：`2`
- 上轮头游/末游：使用默认 `0/3`
- 本家座位：`0`
- 对手：使用此前人工成功桌所用的三个现有 GuanDan Bot；不得把其 ID 写入文档或报告
- local-AI GET 上限：`100`
- poll timeout：`120` 秒
- wall：`3600` 秒
- 完成 1 局即停
- 一个 connector、一个网页桌、零 runmatch、零重试

### 执行顺序

1. 只读确认当前 HEAD 包含 `2209bb71e35c4142c28bf1218fb316f8cf67da2d`、`45d34f0d443847aea527929e2a7c0ebf9e4bdd5a` 和 `31e2fa5a474a377baa3fb80a4a427766623b96c7`；不得还原项目所有者无关改动。
2. 确认没有残留 connector，Botzone 页面已登录且没有活动测试桌。若页面存在旧桌，只报告阻塞，不自动删除或结束旧桌。
3. 以系统扩展权限确认新根目录不存在并创建空 state/audit 目录。若根目录已存在，直接 `precondition_failed`，不得清理后继续。
4. 使用项目 `.venv`，在唯一子进程环境设置 `PYTHON_DOTENV_DISABLED=1`。先以相同 state 路径执行现有 rule `--preflight-only`；必须 exit 0、stdout=`preflight_ready`、stderr 空、state 仍为空。该 preflight 不联网。
5. 直接运行现有 `.venv\Scripts\python.exe -m integrations.botzone`，显式传入 rule、绝对 state/audit、固定 token、timeout/cycle/wall/finished 参数：
   - `exec_command` 必须使用 `sandbox_permissions=require_escalated`、`tty=true`、初始 yield 约 10 秒；
   - 必须返回仍运行的 session ID 且没有 exit code；
   - 禁止 `Start-Process`、launcher、detached/background shell 或第二个 connector；
   - 后续始终使用同一 session ID 轮询。
6. 获得 session ID 后，使用 Browser 扩展 claim 当前 `https://www.botzone.org.cn/` 标签页。重新打开本地 AI 配置只用于读取连接状态，不修改或重新提交连接密钥。
7. 等待页面显示“已连接”。等待期间同步轮询 connector；如果进程先退出，立即按实际 exit/audit 判 invalid，不创建桌、不重试。
8. 自动打开“创建游戏桌”，选择 GuanDan 和“用本地 AI 替代我”，填写固定设置。使用 DOM 控件而不是坐标猜测；每次交互后读取最新 DOM。
9. 在最终提交前，必须生成并核对一份内存 readback，至少包含：game=GuanDan、tribute=否、seed=32001、seat=0、level=2、first/last=0/3、三个对手槽均已选择且没有第二个本地 AI。readback 只输出非敏感字段和三个 `opponent_selected=true`，不得输出 Bot ID/名称。
10. 任一字段不符时自动纠正一次并重新读取；仍不符则停止，不提交。全部匹配后，在最终“创建/提交”按钮前发出唯一即时浏览器确认；确认后只点击一次。
11. 提交后持续轮询同一 session，并通过 Browser 监督对局已进入及结束。不得因聊天响应时序、state 首次出现或页面刷新暂态中止。
12. connector 自行退出后，只读验证 v8 audit、v4 tombstone 与固定 token；不得删除 tombstone。本步骤不修改仓库文件。

### 通过门槛

唯一通过判定：

```text
botzone_codex_automated_rule_pilot_verified
```

必须同时满足：

- 提交前 readback 全部精确匹配固定字段；
- connector exit `0`、stop reason=`finished_target`；
- requests=responses=Headers 且大于 0；
- finished qualified=`1`、normal result=`1`；
- transport failures=`0`；允许独立 long-poll timeout，但只能与 timeout/idle 诊断守恒；
- 无其他 diagnostics/detail/profile；
- `agent_mode=rule`，全部 Agent 决策为 rule primary，模型尝试/fallback=`0`；
- v8 audit 与 v4 最小 tombstone token 精确匹配固定 token；
- 无 active/pending/effect/handler/cache state，无残留 connector；
- 未调用 runmatch、DeepSeek 或第二个测试桌。

### 失败门槛

任一门槛失败：

```text
botzone_codex_automated_rule_pilot_invalid
```

失败后停止，不重试、不补采、不复用 seed `32001` 或根目录。保留原 evidence；不得新增 launcher 或诊断载体。

### 后续边界

该 pilot 通过后，才能用全新 seed/root 规划 Codex 自动执行的 RuleBased/DeepSeek 单对；通过本局不代表策略收益或胜率提升。
