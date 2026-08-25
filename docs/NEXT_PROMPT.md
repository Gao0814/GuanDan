# 下一步实施提示词

## Step L5-A4e8：persistent-session tokenized launcher pilot 恢复

L5-A4e7 已停止，唯一判定：

```text
botzone_tokenized_launcher_live_pilot_invalid
```

### 固定证据

- launcher 实现检查点仍为 `2209bb71e35c4142c28bf1218fb316f8cf67da2d`，代码与离线测试结论不变。
- 失效 pilot 根目录 `D:\VsCodeProject\BotzoneLauncherPilot-27001` 只含空 `audit/`、空 `state/` 和两个 0-byte stream 文件；v8 audit 不存在。
- launcher 曾启动，但在页面连接前退出；没有 state、audit、stdout 或 stderr 内容，也没有 Botzone/DeepSeek 对局请求证据。
- 两个 stream 文件已经由 launcher 成功创建，说明参数解析与 stream open 边界大概率已通过；空流与缺失 audit 更符合进程随后被外层执行环境回收。该判断是边界推断，不追认为已证实根因。
- seed `27001` 与该目录永久只读，不得重试、清理、复用或计分。
- 当前 Edge 浏览器扩展已能被 Browser 控制识别；`https://www.botzone.org.cn/` 的 `Botzone` 标签页已成功发现并绑定。后续不得退回无法识别 URL 的桌面截图方案。

项目所有者常驻项目授权继续有效，不再询问 Botzone/DeepSeek 项目授权。浏览器最终提交“创建测试桌”属于外部页面动作，必须按浏览器安全规则在点击前进行一次即时确认；这不是重新申请项目授权。

### 目标

使用全新 seed `28001`、本家座位 `0`、`deepseek` 模式运行恰好一局无贡 pilot。唯一变化是 launcher 必须直接运行在 Codex 的持续前台统一执行会话中，并持有 session ID；禁止任何 detached/background/Start-Process/job 方式。通过 Browser 扩展监督 Botzone 页面，验证进程保活与 v8/v4/token 完整闭环。

### 固定预算

- 新仓库外根目录：`D:\VsCodeProject\BotzoneLauncherPilot-28001`；开始时必须不存在或为空。
- token 由 canonical `pilot/28001/seat0/deepseek` 的 SHA-256 前 32 位派生，不输出。
- 一个 launcher/connector、一个统一执行 session、一个网页桌、一个 state、一个 v8 audit、一个 stdout/stderr 对。
- Botzone GET 最多 100 次；poll timeout 120 秒；wall 3600 秒；完成一局即停；不重试。
- DeepSeek 使用锁定 endpoint/model、timeout 60 秒、retries 0；不得 runmatch、CLI 对局或 probe。
- 桌面固定：需要进贡=否、级牌 2、seed 28001、本家座位 0；其余 profile 与已验证人工 smoke 一致。

### 执行

1. 核对 HEAD/检查点、工作区、无残留 connector、配置脱敏元数据，以及 Edge Browser 扩展中精确存在 `Botzone` + `https://www.botzone.org.cn/` 标签页。不得读取 Cookie、连接 URL、key 或账号信息。
2. 原子创建全新 state/audit/streams 布局；state/streams 为空，audit/stdout/stderr 目标不存在。未知内容立即停止。
3. 使用统一执行工具直接以前台方式运行 `.venv\Scripts\python.exe -m integrations.botzone.live_launcher ...`，显式传入 deepseek/state/token/预算/audit/stdout/stderr。必须等待工具返回“仍在运行”的 session ID；不得使用 `Start-Process`、`&`、PowerShell job、分离子进程、任务计划或未等待 promise。
4. 若启动调用直接返回 exit code，则 launcher 没有保活：读取该调用的固定输出及 stream 类别，脱敏后判 invalid；不得建桌或重启。
5. 保存并持续使用同一 session ID 轮询进程状态；浏览器操作前后都确认 session 仍在运行。不得通过进程名模糊搜索替代 session ID。
6. 通过 Browser 扩展 claim 已存在的 Botzone 标签页并检查页面。若需要登录、验证码或安全确认，请项目所有者处理；不得自动填写认证信息。
7. 页面显示本地 AI“已连接”且 session 仍运行后，由 Codex 打开 GuanDan 测试桌表单，填写唯一无贡桌、seed 28001、seat 0 与固定 profile。在最终点击创建/提交前，向项目所有者进行一次即时浏览器动作确认；确认后点击一次，不得重复提交。
8. 确认进入对局后持续交替检查 Browser 页面与同一执行 session，直到 launcher 自行退出。不得启动第二进程或创建第二桌。
9. 完成门槛：exit 0、`finished_target`、request=response=Header 且大于 0、qualified finished=1、零 transport failure/timeout、空 diagnostics/detail/profile、正常四人结果、agent mode deepseek、全部观测守恒。
10. v8 audit、v4 最小 tombstone 与派生 token 三方精确一致；state 只剩该 tombstone。stdout 只能有固定完成行，stderr 为空。
11. DeepSeek outcome/fallback 守恒；允许 model exposure=0。仅报告脱敏聚合与 artifact bytes/SHA-256，不输出 token、URL、Header、ID、牌、动作、prompt 或模型正文。

### 判定

全部通过：

```text
botzone_persistent_session_launcher_pilot_verified
```

任一 session、Browser、外部确认、协议、transport、结果、stream、v8/v4/token 或敏感门槛失败：

```text
botzone_persistent_session_launcher_pilot_invalid
```

失败不得重试或复用 `28001`。成功后先离线清理唯一 tombstone，再以全新 seed/root 规划新的 paired capacity；本 pilot 不计入策略比较。
