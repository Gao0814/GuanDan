# 下一步实施提示词

## Step L5-A4e7：tokenized launcher 单局可见前台 pilot

L5-A4e6 已完成并封存：

```text
botzone_tokenized_live_launcher_contract_verified
```

### 固定前置

- 实现检查点：`2209bb71e35c4142c28bf1218fb316f8cf67da2d`，提交范围精确为 `integrations/botzone/live_launcher.py` 与 `tests/test_botzone_live_launcher.py`。
- launcher 已严格支持 `--agent`、仓库外绝对 `--state-dir` 与 32 位小写 hex `--run-token`，同进程调用既有 connector 并独立捕获 stdout/stderr。
- 定向 32 项、全量 619 项和 `git diff --check` 均通过；普通 connector 的 v3/v7 默认行为未改。
- 旧批次 `24001/24002`、`25001/25002`、`26001/26002` 及其全部 artifact 永久只读、不得复用或计分。
- 项目所有者已常驻授权计划内 Botzone/DeepSeek 操作，并授权 Codex 使用桌面/浏览器控制监督页面和创建唯一测试桌；不得再次询问项目授权。

### 目标

使用全新 seed `27001`、本家座位 `0`、`deepseek` 模式运行恰好一局人工无贡 pilot，验证新版 launcher 从进程启动、页面连接、建桌、对局到 v8/v4/token 证据的完整生命周期。该 pilot 不是 paired benchmark，不形成策略比较或胜率结论。

### 固定预算

- 新仓库外根目录：`D:\VsCodeProject\BotzoneLauncherPilot-27001`；开始时必须不存在或为空，只能创建本 pilot 的 state、audit 和 stream 布局。
- 一个确定性 32-hex run token，由固定非敏感字段 `pilot/27001/seat0/deepseek` 的 canonical SHA-256 前 32 位派生；不得输出或持久化到 audit/state 以外的位置。
- 仅一个 launcher/connector 进程、一个人工网页桌、一个 state、一个 v8 audit、一个 stdout 和一个 stderr。
- Botzone GET 最多 100 次；poll timeout 120 秒；wall 3600 秒；完成一局即停；不重试。
- DeepSeek 使用当前锁定 endpoint/model，timeout 60 秒、retries 0；不得调用 runmatch、CLI 对局或探测请求。
- 桌面设置固定：需要进贡=否、级牌 2、随机种子 27001、本家座位 0；其余桌面 profile 与已验证人工 smoke 保持一致。

### 执行

1. 只读核对 HEAD、检查点范围、工作区、无残留 connector，以及 Botzone/DeepSeek 配置的脱敏元数据；不得读取 `.env`、URL 或 key 内容。
2. 原子创建全新 pilot 布局；state 与 stream 目录必须为空，audit/stdout/stderr 目标必须不存在。若根目录已有未知内容，立即停止，不清理或复用。
3. 使用项目 `.venv\Scripts\python.exe -m integrations.botzone.live_launcher` 启动唯一进程，显式传入 `deepseek`、state、run token、固定预算和三个输出目标；保留真实进程句柄。
4. 启动后持续检查真实句柄。若进程在页面连接前退出，禁止建桌；读取固定 exit code 和脱敏 stdout/stderr 类别，验证没有敏感内容后直接判 invalid，不重启。
5. 通过 Codex 桌面/浏览器控制观察 Botzone 页面。若尚未登录、出现验证码或平台安全确认，仅在此时请求项目所有者处理；其余情况不要求项目所有者回复。
6. 页面显示“已连接”且进程仍存活后，由 Codex 创建唯一 GuanDan 测试桌，严格选择无贡、seed 27001、本家座位 0 和固定 profile，并确认已进入对局。不得创建第二桌。
7. 持续监督页面与进程直到 connector 自行退出；不得因页面短暂刷新启动第二进程或重复建桌。
8. 完成后验收：exit 0、`finished_target`、request=response=Header 且大于 0、qualified finished=1、零 transport failure/timeout、空 diagnostics/detail/profile、正常四人结果、agent mode=`deepseek`、观测守恒全部通过。
9. v8 audit 与 v4 最小 tombstone 必须严格合法，二者 run token 与本次派生 token 精确一致；state 只能保留该 tombstone。stdout 只能是固定 connector 完成行，stderr 必须为空。
10. DeepSeek model outcome 与 fallback 必须守恒；允许本局 model exposure 为 0，因为本步骤只验 launcher 生命周期，既有 L5-A3c 已证明真实模型成功路径。
11. 仅输出脱敏聚合、audit/tombstone/stream bytes 与 SHA-256；不得输出 token、URL、Header、match/player/Bot ID、牌、动作、prompt、reasoning、响应或账号信息。

### 判定

全部门槛通过：

```text
botzone_tokenized_launcher_live_pilot_verified
```

任一启动、UI、协议、transport、结果、stream、v8/v4/token 或敏感边界失败：

```text
botzone_tokenized_launcher_live_pilot_invalid
```

失败不得重试或复用 seed `27001`。成功也不得直接计入 paired benchmark；成功后先清理唯一 tombstone，再以全新 seed/root 规划 16 局 tokenized capacity 批次。
